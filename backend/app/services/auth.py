"""
认证服务
处理用户注册、登录、JWT Token 生成等
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.repository.user import UserRepository
from app.schemas.auth import (
    UserRegister, UserLogin, TokenResponse, UserResponse,
    PhoneRegister, PhoneLogin
)
from app.models.user import User
from app.services.sms import SMSService


# HTTP Bearer Token 认证
security = HTTPBearer()


class AuthService:
    """认证服务类"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    
    def get_password_hash(self, password: str) -> str:
        """生成密码哈希"""
        return bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')
    
    def create_access_token(self, user_id: str, username: str) -> str:
        """生成 JWT Token"""
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode = {
            "sub": str(user_id),
            "username": username,
            "exp": expire
        }
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt
    
    async def register(self, user_data: UserRegister) -> TokenResponse:
        """
        用户注册 (全量注册：用户名、密码、手机、验证码)
        """
        # 1. 验证密码一致性
        if user_data.password != user_data.confirm_password:
            raise HTTPException(status_code=400, detail="两次输入的密码不一致")

        # 2. 验证短信验证码
        if not SMSService.verify_code(user_data.phone, user_data.code):
            raise HTTPException(status_code=400, detail="验证码错误或已过期")

        # 3. 检查唯一性
        if await self.user_repo.get_by_username(user_data.username):
            raise HTTPException(status_code=400, detail="该用户名已被使用")
        
        if await self.user_repo.get_by_phone(user_data.phone):
            raise HTTPException(status_code=400, detail="该手机号已注册")

        if user_data.email and await self.user_repo.get_by_email(user_data.email):
            raise HTTPException(status_code=400, detail="该邮箱已被注册")

        # 4. 创建用户 (初始角色为 VISITOR, 权限为 PUBLIC)
        hashed_password = self.get_password_hash(user_data.password)
        user = await self.user_repo.create(user_data, hashed_password)
        user.role = "VISITOR"
        user.permission = "PUBLIC"
        
        # 5. 处理邀请逻辑 (游客注册奖励 20 积分)
        if user_data.invitation_code:
            inviter = await self.user_repo.get_by_invitation_code(user_data.invitation_code)
            if inviter:
                user.invited_by_id = inviter.id
                # 邀请一个人成为游客，可获得20积分
                reward_points = 20
                inviter.points += reward_points
                
                # 记录积分流水
                from app.models.transaction import Transaction, TransactionType
                inviter_tx = Transaction(
                    user_id=inviter.id,
                    type=TransactionType.COMMISSION,
                    amount=0,
                    balance_after=inviter.balance,
                    detail=f"邀请好友 {user.username} 注册奖励 {reward_points} 积分"
                )
                self.db.add(inviter_tx)
        
        await self.db.commit()
        await self.db.refresh(user)

        # 6. 生成 Token
        access_token = self.create_access_token(str(user.id), user.username)
        
        return TokenResponse(
            access_token=access_token,
            user=UserResponse.model_validate(user)
        )

    async def login(self, login_data: UserLogin) -> TokenResponse:
        """
        用户登录 (支持 邮箱/用户名/手机号)
        """
        # 先尝试通过邮箱查找
        user = await self.user_repo.get_by_email(login_data.email)
        
        # 如果邮箱未找到，尝试通过用户名查找
        if not user:
            user = await self.user_repo.get_by_username(login_data.email)
            
        # 如果还未找到，尝试通过手机号查找
        if not user:
            user = await self.user_repo.get_by_phone(login_data.email)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="账号或密码错误"
            )
        
        # 验证密码
        if not self.verify_password(login_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="账号或密码错误"
            )
        
        # 检查用户是否被禁用
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="账号已被禁用"
            )
        
        # 更新最后登录时间
        await self.user_repo.update_last_login(user.id)
        await self.db.commit()
        
        # 生成 Token
        access_token = self.create_access_token(str(user.id), user.username)
        
        return TokenResponse(
            access_token=access_token,
            user=UserResponse.model_validate(user)
        )
    
    async def register_by_phone(self, register_data: PhoneRegister) -> TokenResponse:
        """手机号注册"""
        # 1. 验证验证码
        if not SMSService.verify_code(register_data.phone, register_data.code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="验证码错误或已过期"
            )
            
        # 2. 检查手机号是否已存在
        existing_user = await self.user_repo.get_by_phone(register_data.phone)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该手机号已注册"
            )
            
        # 3. 检查用户名是否已存在
        existing_username = await self.user_repo.get_by_username(register_data.username)
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该用户名已被使用"
            )
            
        # 4. 创建用户 (初始角色为 VISITOR, 权限为 PUBLIC)
        user = await self.user_repo.create(register_data, phone=register_data.phone)
        user.role = "VISITOR"
        user.permission = "PUBLIC"
        
        # 5. 处理邀请逻辑 (奖励机制同普通注册)
        if register_data.invitation_code:
            inviter = await self.user_repo.get_by_invitation_code(register_data.invitation_code)
            if inviter:
                user.invited_by_id = inviter.id
                reward_points = 20
                inviter.points += reward_points
                
                from app.models.transaction import Transaction, TransactionType
                inviter_tx = Transaction(
                    user_id=inviter.id,
                    type=TransactionType.COMMISSION,
                    amount=0,
                    balance_after=inviter.balance,
                    detail=f"邀请好友 {user.username} 手机注册奖励 {reward_points} 积分"
                )
                self.db.add(inviter_tx)

        await self.db.commit()
        await self.db.refresh(user)
        
        # 6. 生成 Token
        access_token = self.create_access_token(str(user.id), user.username)
        
        return TokenResponse(
            access_token=access_token,
            user=UserResponse.model_validate(user)
        )

    async def login_by_phone(self, login_data: PhoneLogin) -> TokenResponse:
        """手机号验证码登录"""
        # 1. 验证验证码
        if not SMSService.verify_code(login_data.phone, login_data.code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="验证码错误或已过期"
            )
            
        # 2. 获取用户
        user = await self.user_repo.get_by_phone(login_data.phone)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="该手机号未注册"
            )
            
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="账号已被禁用"
            )
            
        # 3. 更新最后登录时间
        await self.user_repo.update_last_login(user.id)
        await self.db.commit()
        
        # 4. 生成 Token
        access_token = self.create_access_token(str(user.id), user.username)
        
        return TokenResponse(
            access_token=access_token,
            user=UserResponse.model_validate(user)
        )
    
    async def verify_token(self, token: str) -> User:
        """
        验证 JWT Token
        返回用户对象
        """
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id: str = payload.get("sub")
            if user_id is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="无效的认证凭证"
                )
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证凭证"
            )
        
        # 查询用户
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="账号已被禁用"
            )
        
        return user


# 依赖注入：获取当前用户
async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    从请求头中获取 Token 并验证
    返回当前登录用户
    NOTE: DEBUG 模式下，如果没有提供 Token，自动模拟管理员用户
    """
    if not credentials:
        # DEBUG 模式：无 token 时降级为模拟管理员
        if settings.DEBUG:
            from uuid import UUID as _UUID
            return User(
                id=_UUID("d3ce3180-3195-4249-89d1-7818a722b9f3"),
                role="ADMIN",
                username="admin_debug"
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭证"
        )
    token = credentials.credentials
    auth_service = AuthService(db)
    return await auth_service.verify_token(token)


# 依赖注入：获取当前用户（可选）
async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    可选的用户认证
    如果提供了 Token 则验证，否则返回 None
    """
    if not credentials:
        return None
    
    token = credentials.credentials
    auth_service = AuthService(db)
    try:
        return await auth_service.verify_token(token)
    except HTTPException:
        return None

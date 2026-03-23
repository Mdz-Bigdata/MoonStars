"""
用户数据访问层
处理用户相关的数据库操作
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from uuid import UUID
from datetime import datetime

from app.models.user import User
from app.schemas.auth import UserRegister


class UserRepository:
    """用户数据仓库"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """根据邮箱查询用户"""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    async def get_by_username(self, username: str) -> Optional[User]:
        """根据用户名查询用户"""
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()
    
    async def get_by_phone(self, phone: str) -> Optional[User]:
        """根据手机号查询用户"""
        result = await self.db.execute(
            select(User).where(User.phone == phone)
        )
        return result.scalar_one_or_none()

    async def get_by_invitation_code(self, code: str) -> Optional[User]:
        """根据邀请码查询用户"""
        result = await self.db.execute(
            select(User).where(User.invitation_code == code)
        )
        return result.scalar_one_or_none()
    
    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        """根据 ID 查询用户"""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def create(self, user_data: UserRegister, hashed_password: Optional[str] = None, phone: Optional[str] = None) -> User:
        """创建新用户"""
        import random
        import string

        # 生成唯一邀请码
        invitation_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        user = User(
            username=user_data.username,
            email=getattr(user_data, 'email', None),
            phone=phone or getattr(user_data, 'phone', None),
            hashed_password=hashed_password,
            invitation_code=invitation_code
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user
    
    async def update_last_login(self, user_id: UUID) -> None:
        """更新最后登录时间"""
        user = await self.get_by_id(user_id)
        if user:
            user.last_login_at = datetime.utcnow()
            await self.db.flush()
    
    async def update_password(self, user_id: UUID, hashed_password: str) -> bool:
        """更新用户密码"""
        user = await self.get_by_id(user_id)
        if user:
            user.hashed_password = hashed_password
            await self.db.flush()
            return True
        return False

    async def update(
        self, 
        user_id: UUID, 
        username: Optional[str] = None, 
        phone: Optional[str] = None,
        permission: Optional[str] = None,
        mcp_servers: Optional[list] = None,
        user_rules: Optional[str] = None,
        project_rules: Optional[str] = None,
        role: Optional[str] = None,
        invitation_code: Optional[str] = None,
        bank_card_info: Optional[dict] = None,
        wechat_info: Optional[dict] = None,
        alipay_info: Optional[dict] = None
    ) -> Optional[User]:
        """更新用户信息"""
        user = await self.get_by_id(user_id)
        if user:
            if username:
                user.username = username
            if phone:
                user.phone = phone
            if role:
                role_upper = role.upper()
                user.role = role_upper
                # 设置角色默认权限
                if not permission:
                    if role_upper in ["ADMIN", "MEMBER"]:
                        user.permission = "PRIVATE"
                    else:
                        user.permission = "PUBLIC"
            
            if permission:
                perm_upper = permission.upper()
                user.permission = perm_upper
            
            if mcp_servers is not None:
                user.mcp_servers = mcp_servers
            if user_rules is not None:
                user.user_rules = user_rules
            if project_rules is not None:
                user.project_rules = project_rules
            if invitation_code is not None:
                user.invitation_code = invitation_code
            # 账号绑定信息
            if bank_card_info is not None:
                user.bank_card_info = bank_card_info
            if wechat_info is not None:
                user.wechat_info = wechat_info
            if alipay_info is not None:
                user.alipay_info = alipay_info
                
            await self.db.flush()
            await self.db.refresh(user)
            return user
        return None

    async def update_permissions(self, user_id: UUID, role: Optional[str] = None) -> Optional[User]:
        """更新用户角色 (仅限管理员操作)"""
        user = await self.get_by_id(user_id)
        if user and role:
            user.role = role
            await self.db.flush()
            await self.db.refresh(user)
            return user
        return None

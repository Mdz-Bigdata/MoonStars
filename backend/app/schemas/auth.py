"""
认证相关的 Schema
用于请求和响应的数据验证
"""
from pydantic import BaseModel, Field
from typing import Optional, Union
from datetime import datetime
from uuid import UUID


class UserRegister(BaseModel):
    """用户注册请求"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: Optional[str] = Field(None, description="邮箱地址")
    password: str = Field(..., min_length=6, max_length=50, description="密码")
    confirm_password: str = Field(..., min_length=6, max_length=50, description="确认密码")
    phone: str = Field(..., min_length=11, max_length=11, description="手机号")
    code: str = Field(..., min_length=6, max_length=6, description="短信验证码")
    invitation_code: Optional[str] = Field(None, description="邀请码")


class UserUpdate(BaseModel):
    """用户资料更新请求"""
    username: Optional[str] = Field(None, min_length=3, max_length=50, description="用户名")
    phone: Optional[str] = Field(None, min_length=0, max_length=20, description="手机号")
    role: Optional[str] = Field(None, description="admin, member, visitor")
    permission: Optional[str] = Field(None, description="public, private")
    mcp_servers: Optional[Union[dict, list]] = None
    user_rules: Optional[str] = None
    project_rules: Optional[str] = None
    invitation_code: Optional[str] = Field(None, min_length=6, max_length=20, description="邀请码")
    # 账号绑定
    bank_card_info: Optional[dict] = Field(None, description="银行卡绑定信息")
    wechat_info: Optional[dict] = Field(None, description="微信绑定信息")
    alipay_info: Optional[dict] = Field(None, description="支付宝绑定信息")


class UserLogin(BaseModel):
    """用户登录请求"""
    email: str = Field(..., description="邮箱地址或用户名")
    password: str = Field(..., description="密码")


class UserResponse(BaseModel):
    """用户信息响应"""
    id: UUID
    username: str
    email: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool
    role: str # admin, member, visitor
    permission: str # public, private
    balance: int = 0
    points: int = 0
    invitation_code: Optional[str] = None
    invited_by_id: Optional[UUID] = None
    
    # 会员与绑定信息
    membership_expires_at: Optional[datetime] = None
    bank_card_info: Optional[dict] = None
    wechat_info: Optional[dict] = None
    alipay_info: Optional[dict] = None
    
    # 扩展设置
    mcp_servers: Optional[Union[dict, list]] = {}
    user_rules: Optional[str] = None
    project_rules: Optional[str] = None
    
    created_at: datetime
    last_login_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Token 响应"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class PasswordChange(BaseModel):
    """修改密码请求"""
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=50, description="新密码")


# 手机验证码相关
class SendSMSRequest(BaseModel):
    """发送验证码请求"""
    phone: str = Field(..., min_length=11, max_length=11, description="手机号（11位）")


class PhoneRegister(BaseModel):
    """手机号注册请求"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    phone: str = Field(..., min_length=11, max_length=11, description="手机号")
    code: str = Field(..., min_length=6, max_length=6, description="验证码")
    invitation_code: Optional[str] = Field(None, description="邀请码")


class PhoneLogin(BaseModel):
    """手机号登录请求"""
    phone: str = Field(..., min_length=11, max_length=11, description="手机号")
    code: str = Field(..., min_length=6, max_length=6, description="验证码")


"""
用户模型
存储用户账号信息
"""
from sqlalchemy import Column, String, DateTime, Boolean, Enum, Text, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid
import enum

from app.core.database import Base


class UserRole(str, enum.Enum):
    """用户角色"""
    ADMIN = "ADMIN"  # 超级管理员
    MEMBER = "MEMBER"  # 会员
    VISITOR = "VISITOR"  # 访客

class AccountPermission(str, enum.Enum):
    """账号权限/可见性"""
    PUBLIC = "PUBLIC"
    PRIVATE = "PRIVATE"

class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="用户 ID")
    username = Column(String(50), unique=True, nullable=False, index=True, comment="用户名")
    email = Column(String(255), unique=True, nullable=True, index=True, comment="电子邮箱")
    phone = Column(String(20), unique=True, nullable=True, index=True, comment="手机号")
    hashed_password = Column(String(255), nullable=True, comment="哈希密码")
    
    is_active = Column(Boolean, default=True, nullable=False, comment="是否激活")
    is_admin = Column(Boolean, default=False, nullable=False, comment="是否是管理员")
    role = Column(Enum(UserRole), default=UserRole.VISITOR, nullable=False, index=True, comment="用户角色")
    permission = Column(Enum(AccountPermission), default=AccountPermission.PUBLIC, nullable=False, comment="账号权限")
    
    # 扩展设置 (MCP & Rules)
    mcp_servers = Column(JSONB, default=dict, nullable=False, comment="MCP 服务器配置")
    user_rules = Column(Text, nullable=True, comment="全局用户规则")
    project_rules = Column(Text, nullable=True, comment="项目特定规则")

    # 财务与邀请系统
    balance = Column(Integer, default=0, nullable=False, comment="账户余额（单位：分）")
    points = Column(Integer, default=0, nullable=False, comment="奖励积分")
    invitation_code = Column(String(20), unique=True, nullable=True, index=True, comment="专属邀请码")
    invited_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, comment="邀请人 ID")
    
    # 会员与绑定信息
    membership_expires_at = Column(DateTime(timezone=True), nullable=True, comment="会员过期时间")
    bank_card_info = Column(JSONB, nullable=True, comment="银行卡绑定信息")
    wechat_info = Column(JSONB, nullable=True, comment="微信绑定信息")
    alipay_info = Column(JSONB, nullable=True, comment="支付宝绑定信息")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    last_login_at = Column(DateTime(timezone=True), nullable=True, comment="最后登录时间")
    
    def __repr__(self):
        return f"<User {self.username} ({self.role})>"

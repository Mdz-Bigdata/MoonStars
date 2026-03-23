"""
管理员操作日志模型
用于记录权限修改等敏感操作
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from app.core.database import Base


class AdminLog(Base):
    """管理员操作日志"""
    __tablename__ = "admin_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="日志 ID")
    admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True, comment="管理员 ID")
    target_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True, comment="目标用户 ID")
    
    action = Column(String(100), nullable=False, index=True, comment="操作动作") # e.g., "CHANGE_PERMISSION"
    detail = Column(Text, nullable=False, comment="操作详情") # 变动详情
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True, comment="创建时间")

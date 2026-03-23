"""
提现申请模型
用于记录和审核用户提现请求
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.core.database import Base


class WithdrawalStatus(str, enum.Enum):
    """提现状态枚举"""
    PENDING = "pending"    # 待审核
    APPROVED = "approved"   # 已批准（处理中）
    COMPLETED = "completed" # 已完成
    REJECTED = "rejected"   # 已驳回
    FAILED = "failed"       # 转账失败


class WithdrawalRequest(Base):
    """提现申请模型"""
    __tablename__ = "withdrawal_requests"
    
    # 主键
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="提现 ID")
    
    # 用户信息
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True, comment="用户 ID")
    
    # 提现详情
    amount = Column(Integer, nullable=False, comment="提现金额（单位：分）")
    fee = Column(Integer, default=0, comment="手续费（单位：分）")
    actual_amount = Column(Integer, nullable=False, comment="实际到账金额")
    
    # 账户信息
    method = Column(String(50), nullable=False, comment="提现方式 (alipay, wechat, bank)")
    account_info = Column(JSONB, nullable=False, comment="提现账户详情 (名称、账号等)")
    
    # 状态与审核
    status = Column(String(20), default=WithdrawalStatus.PENDING.value, nullable=False, index=True, comment="提现状态")
    reject_reason = Column(String(500), comment="驳回原因")
    
    # 财务流水关联
    transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, comment="更新时间")
    processed_at = Column(DateTime, comment="处理完成时间")
    
    # 关系
    user = relationship("User")
    transaction = relationship("Transaction")

"""
交易记录模型
用于记录余额变动（充值、消费、分佣、提现）
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.core.database import Base


class TransactionType(str, enum.Enum):
    """交易类型枚举"""
    RECHARGE = "recharge"  # 充值
    PURCHASE = "purchase"  # 购买专栏
    COMMISSION = "commission"  # 邀请分佣
    WITHDRAWAL = "withdrawal"  # 提现
    REFUND = "refund"  # 退款


class Transaction(Base):
    """交易记录模型"""
    __tablename__ = "transactions"
    
    # 主键
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="交易 ID")
    
    # 关联用户
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True, comment="用户 ID")
    
    # 交易信息
    type = Column(String(20), nullable=False, index=True, comment="交易类型")
    amount = Column(Integer, nullable=False, comment="变动金额（单位：分，正数为增，负数为减）")
    balance_after = Column(Integer, nullable=False, comment="变动后余额（单位：分）")
    
    # 关联订单/业务
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=True, index=True, comment="关联订单ID")
    detail = Column(String(500), comment="交易详情描述")
    extra_data = Column(JSONB, default=dict, comment="额外数据 (如提现目的地、操作IP等)")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True, comment="创建时间")
    
    # 关系
    user = relationship("User")
    order = relationship("Order")

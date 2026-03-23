"""
订单数据模型
用于支付和订阅管理
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Enum as SQLEnum, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.core.database import Base


class PaymentMethod(str, enum.Enum):
    """支付方式枚举"""
    WECHAT = "wechat"
    ALIPAY = "alipay"


class OrderStatus(str, enum.Enum):
    """订单状态枚举"""
    PENDING = "pending"  # 待支付
    PAID = "paid"  # 已支付
    SHIPPED = "shipped"  # 已发货/已生效
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 支付失败
    CANCELLED = "cancelled"  # 已取消


class Order(Base):
    """订单模型"""
    __tablename__ = "orders"
    
    # 主键
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="订单 ID")
    
    # 用户信息
    user_email = Column(String(200), nullable=True, comment="用户邮箱（可选）")
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True, comment="用户 ID")
    
    # 专栏关联
    column_id = Column(UUID(as_uuid=True), ForeignKey("columns.id"), nullable=False, index=True, comment="专栏 ID")
    
    # 支付信息
    amount = Column(Integer, nullable=False, comment="订单金额（单位：分）")
    payment_method = Column(SQLEnum(PaymentMethod), nullable=False, comment="支付方式")
    status = Column(SQLEnum(OrderStatus), default=OrderStatus.PENDING, nullable=False, index=True, comment="订单状态")
    
    # 第三方交易信息
    transaction_id = Column(String(200), unique=True, nullable=True, comment="第三方支付交易号")
    qr_code_url = Column(String(500), comment="支付二维码 URL")
    
    # 会员中心扩展功能
    logistics_info = Column(JSONB, comment="物流/服务进度信息")
    evaluation = Column(Text, comment="评价内容")
    rating = Column(Integer, comment="评分 (1-5)")
    is_favorite = Column(Boolean, default=False, index=True, comment="是否收藏该记录")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True, comment="创建时间")
    paid_at = Column(DateTime, nullable=True, comment="支付完成时间")
    expires_at = Column(DateTime, nullable=True, comment="订单过期时间")
    
    # 关系
    column = relationship("Column", back_populates="orders")

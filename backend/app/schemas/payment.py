"""
支付和订单相关的 Pydantic Schema
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID

from app.models.order import PaymentMethod, OrderStatus


class OrderCreateRequest(BaseModel):
    """创建订单请求"""
    column_id: UUID = Field(..., description="专栏 ID")
    payment_method: PaymentMethod = Field(..., description="支付方式: wechat/alipay")
    user_email: Optional[str] = Field(None, description="用户邮箱（可选）")


class PaymentQRCode(BaseModel):
    """支付二维码信息"""
    qr_code_url: str = Field(..., description="二维码 URL")
    amount: int = Field(..., description="支付金额（分）")
    expires_in: int = Field(..., description="过期时间（秒）")


class OrderResponse(BaseModel):
    """订单响应"""
    id: UUID
    column_id: UUID
    amount: int
    payment_method: PaymentMethod
    status: OrderStatus
    qr_code_url: Optional[str] = None
    created_at: datetime
    paid_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class OrderCreateResponse(OrderResponse):
    """创建订单响应（包含支付信息）"""
    payment_info: Optional[PaymentQRCode] = None


class PaymentCallbackRequest(BaseModel):
    """支付回调请求（简化版）"""
    transaction_id: str
    order_id: str
    signature: str
    # 实际使用时需要根据微信/支付宝的回调参数调整

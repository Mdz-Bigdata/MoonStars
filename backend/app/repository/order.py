"""
订单数据访问层
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from uuid import UUID
from datetime import datetime

from app.models.order import Order, OrderStatus
from app.schemas.payment import OrderCreateRequest


class OrderRepository:
    """订单数据访问类"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(
        self, 
        order_data: OrderCreateRequest,
        amount: int,
        user_id: Optional[UUID] = None,
        qr_code_url: str = None
    ) -> Order:
        """创建订单"""
        order = Order(
            column_id=order_data.column_id,
            user_email=order_data.user_email,
            user_id=user_id,
            payment_method=order_data.payment_method,
            amount=amount,
            qr_code_url=qr_code_url,
            status=OrderStatus.PENDING
        )
        self.db.add(order)
        await self.db.flush()
        await self.db.refresh(order)
        return order
    
    async def get_by_id(self, order_id: UUID) -> Optional[Order]:
        """根据 ID 获取订单"""
        result = await self.db.execute(
            select(Order).where(Order.id == order_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_transaction_id(self, transaction_id: str) -> Optional[Order]:
        """根据第三方交易号获取订单"""
        result = await self.db.execute(
            select(Order).where(Order.transaction_id == transaction_id)
        )
        return result.scalar_one_or_none()
    
    async def update_status(
        self, 
        order_id: UUID, 
        status: OrderStatus,
        transaction_id: str = None
    ) -> Optional[Order]:
        """更新订单状态"""
        order = await self.get_by_id(order_id)
        if not order:
            return None
        
        order.status = status
        if transaction_id:
            order.transaction_id = transaction_id
        
        if status == OrderStatus.PAID:
            order.paid_at = datetime.utcnow()
        
        await self.db.flush()
        await self.db.refresh(order)
        return order

    async def get_list_by_user(self, user_id: UUID) -> list[Order]:
        """获取用户的订单列表"""
        result = await self.db.execute(
            select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_paid_column_ids(self, user_id: UUID) -> list[UUID]:
        """获取用户已支付的专栏 ID 列表"""
        result = await self.db.execute(
            select(Order.column_id).where(
                Order.user_id == user_id,
                Order.status == OrderStatus.PAID
            )
        )
        return list(result.scalars().all())

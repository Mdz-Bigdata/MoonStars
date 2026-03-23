"""
购买记录数据访问层
支持筛选、搜索、分页
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, or_
from typing import List, Optional, Tuple
from uuid import UUID
from datetime import datetime

from app.models.order import Order, OrderStatus
from app.models.column import Column
from app.models.user import User

class PurchaseRecordRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_records(
        self,
        user_id: Optional[UUID] = None,
        page: int = 1,
        size: int = 10,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        status: Optional[OrderStatus] = None,
        search: Optional[str] = None
    ) -> Tuple[List[Order], int]:
        """获取购买记录（支持筛选和搜索）"""
        query = select(Order).join(Column, Order.column_id == Column.id)
        count_query = select(func.count(Order.id)).select_from(Order).join(Column, Order.column_id == Column.id)
        
        filters = []
        if user_id:
            filters.append(Order.user_id == user_id)
            
        if start_date:
            filters.append(Order.created_at >= start_date)
            
        if end_date:
            filters.append(Order.created_at <= end_date)
            
        if status:
            filters.append(Order.status == status)
            
        if search:
            # 按商品名称或用户名搜索
            search_filter = or_(
                Column.name.ilike(f"%{search}%"),
                # 这里如果需要按用户名搜索，需要额外 JOIN User
            )
            # 如果是管理员，支持按用户名搜索其他人的记录
            if not user_id:
                query = query.join(User, Order.user_id == User.id)
                count_query = count_query.join(User, Order.user_id == User.id)
                search_filter = or_(search_filter, User.username.ilike(f"%{search}%"))
            
            filters.append(search_filter)
            
        if filters:
            query = query.where(and_(*filters))
            count_query = count_query.where(and_(*filters))
            
        # 默认按时间倒序
        query = query.order_by(desc(Order.created_at))
        
        # 分页
        query = query.offset((page - 1) * size).limit(size)
        
        # 执行查询
        result = await self.db.execute(query)
        total = await self.db.scalar(count_query) or 0
        
        return list(result.scalars().all()), total

    async def get_latest_record_detail(self, user_id: UUID) -> Optional[Order]:
        """获取用户最近一次购买记录详情"""
        result = await self.db.execute(
            select(Order)
            .where(Order.user_id == user_id)
            .order_by(desc(Order.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def update_record(self, order_id: UUID, data: dict) -> Optional[Order]:
        """更新记录（评价、收藏、状态等）"""
        result = await self.db.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if not order:
            return None
            
        for key, value in data.items():
            if hasattr(order, key):
                setattr(order, key, value)
        
        await self.db.flush()
        return order

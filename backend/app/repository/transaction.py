"""
交易记录数据访问层
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import List, Optional, Tuple
from uuid import UUID

from app.models.transaction import Transaction

class TransactionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: UUID, type: str, amount: int, balance_after: int, order_id: Optional[UUID] = None, detail: Optional[str] = None) -> Transaction:
        """创建交易记录"""
        tx = Transaction(
            user_id=user_id,
            type=type,
            amount=amount,
            balance_after=balance_after,
            order_id=order_id,
            detail=detail
        )
        self.db.add(tx)
        await self.db.flush()
        await self.db.refresh(tx)
        return tx

    async def get_by_user(self, user_id: UUID, skip: int = 0, limit: int = 20) -> Tuple[List[Transaction], int]:
        """获取用户的交易记录"""
        query = select(Transaction).where(Transaction.user_id == user_id).order_by(desc(Transaction.created_at))
        
        # Get count
        count_query = select(func.count()).select_from(Transaction).where(Transaction.user_id == user_id)
        total = await self.db.scalar(count_query)
        
        # Get items
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

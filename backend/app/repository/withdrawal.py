"""
提现申请数据访问层
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import List, Optional, Tuple
from uuid import UUID

from app.models.withdrawal import WithdrawalRequest, WithdrawalStatus

class WithdrawalRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: UUID, amount: int, method: str, account_info: str, account_name: str) -> WithdrawalRequest:
        """创建提现申请"""
        request = WithdrawalRequest(
            user_id=user_id,
            amount=amount,
            method=method,
            account_info=account_info,
            account_name=account_name,
            status=WithdrawalStatus.PENDING
        )
        self.db.add(request)
        await self.db.flush()
        await self.db.refresh(request)
        return request

    async def get_by_user(self, user_id: UUID) -> List[WithdrawalRequest]:
        """获取用户的提现申请记录"""
        result = await self.db.execute(
            select(WithdrawalRequest).where(WithdrawalRequest.user_id == user_id).order_by(desc(WithdrawalRequest.created_at))
        )
        return list(result.scalars().all())

    async def get_all_pending(self) -> List[WithdrawalRequest]:
        """获取所有待审核的提现申请 (管理员)"""
        result = await self.db.execute(
            select(WithdrawalRequest).where(WithdrawalRequest.status == WithdrawalStatus.PENDING).order_by(WithdrawalRequest.created_at)
        )
        return list(result.scalars().all())

    async def get_by_id(self, request_id: UUID) -> Optional[WithdrawalRequest]:
        """根据 ID 获取提现申请"""
        result = await self.db.execute(
            select(WithdrawalRequest).where(WithdrawalRequest.id == request_id)
        )
        return result.scalar_one_or_none()

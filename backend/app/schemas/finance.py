from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from uuid import UUID
from app.models.withdrawal import WithdrawalStatus

class TransactionSchema(BaseModel):
    id: UUID
    user_id: UUID
    type: str
    amount: int
    balance_after: int
    detail: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

class TransactionListResponse(BaseModel):
    items: List[TransactionSchema]
    total: int

class BalanceResponse(BaseModel):
    balance: int
    points: int
    invitation_code: Optional[str]

class WithdrawalCreate(BaseModel):
    amount: int = Field(..., gt=0)
    method: str = Field(..., description="alipay, wechat, bank")
    account_info: str
    account_name: str
    bank_name: Optional[str] = None

class WithdrawalResponse(BaseModel):
    id: UUID
    amount: int
    method: str
    account_info: str
    account_name: str
    bank_name: Optional[str] = None
    status: WithdrawalStatus
    created_at: datetime
    processed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class WithdrawalAuditRequest(BaseModel):
    approve: bool
    remark: Optional[str] = None

class PointRedeemRequest(BaseModel):
    """积分兑换请求"""
    amount: int = Field(..., description="兑换档位: 1000, 2000, 5000")

class PointRedeemResponse(BaseModel):
    """积分兑换响应"""
    points_deducted: int
    balance_added: int
    new_points: int
    new_balance: int

class FinancialStats(BaseModel):
    """管理员财务统计信息"""
    total_income: int
    total_withdrawals_pending: int
    total_withdrawals_completed: int
    user_count_visitor: int
    user_count_member: int
    user_count_admin: int
    recent_transactions: List[TransactionSchema]

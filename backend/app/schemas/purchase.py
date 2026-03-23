"""
购买记录 Schema
"""
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, List, Any
from app.models.order import OrderStatus, PaymentMethod

class PurchaseRecordResponse(BaseModel):
    id: UUID
    column_name: str
    column_id: UUID
    amount: int
    payment_method: PaymentMethod
    status: OrderStatus
    created_at: datetime
    paid_at: Optional[datetime] = None
    logistics_info: Optional[Any] = None
    evaluation: Optional[str] = None
    rating: Optional[int] = None
    is_favorite: bool = False
    
    class Config:
        from_attributes = True

class PurchaseRecordList(BaseModel):
    total: int
    items: List[PurchaseRecordResponse]
    page: int
    size: int

class OrderEvaluateRequest(BaseModel):
    rating: int # 1-5
    evaluation: str

class OrderStatusUpdate(BaseModel):
    status: OrderStatus

class PurchaseRecordSearchQuery(BaseModel):
    page: int = 1
    size: int = 10
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[OrderStatus] = None
    search: Optional[str] = None

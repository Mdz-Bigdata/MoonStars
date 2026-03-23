"""
专栏相关的 Pydantic Schema
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class ColumnBase(BaseModel):
    """专栏基础信息"""
    name: str = Field(..., min_length=1, max_length=200, description="专栏名称")
    description: Optional[str] = Field(None, description="专栏描述")
    cover_image: Optional[str] = Field(None, description="封面图 URL")
    price: int = Field(0, ge=0, description="价格（单位：分）")
    is_free: bool = Field(True, description="是否免费")
    media_types: List[str] = Field(default_factory=list, description="支持的媒体类型 (text, image, audio, video)")
    update_frequency: Optional[str] = Field(None, description="更新频率")
    category: Optional[str] = Field(None, description="专栏分类 (Linux, 大数据, Web 后端, 大模型)")


class ColumnCreate(ColumnBase):
    """创建专栏"""
    pass


class ColumnUpdate(BaseModel):
    """更新专栏"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    cover_image: Optional[str] = None
    price: Optional[int] = Field(None, ge=0)
    is_free: Optional[bool] = None
    media_types: Optional[List[str]] = None
    update_frequency: Optional[str] = None
    category: Optional[str] = None


class ColumnResponse(ColumnBase):
    """专栏响应"""
    id: UUID
    creator_id: Optional[UUID] = None
    article_count: int
    subscriber_count: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ColumnListResponse(BaseModel):
    """专栏列表响应"""
    total: int
    items: List[ColumnResponse]

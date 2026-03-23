"""
元数据 Schema (标签、分类、收藏)
"""
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, List

class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None

class CategoryCreate(CategoryBase):
    pass

class CategoryResponse(CategoryBase):
    id: UUID
    
    class Config:
        from_attributes = True


class TagBase(BaseModel):
    name: str

class TagCreate(TagBase):
    pass

class TagResponse(TagBase):
    id: UUID
    use_count: int
    
    class Config:
        from_attributes = True


class FavoriteCreate(BaseModel):
    article_id: UUID

class FavoriteResponse(BaseModel):
    id: UUID
    user_id: UUID
    article_id: UUID
    created_at: datetime
    
    class Config:
        from_attributes = True

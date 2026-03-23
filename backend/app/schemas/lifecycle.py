"""
内容生命周期 Schema (版本、模板)
"""
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, List, Dict, Any

class ArticleHistoryResponse(BaseModel):
    """文章历史版本响应"""
    id: UUID
    article_id: UUID
    title: str
    version_num: int
    created_at: datetime
    creator_id: Optional[UUID] = None
    
    class Config:
        from_attributes = True

class ArticleHistoryDetail(ArticleHistoryResponse):
    """文章历史版本详情"""
    content: List[Dict[str, Any]]


class DocumentTemplateBase(BaseModel):
    """文档模板基础"""
    name: str
    description: Optional[str] = None
    content: List[Dict[str, Any]]

class DocumentTemplateCreate(DocumentTemplateBase):
    pass

class DocumentTemplateResponse(DocumentTemplateBase):
    id: UUID
    created_at: datetime
    
    class Config:
        from_attributes = True

"""
文章相关的 Pydantic Schema
用于请求验证和响应序列化
"""
from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum
from app.schemas.metadata import TagResponse # 新增导入


class ArticleStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    PUBLISHED = "PUBLISHED"


class ArticleVisibility(str, Enum):
    PUBLIC = "PUBLIC"
    PRIVATE = "PRIVATE"
    PREVIEW = "PREVIEW"


class TOCItem(BaseModel):
    """目录项"""
    id: str
    level: int
    text: str
    children: List["TOCItem"] = []


class ArticleContentBlock(BaseModel):
    """文章内容块（文本、图片、表格等）"""
    type: str = Field(..., description="块类型: text/image/table/code")
    content: Any = Field(..., description="块内容")


class ArticleConvertRequest(BaseModel):
    """文章转换请求"""
    url: str = Field(..., description="原始文章 URL")
    title: Optional[str] = Field(None, description="强制指定的文章标题（可选）")
    column_id: Optional[UUID] = Field(None, description="所属专栏 ID（可选）")
    cookies: Optional[Dict[str, str]] = Field(None, description="Cookies (用于飞书等鉴权)")
    password: Optional[str] = Field(None, description="访问密码 (针对加密文档)")
    parent_id: Optional[UUID] = Field(None, description="父文档 ID")


class ArticleBatchConvertRequest(BaseModel):
    """批量文章转换请求"""
    urls: List[str] = Field(..., description="文章 URL 列表")
    column_id: Optional[UUID] = Field(None, description="所属专栏 ID（可选）")
    parent_id: Optional[UUID] = Field(None, description="父文档 ID")


class ArticleBase(BaseModel):
    """文章基础信息"""
    title: str
    summary: Optional[str] = None
    # NOTE: source_url 和 source_platform 设为可选，支持原创文章
    source_url: Optional[str] = None
    source_platform: Optional[str] = "original"
    cover_image: Optional[str] = None
    column_id: Optional[UUID] = None
    status: ArticleStatus = ArticleStatus.PUBLISHED
    visibility: ArticleVisibility = ArticleVisibility.PUBLIC
    parent_id: Optional[UUID] = None
    category_id: Optional[UUID] = None
    tag_names: Optional[List[str]] = None  # 创建时传入标签名称
    language: Optional[str] = "zh"
    original_id: Optional[UUID] = None
    is_free: bool = True


class ArticleCreate(ArticleBase):
    """创建文章（URL 转换使用）"""
    content: List[Dict[str, Any]]  # JSONB 格式


class ArticleCreateOriginal(BaseModel):
    """
    原创文章创建请求
    用于创作者在线写文章场景
    """
    title: str = Field(..., description="文章标题")
    content: str = Field(..., description="Markdown 正文")
    summary: Optional[str] = Field(None, description="文章摘要")
    column_id: Optional[UUID] = Field(None, description="关联专栏 ID")
    tag_names: Optional[List[str]] = Field(None, description="标签名称列表")
    status: ArticleStatus = Field(ArticleStatus.DRAFT, description="文章状态，默认草稿")
    cover_image: Optional[str] = Field(None, description="封面图 URL")


class ArticleUpdate(BaseModel):
    """更新文章"""
    title: Optional[str] = None
    summary: Optional[str] = None
    content: Optional[List[Dict[str, Any]]] = None
    cover_image: Optional[str] = None
    column_id: Optional[UUID] = None
    status: Optional[ArticleStatus] = None
    visibility: Optional[ArticleVisibility] = None
    parent_id: Optional[UUID] = None
    category_id: Optional[UUID] = None
    tag_names: Optional[List[str]] = None
    language: Optional[str] = None
    original_id: Optional[UUID] = None
    is_free: Optional[bool] = None


class ArticleResponse(ArticleBase):
    """文章响应（列表展示）"""
    id: UUID
    view_count: int
    lock_user_id: Optional[UUID] = None
    lock_expires_at: Optional[datetime] = None
    column_category: Optional[str] = None # 新增：关联专栏的分类名称
    column_is_free: Optional[bool] = None # 新增：关联专栏是否免费
    tags: List[TagResponse] = []
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ArticleDetailResponse(ArticleResponse):
    """文章详情响应"""
    content: List[Dict[str, Any]]
    toc: List[TOCItem] = []
    
    class Config:
        from_attributes = True

TOCItem.model_rebuild()


class ArticleListResponse(BaseModel):
    """文章列表响应"""
    total: int
    items: List[ArticleResponse]
    page: int
    size: int


class RestoreFromHistory(BaseModel):
    """从历史恢复请求"""
    history_id: UUID


class ConvertResult(BaseModel):
    """单个转换结果"""
    url: str
    success: bool
    article_id: Optional[UUID] = None
    error: Optional[str] = None


class BatchConvertResponse(BaseModel):
    """批量转换响应"""
    total: int
    success_count: int
    failed_count: int
    results: List[ConvertResult]


class ArticleLockResponse(BaseModel):
    """文章锁定响应"""
    success: bool
    locked: bool
    lock_user_id: Optional[UUID] = None
    lock_expires_at: Optional[datetime] = None
    message: Optional[str] = None

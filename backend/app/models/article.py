"""
文章数据模型
存储转换后的博客文章
"""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.core.database import Base


class ArticleStatus(str, enum.Enum):
    """文章状态枚举"""
    DRAFT = "DRAFT"  # 草稿
    PENDING_REVIEW = "PENDING_REVIEW"  # 待审核
    PUBLISHED = "PUBLISHED"  # 已发布


class ArticleVisibility(str, enum.Enum):
    """文章可见性枚举"""
    PUBLIC = "PUBLIC"  # 公开
    PRIVATE = "PRIVATE"  # 私密
    PREVIEW = "PREVIEW"  # 试读


class Article(Base):
    """文章模型"""
    __tablename__ = "articles"
    
    # 主键
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="文章 ID")
    
    # 基本信息
    title = Column(String(500), nullable=False, index=True, comment="文章标题")
    summary = Column(Text, comment="文章摘要")
    content = Column(JSONB, nullable=False, comment="文章内容")
    
    # 来源信息
    # NOTE: source_url 设为可选，支持原创文章（无外部 URL）
    source_url = Column(String(1000), nullable=True, comment="原始文章 URL")
    source_platform = Column(String(50), nullable=True, default="original", index=True, comment="来源平台: wechat/feishu/yuque/original")
    
    # 媒体资源
    cover_image = Column(String(500), comment="封面图 URL")
    
    # 专栏关联
    column_id = Column(UUID(as_uuid=True), ForeignKey("columns.id"), nullable=True, index=True, comment="所属专栏 ID")
    
    # 分类关联
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True, index=True, comment="所属分类 ID")
    
    # 创作者关联
    creator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True, comment="创作者 ID")
    
    # 状态与权限
    status = Column(String(20), default=ArticleStatus.PUBLISHED.value, nullable=False, index=True, comment="文章状态")
    visibility = Column(String(20), default=ArticleVisibility.PUBLIC.value, nullable=False, index=True, comment="文章可见性")
    is_free = Column(Boolean, default=True, comment="是否为免费文章")
    
    # 层级关系
    parent_id = Column(UUID(as_uuid=True), ForeignKey("articles.id"), nullable=True, index=True, comment="父文档 ID")
    
    # 多语言支持
    language = Column(String(10), default="zh", index=True, comment="语言代码")
    original_id = Column(UUID(as_uuid=True), ForeignKey("articles.id"), nullable=True, index=True, comment="原语种文档 ID")
    
    # 统计信息
    view_count = Column(Integer, default=0, comment="浏览次数")
    
    # 锁定信息
    lock_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, comment="锁定用户 ID")
    lock_expires_at = Column(DateTime, nullable=True, comment="锁定过期时间")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, comment="更新时间")
    
    # 关系
    column = relationship("Column", back_populates="articles")
    category = relationship("Category", back_populates="articles")
    tags = relationship("Tag", secondary="article_tags", back_populates="articles")
    history = relationship("ArticleHistory", back_populates="article", cascade="all, delete-orphan", passive_deletes=True)

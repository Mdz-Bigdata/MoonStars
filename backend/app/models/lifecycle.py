"""
内容生命周期模型 (版本、模板)
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class ArticleHistory(Base):
    """文章历史版本模型"""
    __tablename__ = "article_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="历史 ID")
    article_id = Column(UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, index=True, comment="文章 ID")
    
    # 版本快照
    title = Column(String(500), nullable=False, comment="文章标题")
    content = Column(JSONB, nullable=False, comment="文章内容")
    
    version_num = Column(Integer, nullable=False, comment="版本号")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment="创建时间")
    creator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, comment="创建者 ID")
    
    # 关系
    article = relationship("Article", back_populates="history")



class DocumentTemplate(Base):
    """文档模板模型"""
    __tablename__ = "document_templates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="模板 ID")
    name = Column(String(200), nullable=False, comment="模板名称")
    description = Column(Text, comment="模板描述")
    content = Column(JSONB, nullable=False, comment="模板内容") # 预设内容块
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment="创建时间")

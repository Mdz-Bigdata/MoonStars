"""
标签与分类模型
"""
from sqlalchemy import Column, String, ForeignKey, Table, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base


# 文章与标签的多对多关联表
article_tags = Table(
    "article_tags",
    Base.metadata,
    Column("article_id", UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True, comment="文章 ID"),
    Column("tag_id", UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True, comment="标签 ID")
)


class Category(Base):
    """文档分类模型"""
    __tablename__ = "categories"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="分类 ID")
    name = Column(String(100), unique=True, nullable=False, index=True, comment="分类名称")
    description = Column(String(500), comment="分类描述")
    
    # 关系
    articles = relationship("Article", back_populates="category")


class Tag(Base):
    """文档标签模型"""
    __tablename__ = "tags"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="标签 ID")
    name = Column(String(100), unique=True, nullable=False, index=True, comment="标签名称")
    
    # 统计使用频率用于标签云
    use_count = Column(Integer, default=0, comment="使用次数")
    
    # 关系
    articles = relationship("Article", secondary=article_tags, back_populates="tags")

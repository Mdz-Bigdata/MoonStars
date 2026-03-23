"""
专栏数据模型
用于组织付费内容
"""
from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class Column(Base):
    """专栏模型"""
    __tablename__ = "columns"
    
    # 主键
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="专栏 ID")
    
    # 基本信息
    name = Column(String(200), nullable=False, index=True, comment="专栏名称")
    description = Column(Text, comment="专栏描述")
    cover_image = Column(String(500), comment="专栏封面图")
    category = Column(String(50), index=True, comment="专栏分类")
    
    # 定价信息
    price = Column(Numeric(10, 2), default=0.00, nullable=False, comment="价格")
    is_free = Column(Boolean, default=True, nullable=False, index=True, comment="是否免费")
    
    # 扩展信息
    media_types = Column(JSONB, default=list, nullable=False, comment="支持的媒体类型")
    update_frequency = Column(String(50), comment="更新频率")
    
    # 统计信息
    article_count = Column(Integer, default=0, comment="文章数量")
    subscriber_count = Column(Integer, default=0, comment="订阅人数")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, comment="更新时间")
    
    # 关系
    creator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), index=True, comment="创建者 ID")
    creator = relationship("User")
    
    articles = relationship("Article", back_populates="column")
    orders = relationship("Order", back_populates="column")

from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base

class Comment(Base):
    """文章评论模型"""
    __tablename__ = "comments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="评论 ID")
    article_id = Column(UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, index=True, comment="文章 ID")
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True, comment="用户 ID")
    user_name = Column(String(100), default="匿名用户", comment="用户名")
    content = Column(Text, nullable=False, comment="评论内容")
    parent_id = Column(UUID(as_uuid=True), ForeignKey("comments.id", ondelete="CASCADE"), nullable=True, index=True, comment="父评论 ID")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment="创建时间")
    
    # 关系
    article = relationship("Article", backref="comments")
    parent = relationship("Comment", remote_side=[id], backref="replies")
    user = relationship("User", backref="comments")

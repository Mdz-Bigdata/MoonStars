from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, List

class CommentBase(BaseModel):
    content: str
    user_name: Optional[str] = "匿名用户"

class CommentCreate(CommentBase):
    article_id: UUID
    parent_id: Optional[UUID] = None

class Comment(CommentBase):
    id: UUID
    article_id: UUID
    user_id: Optional[UUID] = None
    parent_id: Optional[UUID] = None
    created_at: datetime
    replies: List["Comment"] = []

    class Config:
        from_attributes = True


# To handle circular reference
Comment.model_rebuild()

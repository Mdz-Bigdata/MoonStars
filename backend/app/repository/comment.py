from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import List

from app.models.comment import Comment
from app.schemas.comment import CommentCreate

class CommentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def create(self, comment_data: CommentCreate) -> Comment:
        """创建评论"""
        db_comment = Comment(
            article_id=comment_data.article_id,
            content=comment_data.content,
            user_name=comment_data.user_name or "匿名用户"
        )
        self.db.add(db_comment)
        await self.db.flush()
        return db_comment
        
    async def get_by_article(self, article_id: UUID) -> List[Comment]:
        """获取文章的所有评论"""
        query = select(Comment).where(Comment.article_id == article_id).order_by(Comment.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

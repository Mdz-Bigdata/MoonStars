"""
内容生命周期数据访问层 (版本、模板)
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import List, Optional
from uuid import UUID

from app.models.lifecycle import ArticleHistory, DocumentTemplate

class ArticleHistoryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def create_snapshot(self, article_id: UUID, title: str, content: list, creator_id: Optional[UUID] = None) -> ArticleHistory:
        """为文章创建版本快照"""
        # 获取当前最高版本号
        result = await self.db.execute(
            select(func.max(ArticleHistory.version_num)).where(ArticleHistory.article_id == article_id)
        )
        max_version = result.scalar() or 0
        
        history = ArticleHistory(
            article_id=article_id,
            title=title,
            content=content,
            version_num=max_version + 1,
            creator_id=creator_id
        )
        self.db.add(history)
        await self.db.flush()
        return history
        
    async def get_history_list(self, article_id: UUID) -> List[ArticleHistory]:
        """获取文章的所有历史版本"""
        result = await self.db.execute(
            select(ArticleHistory)
            .where(ArticleHistory.article_id == article_id)
            .order_by(desc(ArticleHistory.version_num))
        )
        return list(result.scalars().all())
        
    async def get_by_id(self, history_id: UUID) -> Optional[ArticleHistory]:
        """获取特定历史版本"""
        result = await self.db.execute(select(ArticleHistory).where(ArticleHistory.id == history_id))
        return result.scalar_one_or_none()


class DocumentTemplateRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def create(self, name: str, content: list, description: str = None) -> DocumentTemplate:
        template = DocumentTemplate(name=name, content=content, description=description)
        self.db.add(template)
        await self.db.flush()
        return template
        
    async def get_all(self) -> List[DocumentTemplate]:
        result = await self.db.execute(select(DocumentTemplate))
        return list(result.scalars().all())
        
    async def get_by_id(self, template_id: UUID) -> Optional[DocumentTemplate]:
        result = await self.db.execute(select(DocumentTemplate).where(DocumentTemplate.id == template_id))
        return result.scalar_one_or_none()

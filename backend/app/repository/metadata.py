"""
元数据数据访问层 (标签、分类、收藏)
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, and_
from typing import List, Optional
from uuid import UUID

from app.models.metadata import Tag, Category, article_tags
from app.models.favorite import Favorite
from app.schemas.metadata import CategoryCreate, TagCreate

class CategoryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def create(self, data: CategoryCreate) -> Category:
        category = Category(**data.model_dump())
        self.db.add(category)
        await self.db.flush()
        return category
        
    async def get_all(self) -> List[Category]:
        result = await self.db.execute(select(Category))
        return list(result.scalars().all())
    
    async def get_by_name(self, name: str) -> Optional[Category]:
        """根据名称获取分类"""
        result = await self.db.execute(select(Category).where(Category.name == name))
        return result.scalar_one_or_none()
    
    async def get_by_id(self, id: UUID) -> Optional[Category]:
        result = await self.db.execute(select(Category).where(Category.id == id))
        return result.scalar_one_or_none()


class TagRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def get_or_create_by_name(self, name: str) -> Tag:
        result = await self.db.execute(select(Tag).where(Tag.name == name))
        tag = result.scalar_one_or_none()
        if not tag:
            tag = Tag(name=name)
            self.db.add(tag)
            await self.db.flush()
        return tag
        
    async def get_all(self) -> List[Tag]:
        result = await self.db.execute(select(Tag).order_by(Tag.use_count.desc()))
        return list(result.scalars().all())

    async def increment_count(self, tag_id: UUID):
        result = await self.db.execute(select(Tag).where(Tag.id == tag_id))
        tag = result.scalar_one_or_none()
        if tag:
            tag.use_count += 1
            await self.db.flush()


class FavoriteRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def add(self, user_id: UUID, article_id: UUID) -> Favorite:
        # 检查是否已收藏
        existing = await self.get_favorite(user_id, article_id)
        if existing:
            return existing
            
        favorite = Favorite(user_id=user_id, article_id=article_id)
        self.db.add(favorite)
        await self.db.flush()
        return favorite
        
    async def remove(self, user_id: UUID, article_id: UUID) -> bool:
        result = await self.db.execute(
            delete(Favorite).where(
                and_(Favorite.user_id == user_id, Favorite.article_id == article_id)
            )
        )
        await self.db.flush()
        return result.rowcount > 0
        
    async def get_by_user(self, user_id: UUID) -> List[Favorite]:
        result = await self.db.execute(
            select(Favorite).where(Favorite.user_id == user_id).order_by(Favorite.created_at.desc())
        )
        return list(result.scalars().all())
        
    async def get_favorite(self, user_id: UUID, article_id: UUID) -> Optional[Favorite]:
        result = await self.db.execute(
            select(Favorite).where(
                and_(Favorite.user_id == user_id, Favorite.article_id == article_id)
            )
        )
        return result.scalar_one_or_none()

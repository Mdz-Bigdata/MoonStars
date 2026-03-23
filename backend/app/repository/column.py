"""
专栏数据访问层
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from uuid import UUID

from app.models.column import Column
from app.schemas.column import ColumnCreate, ColumnUpdate


class ColumnRepository:
    """专栏数据访问类"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(self, column_data: ColumnCreate, creator_id: Optional[UUID] = None) -> Column:
        """创建专栏"""
        data = column_data.model_dump()
        column = Column(**data, creator_id=creator_id)
        self.db.add(column)
        await self.db.flush()
        await self.db.refresh(column)
        return column
    
    async def get_by_id(self, column_id: UUID) -> Optional[Column]:
        """根据 ID 获取专栏"""
        result = await self.db.execute(
            select(Column).where(Column.id == column_id)
        )
        return result.scalar_one_or_none()
    
    async def get_list(self) -> List[Column]:
        """获取所有专栏"""
        result = await self.db.execute(
            select(Column).order_by(Column.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def update(self, column_id: UUID, column_data: ColumnUpdate) -> Optional[Column]:
        """更新专栏"""
        column = await self.get_by_id(column_id)
        if not column:
            return None
        
        update_dict = column_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(column, field, value)
        
        await self.db.flush()
        await self.db.refresh(column)
        return column
    
    async def delete(self, column_id: UUID) -> bool:
        """删除专栏"""
        column = await self.get_by_id(column_id)
        if not column:
            return False
        
        await self.db.delete(column)
        await self.db.flush()
        return True
    
    async def increment_subscriber_count(self, column_id: UUID) -> None:
        """增加订阅人数"""
        column = await self.get_by_id(column_id)
        if column:
            column.subscriber_count += 1
            await self.db.flush()

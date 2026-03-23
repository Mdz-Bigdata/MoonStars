import asyncio
import logging
from decimal import Decimal
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models import article, column, order, user, lifecycle, transaction, withdrawal, system_settings
from app.models.column import Column

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seeding")

FREE_COLUMNS = [
    {"name": "Linux 基础与集群运维教程", "category": "liunx基础与集群运维", "is_free": True, "price": 0},
    {"name": "大数据通识指南", "category": "大数据通识", "is_free": True, "price": 0},
    {"name": "LLM 与 AIGC 实战", "category": "LLM与AIGC", "is_free": True, "price": 0},
    {"name": "前端开发进阶", "category": "前端开发", "is_free": True, "price": 0},
    {"name": "后端开发实战", "category": "后端开发", "is_free": True, "price": 0}
]

PAID_COLUMNS = [
    {"name": "Linux 内核与驱动开发", "category": "Linux 内核与驱动开发", "is_free": False, "price": 5900},
    {"name": "前置工程化与性能优化", "category": "前置工程化与性能优化", "is_free": False, "price": 5900},
    {"name": "大数据实战与架构设计", "category": "大数据实战与架构设计", "is_free": False, "price": 19900},
    {"name": "多种高性能架构演进", "category": "多种高性能架构演进", "is_free": False, "price": 19900},
    {"name": "LLM 架构：RAG 与 Agent 实战", "category": "LLM架构：RAG与Agent实战", "is_free": False, "price": 38800},
]

async def seed():
    async with AsyncSessionLocal() as session:
        for col_data in FREE_COLUMNS + PAID_COLUMNS:
            # Check if exists
            result = await session.execute(
                select(Column).where(Column.name == col_data["name"])
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                logger.info(f"Updating column: {col_data['name']}")
                existing.category = col_data["category"]
                existing.is_free = col_data["is_free"]
                existing.price = Decimal(str(col_data["price"]))
            else:
                logger.info(f"Creating column: {col_data['name']}")
                new_col = Column(
                    name=col_data["name"],
                    category=col_data["category"],
                    is_free=col_data["is_free"],
                    price=Decimal(str(col_data["price"]))
                )
                session.add(new_col)
        
        await session.commit()
        logger.info("Seeding complete.")

if __name__ == "__main__":
    asyncio.run(seed())

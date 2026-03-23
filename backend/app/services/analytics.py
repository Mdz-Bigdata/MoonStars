"""
专栏数据统计服务
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from uuid import UUID
from datetime import datetime, timedelta
from typing import Dict, Any

from app.models.order import Order, OrderStatus
from app.models.article import Article

class AnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_column_analytics(self, column_id: UUID) -> Dict[str, Any]:
        """获取专栏多维度统计数据"""
        # 1. 订阅趋势 (最近 30 天)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        subs_result = await self.db.execute(
            select(func.date(Order.created_at), func.count(Order.id))
            .where(
                Order.column_id == column_id,
                Order.status == OrderStatus.PAID,
                Order.created_after >= thirty_days_ago
            )
            .group_by(func.date(Order.created_at))
        )
        trends = {str(row[0]): row[1] for row in subs_result.all()}

        # 2. 文章阅读量统计
        reading_result = await self.db.execute(
            select(func.sum(Article.view_count))
            .where(Article.column_id == column_id)
        )
        total_views = reading_result.scalar() or 0

        # 3. 互动情况 (评论、收藏等需额外关联)
        return {
            "subscription_trend": trends,
            "total_views": total_views,
            "updated_at": datetime.utcnow()
        }

    async def get_author_summary(self, author_id: UUID) -> Dict[str, Any]:
        """作者工作台总览数据"""
        # 示例：获取该作者名下所有专栏的总收入和总订阅
        # 实际需关联 Column.creator_id (如有此字段)
        return {
            "total_revenue": 0,
            "active_subscribers": 0
        }

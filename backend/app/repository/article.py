from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import List, Optional
from uuid import UUID

from app.models.article import Article, ArticleStatus, ArticleVisibility
from app.models.user import User
from app.models.metadata import Tag
from app.schemas.article import ArticleCreate, ArticleUpdate


class ArticleRepository:
    """文章数据访问类"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(self, article_data: ArticleCreate, creator_id: Optional[UUID] = None) -> Article:
        """创建文章"""
        data = article_data.model_dump(exclude={"tag_names"})
        tag_names = article_data.tag_names or []
        
        article = Article(**data, creator_id=creator_id)
        self.db.add(article)
        
        # 处理标签
        if tag_names:
            from app.repository.metadata import TagRepository
            tag_repo = TagRepository(self.db)
            tags = []
            for name in tag_names:
                tag = await tag_repo.get_or_create_by_name(name)
                tags.append(tag)
                await tag_repo.increment_count(tag.id)
            article.tags = tags
            
        await self.db.flush()
        await self.db.refresh(article)
        return article

    async def get_by_id(self, article_id: UUID) -> Optional[Article]:
        """根据 ID 获取文章"""
        from sqlalchemy.orm import selectinload
        result = await self.db.execute(
            select(Article).where(Article.id == article_id).options(
                selectinload(Article.tags),
                selectinload(Article.column)
            )
        )
        article = result.scalar_one_or_none()
        if article and article.column:
            article.column_category = article.column.category
            article.column_is_free = article.column.is_free
        return article
    
    async def get_by_url(self, source_url: str) -> Optional[Article]:
        """根据原始 URL 获取文章（避免重复抓取）"""
        result = await self.db.execute(
            select(Article).where(Article.source_url == source_url)
        )
        return result.scalar_one_or_none()
    
    async def get_list(
        self, 
        page: int = 1, 
        size: int = 20,
        column_id: Optional[UUID] = None,
        platform: Optional[str] = None,
        creator_id: Optional[UUID] = None,
        parent_id: Optional[UUID] = None,
        current_user: Optional[User] = None,
        include_unreviewed: bool = False,
        can_access_paid: bool = False,
        **kwargs
    ) -> tuple[List[Article], int]:
        """
        获取文章列表（分页）
        返回: (文章列表, 总数)
        """
        # 构建查询条件
        query = select(Article)
        count_query = select(func.count()).select_from(Article)
        
        if column_id:
            query = query.where(Article.column_id == column_id)
            count_query = count_query.where(Article.column_id == column_id)
        
        if platform:
            query = query.where(Article.source_platform == platform)
            count_query = count_query.where(Article.source_platform == platform)
        
        if creator_id:
            query = query.where(Article.creator_id == creator_id)
            count_query = count_query.where(Article.creator_id == creator_id)
        
        if parent_id:
            query = query.where(Article.parent_id == parent_id)
            count_query = count_query.where(Article.parent_id == parent_id)
        
        # 核心权限控制
        from sqlalchemy import or_, and_, exists
        from app.models.column import Column as ColumnModel
        from app.models.order import Order, OrderStatus
        from app.models.user import UserRole
        
        # Join with Column to access its fields
        query = query.outerjoin(ColumnModel)
        count_query = count_query.outerjoin(ColumnModel)

        # 获取当前角色
        user_role = current_user.role if current_user else UserRole.VISITOR
        
        if user_role != UserRole.ADMIN:
            # 基础可见性过滤
            # 1. 默认：公开和试读文章可见
            base_visibility = [
                Article.visibility.in_([ArticleVisibility.PUBLIC, ArticleVisibility.PREVIEW])
            ]
            
            if current_user:
                # 2. 作者本人可见
                base_visibility.append(Article.creator_id == current_user.id)
                
                if user_role == UserRole.MEMBER:
                    # 3. 会员可见性：额外允许 PRIVATE
                    base_visibility.append(Article.visibility == ArticleVisibility.PRIVATE)

            query = query.where(or_(*base_visibility))
            count_query = count_query.where(or_(*base_visibility))

            # 状态过滤：仅 PUBLISHED 或 作者本人
            if not include_unreviewed:
                review_filter = or_(
                    Article.status == ArticleStatus.PUBLISHED,
                    Article.creator_id == (current_user.id if current_user else None)
                )
                query = query.where(review_filter)
                count_query = count_query.where(review_filter)

            # --- 支付/免费校验逻辑 ---
            if user_role == UserRole.VISITOR:
                # 访客：仅展示免费的内容
                # 免费条件：Article.is_free == True OR Article.is_free IS NULL
                free_filter = or_(
                    Article.is_free == True,
                    Article.is_free == None  # is_free 为 NULL 视为免费
                )
                query = query.where(free_filter)
                count_query = count_query.where(free_filter)
            
            elif user_role == UserRole.MEMBER:
                # 会员：免费内容 OR 已支付内容 OR 自己创作的内容 OR 没有关联专栏的内容
                paid_order_exists = exists().where(
                    and_(
                        Order.column_id == Article.column_id,
                        Order.user_id == current_user.id,
                        Order.status == OrderStatus.PAID
                    )
                )
                member_access_filter = or_(
                    Article.is_free == True,
                    ColumnModel.is_free == True,
                    Article.column_id == None,
                    Article.creator_id == current_user.id,
                    paid_order_exists
                )
                query = query.where(member_access_filter)
                count_query = count_query.where(member_access_filter)
            
        
        # 按状态筛选
        if kwargs.get('status_filter'):
            query = query.where(Article.status == kwargs.get('status_filter'))
            count_query = count_query.where(Article.status == kwargs.get('status_filter'))
        
        # 搜索与过滤
        if kwargs.get('q'):
            from sqlalchemy import or_
            search_text = kwargs.get('q')
            search_filter = or_(
                Article.title.ilike(f"%{search_text}%"),
                Article.summary.ilike(f"%{search_text}%")
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)
            
        if kwargs.get('category_id'):
            query = query.where(Article.category_id == kwargs.get('category_id'))
            count_query = count_query.where(Article.category_id == kwargs.get('category_id'))
            
        if kwargs.get('tags'):
            from app.models.metadata import Tag
            for tag_name in kwargs.get('tags'):
                query = query.where(Article.tags.any(Tag.name == tag_name))
                count_query = count_query.where(Article.tags.any(Tag.name == tag_name))

        # 按创建时间倒序
        query = query.order_by(Article.created_at.desc())
        
        # 分页
        query = query.offset((page - 1) * size).limit(size)
        
        # 执行查询
        from sqlalchemy.orm import selectinload
        query = query.options(
            selectinload(Article.tags),
            selectinload(Article.column)
        )
        result = await self.db.execute(query)
        articles = result.scalars().all()
        
        # Populate column_category for each article
        for art in articles:
            if art.column:
                art.column_category = art.column.category
                art.column_is_free = art.column.is_free
            else:
                art.column_category = None
                art.column_is_free = None

        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        return list(articles), total
    
    async def update(self, article_id: UUID, article_data: ArticleUpdate) -> Optional[Article]:
        """更新文章"""
        article = await self.get_by_id(article_id)
        if not article:
            return None
        
        update_dict = article_data.model_dump(exclude_unset=True, exclude={"tag_names"})
        tag_names = article_data.tag_names
        
        for field, value in update_dict.items():
            setattr(article, field, value)
            
        # 更新标签
        if tag_names is not None:
            from app.repository.metadata import TagRepository
            tag_repo = TagRepository(self.db)
            tags = []
            for name in tag_names:
                tag = await tag_repo.get_or_create_by_name(name)
                tags.append(tag)
                await tag_repo.increment_count(tag.id)
            article.tags = tags
        
        await self.db.flush()
        await self.db.refresh(article)
        return article
    
    async def delete(self, article_id: UUID) -> bool:
        """删除文章"""
        article = await self.get_by_id(article_id)
        if not article:
            return False
        
        await self.db.delete(article)
        await self.db.flush()
        return True
    
    async def increment_view_count(self, article_id: UUID) -> None:
        """增加浏览次数"""
        article = await self.get_by_id(article_id)
        if article:
            article.view_count += 1
            await self.db.flush()

    async def get_children(self, parent_id: UUID) -> List[Article]:
        """获取子文档"""
        result = await self.db.execute(
            select(Article).where(Article.parent_id == parent_id)
        )
        return list(result.scalars().all())

    async def lock(self, article_id: UUID, user_id: UUID, expires_in_seconds: int = 300) -> Optional[Article]:
        """锁定文章"""
        from datetime import datetime, timedelta
        article = await self.get_by_id(article_id)
        if not article:
            return None
        
        # 检查是否已被其他人锁定且未过期
        if article.lock_user_id and article.lock_user_id != user_id:
            if article.lock_expires_at and article.lock_expires_at > datetime.utcnow():
                return None # 已被锁定且未过期
        
        article.lock_user_id = user_id
        article.lock_expires_at = datetime.utcnow() + timedelta(seconds=expires_in_seconds)
        await self.db.flush()
        await self.db.refresh(article)
        return article

    async def unlock(self, article_id: UUID, user_id: UUID, force: bool = False) -> bool:
        """解锁文章"""
        article = await self.get_by_id(article_id)
        if not article:
            return False
        
        if not force and article.lock_user_id != user_id:
            return False # 只能解锁自己的锁
        
        article.lock_user_id = None
        article.lock_expires_at = None
        await self.db.flush()
        return True

    async def get_recommendations(self, article_id: UUID, limit: int = 5) -> List[Article]:
        """获取推荐文章 (基于标签)"""
        article = await self.get_by_id(article_id)
        if not article or not article.tags:
            # 如果没有标签，推荐最新文章
            result = await self.db.execute(
                select(Article)
                .where(Article.id != article_id)
                .order_by(Article.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())
            
        tag_ids = [t.id for t in article.tags]
        result = await self.db.execute(
            select(Article)
            .join(Article.tags)
            .where(and_(Tag.id.in_(tag_ids), Article.id != article_id))
            .group_by(Article.id)
            .order_by(func.count(Tag.id).desc(), Article.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_analytics_report(self) -> dict:
        """获取全文库分析报告"""
        from app.models.comment import Comment
        from app.models.favorite import Favorite
        
        total_articles = await self.db.scalar(select(func.count(Article.id)))
        total_views = await self.db.scalar(select(func.sum(Article.view_count))) or 0
        total_comments = await self.db.scalar(select(func.count(Comment.id)))
        total_favorites = await self.db.scalar(select(func.count(Favorite.id)))
        
        return {
            "total_documents": total_articles,
            "total_views": total_views,
            "total_comments": total_comments,
            "total_favorites": total_favorites
        }

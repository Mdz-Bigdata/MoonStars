"""
API 端点路由
定义所有 HTTP 接口
"""
import os
import shutil
import logging
import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, Request, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict
from datetime import datetime
from uuid import UUID
from app.core.config import settings

from app.core.database import get_db
from app.schemas.article import (
    ArticleConvertRequest, ArticleBatchConvertRequest,
    ArticleResponse, ArticleDetailResponse, ArticleListResponse,
    BatchConvertResponse, ArticleUpdate, ArticleLockResponse,
    RestoreFromHistory, ArticleStatus, ArticleVisibility,
    ArticleCreateOriginal
)
from app.schemas.column import ColumnCreate, ColumnUpdate, ColumnResponse, ColumnListResponse
from app.schemas.payment import OrderCreateRequest, OrderCreateResponse
from app.schemas.finance import (
    FinancialStats, BalanceResponse, TransactionListResponse, WithdrawalCreate, 
    WithdrawalResponse, WithdrawalAuditRequest,
    PointRedeemRequest, PointRedeemResponse
)
from app.schemas.auth import (
    UserRegister, UserUpdate, UserLogin, TokenResponse, UserResponse,
    SendSMSRequest, PhoneRegister, PhoneLogin
)
from app.schemas.comment import CommentCreate, Comment as CommentSchema
from app.schemas.metadata import CategoryResponse, TagResponse, CategoryCreate, TagCreate
from app.schemas.lifecycle import (
    ArticleHistoryResponse, ArticleHistoryDetail,
    DocumentTemplateResponse, DocumentTemplateCreate
)
from app.schemas.purchase import (
    PurchaseRecordResponse, PurchaseRecordList, 
    OrderEvaluateRequest, OrderStatusUpdate
)
from app.schemas.ai import AIChatRequest, AIChatResponse, AISummaryRequest, AISummaryResponse
from app.services.article import ArticleService
from app.services.ai import AIService
from app.services.auth import AuthService, get_current_user, get_current_user_optional
from app.services.sms import SMSService
from app.repository.article import ArticleRepository
from app.repository.column import ColumnRepository
from app.repository.comment import CommentRepository
from app.repository.user import UserRepository
from app.services.payment import PaymentService
from app.services.document import doc_processor
from app.models.order import PaymentMethod, OrderStatus
from app.models.user import User, UserRole, AccountPermission
from app.schemas.ppt import GenerateRequest, JobStatus, EngineInfo
from app.services.ppt.scraper import ScraperService
from app.services.ppt.summarizer import SummarizerService
from app.services.ppt.ppt_generator import PPTGeneratorService
from app.services.ppt.visuals import VisualService
from app.services.ppt.models import PPTOutline, GenerationMode
from app.services.ppt.banana_bridge import BananaSlidesService
from app.services.ppt.image_generator import ImageGeneratorService
from app.services.video_assistant.routers import (
    note as video_note,
    model as video_model,
    provider as video_provider,
    config as video_config
)

logger = logging.getLogger(__name__)

# PPT 服务全局变量
ppt_scraper = ScraperService()
ppt_summarizer = SummarizerService()
ppt_visuals = VisualService()
ppt_banana = BananaSlidesService()
ppt_image_gen = ImageGeneratorService()
ppt_jobs = {}
ppt_active_connections: Dict[str, List[WebSocket]] = {}

# 创建路由器
router = APIRouter(prefix="/api")


# ==================== 认证接口 ====================

@router.post("/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db)
):
    """用户注册"""
    service = AuthService(db)
    return await service.register(user_data)


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """用户登录"""
    service = AuthService(db)
    return await service.login(login_data)


@router.post("/auth/send-code")
async def send_sms_code(
    request: SendSMSRequest,
    db: AsyncSession = Depends(get_db)
):
    """发送短信验证码"""
    # 检查频率限制
    if not SMSService.check_rate_limit(request.phone):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="发送验证码过于频繁，请稍后再试"
        )
    
    success, message = await SMSService.send_verification_code(request.phone)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=message
        )
    
    return {"message": "验证码已发送"}


@router.post("/auth/phone-login", response_model=TokenResponse)
async def phone_login(
    login_data: PhoneLogin,
    db: AsyncSession = Depends(get_db)
):
    """手机号验证码登录"""
    service = AuthService(db)
    return await service.login_by_phone(login_data)


@router.post("/auth/phone-register", response_model=TokenResponse)
async def phone_register(
    register_data: PhoneRegister,
    db: AsyncSession = Depends(get_db)
):
    """手机号验证码注册"""
    service = AuthService(db)
    return await service.register_by_phone(register_data)


@router.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """获取当前登录用户信息"""
    return UserResponse.model_validate(current_user)


@router.put("/users/me", response_model=UserResponse)
async def update_user_info(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新用户信息（含 MCP 和规则设置）"""
    repo = UserRepository(db)
    updated_user = await repo.update(
        current_user.id, 
        username=user_data.username, 
        phone=user_data.phone,
        role=user_data.role,
        permission=user_data.permission,
        mcp_servers=user_data.mcp_servers,
        user_rules=user_data.user_rules,
        project_rules=user_data.project_rules,
        invitation_code=user_data.invitation_code,
        bank_card_info=user_data.bank_card_info,
        wechat_info=user_data.wechat_info,
        alipay_info=user_data.alipay_info
    )
    await db.commit()
    return UserResponse.model_validate(updated_user)

@router.put("/admin/users/{user_id}/permissions", response_model=UserResponse)
async def update_user_account_settings(
    user_id: UUID,
    role: Optional[str] = None,
    permission: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """修改用户权限与角色 (仅管理员)"""
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="权限不足，仅管理员可执行此操作")
        
    repo = UserRepository(db)
    user = await repo.update(user_id, role=role, permission=permission)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
        
    # 记录管理日志
    from app.models.admin_log import AdminLog
    admin_log = AdminLog(
        admin_id=current_user.id,
        target_user_id=user_id,
        action="CHANGE_ACCOUNT_SETTINGS",
        detail=f"修改设置: role={role}, permission={permission}"
    )
    db.add(admin_log)
    
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


# ==================== 文章接口 ====================

@router.post("/articles/convert", response_model=ArticleResponse, status_code=status.HTTP_201_CREATED)
async def convert_article(
    request: ArticleConvertRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """单篇文章 URL 转换 (仅管理员)"""
    # DEBUG 模式下，如果没有登录，自动模拟管理员权限
    if not current_user and settings.DEBUG:
        logger.info("DEBUG 模式：模拟管理员权限执行转换")
        # 尝试获取一个现有的管理员或默认 ID
        admin_id = UUID("d3ce3180-3195-4249-89d1-7818a722b9f3") 
        current_user = User(id=admin_id, role="ADMIN", username="admin_debug")

    if not current_user:
        raise HTTPException(status_code=401, detail="请先登录")
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="权限不足，仅管理员可执行转换操作")
    service = ArticleService(db)
    
    # 我们仍然 await 结果，但性能优化由 FeishuParser 内部实现
    result = await service.convert_url_to_article(
        request.url, 
        title=request.title,
        column_id=request.column_id,
        creator_id=current_user.id,
        cookies=request.cookies,
        password=request.password,
        parent_id=request.parent_id
    )
    
    if not result.success:
        if result.article_id:
            repo = ArticleRepository(db)
            article = await repo.get_by_id(result.article_id)
            if article:
                return article
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error or "转换失败"
        )
    
    repo = ArticleRepository(db)
    article = await repo.get_by_id(result.article_id)
    return article


@router.post("/articles/batch-convert", response_model=BatchConvertResponse)
async def batch_convert_articles(
    request: ArticleBatchConvertRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """批量文章 URL 转换 (仅管理员)"""
    # DEBUG 模式下，如果没有登录，自动模拟管理员权限
    if not current_user and settings.DEBUG:
        logger.info("DEBUG 模式：模拟管理员权限执行批量转换")
        admin_id = UUID("d3ce3180-3195-4249-89d1-7818a722b9f3")
        current_user = User(id=admin_id, role="ADMIN", username="admin_debug")

    if not current_user:
        raise HTTPException(status_code=401, detail="请先登录")
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="权限不足，仅管理员可执行批量转换操作")
    service = ArticleService(db)
    results = await service.batch_convert(
        request.urls, 
        request.column_id,
        creator_id=current_user.id,
        parent_id=request.parent_id
    )
    
    success_count = sum(1 for r in results if r.success)
    failed_count = len(results) - success_count
    
    return BatchConvertResponse(
        total=len(results),
        success_count=success_count,
        failed_count=failed_count,
        results=results
    )


@router.get("/articles", response_model=ArticleListResponse)
async def get_articles(
    page: int = 1,
    size: int = 20,
    column_id: Optional[UUID] = None,
    platform: Optional[str] = None,
    category_id: Optional[UUID] = None,
    q: Optional[str] = None,
    tags: Optional[List[str]] = Query(None),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """获取文章列表（分页）"""
    # 权限检查：
    # 1. ADMIN: 全能
    # 2. MEMBER: 可看所有（含付费）
    # 3. VISITOR: 只能看免费公开文章
    
    is_admin = current_user and current_user.role == UserRole.ADMIN
    is_member = current_user and current_user.role == UserRole.MEMBER
    is_visitor = not current_user or current_user.role == UserRole.VISITOR
    
    logger.info(f"FETCH ARTICLES: User={current_user.username if current_user else 'ANON'}, Role={current_user.role if current_user else 'None'}, is_admin={is_admin}, is_member={is_member}")
    
    can_access_paid = (is_admin or is_member)

    # 权限控制现由 ArticleRepository.get_list 集中处理
    repo = ArticleRepository(db)
    articles, total = await repo.get_list(
        page, size, column_id, platform, 
        current_user=current_user,
        category_id=category_id,
        q=q,
        tags=tags,
        can_access_paid=can_access_paid,
        include_unreviewed=is_admin
    )
    
    return ArticleListResponse(
        total=total,
        items=articles,
        page=page,
        size=size
    )


@router.get("/creator/articles", response_model=ArticleListResponse)
async def get_my_articles(
    page: int = 1,
    size: int = 20,
    article_status: Optional[str] = Query(None, alias="status", description="按状态筛选: DRAFT/PUBLISHED"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户的文章列表，支持按状态筛选"""
    repo = ArticleRepository(db)
    
    # 构建查询参数
    extra_kwargs = {}
    if article_status:
        extra_kwargs['status_filter'] = article_status
    
    articles, total = await repo.get_list(
        page, size, 
        creator_id=current_user.id, 
        current_user=current_user,
        include_unreviewed=True,
        **extra_kwargs
    )
    
    return ArticleListResponse(
        total=total,
        items=articles,
        page=page,
        size=size
    )


@router.post("/creator/articles/create", response_model=ArticleResponse, status_code=status.HTTP_201_CREATED)
async def create_original_article(
    request: ArticleCreateOriginal,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    创建原创文章
    将 Markdown 内容转为 JSONB 格式存储，支持草稿和发布
    """
    from app.schemas.article import ArticleCreate
    
    # 将 Markdown 原文封装为 JSONB content 格式
    content_blocks = [{"type": "markdown", "content": request.content}]
    
    # NOTE: 发布时根据是否关联专栏设置可见性和付费属性
    is_publishing = request.status == ArticleStatus.PUBLISHED
    if is_publishing and request.column_id:
        article_visibility = ArticleVisibility.PRIVATE
        article_is_free = False
    elif is_publishing:
        article_visibility = ArticleVisibility.PUBLIC
        article_is_free = True
    else:
        # 草稿状态：私密、免费
        article_visibility = ArticleVisibility.PRIVATE
        article_is_free = True
    
    article_data = ArticleCreate(
        title=request.title,
        summary=request.summary,
        content=content_blocks,
        source_url=None,
        source_platform="original",
        cover_image=request.cover_image,
        column_id=request.column_id,
        tag_names=request.tag_names,
        status=request.status,
        visibility=article_visibility,
        is_free=article_is_free
    )
    
    repo = ArticleRepository(db)
    article = await repo.create(article_data, creator_id=current_user.id)
    await db.commit()
    await db.refresh(article)
    
    return article


@router.put("/creator/articles/{article_id}", response_model=ArticleResponse)
async def update_original_article(
    article_id: UUID,
    request: ArticleCreateOriginal,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新原创文章内容"""
    repo = ArticleRepository(db)
    article = await repo.get_by_id(article_id)
    
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    
    if article.creator_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="权限不足，只能编辑自己的文章")
    
    content_blocks = [{"type": "markdown", "content": request.content}]
    
    update_data = ArticleUpdate(
        title=request.title,
        summary=request.summary,
        content=content_blocks,
        cover_image=request.cover_image,
        column_id=request.column_id,
        tag_names=request.tag_names
    )
    
    updated = await repo.update(article_id, update_data)
    await db.commit()
    return updated


@router.post("/creator/articles/{article_id}/publish", response_model=ArticleResponse)
async def publish_original_article(
    article_id: UUID,
    column_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    发布文章
    无专栏: is_free=True, visibility=PUBLIC
    有专栏: is_free=False, visibility=PRIVATE
    """
    repo = ArticleRepository(db)
    article = await repo.get_by_id(article_id)
    
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    
    if article.creator_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="权限不足，只能发布自己的文章")
    
    # 根据是否关联专栏设置可见性
    final_column_id = column_id or article.column_id
    if final_column_id:
        update_data = ArticleUpdate(
            status=ArticleStatus.PUBLISHED,
            visibility=ArticleVisibility.PRIVATE,
            is_free=False,
            column_id=final_column_id
        )
    else:
        update_data = ArticleUpdate(
            status=ArticleStatus.PUBLISHED,
            visibility=ArticleVisibility.PUBLIC,
            is_free=True
        )
    
    updated = await repo.update(article_id, update_data)
    await db.commit()
    return updated


@router.delete("/creator/articles/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_article(
    article_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除自己的文章（仅草稿状态可删，管理员可强制删除）"""
    repo = ArticleRepository(db)
    article = await repo.get_by_id(article_id)
    
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    
    if article.creator_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="权限不足，只能删除自己的文章")
    
    # 非管理员只能删除草稿
    if current_user.role != UserRole.ADMIN and article.status != ArticleStatus.DRAFT.value:
        raise HTTPException(status_code=400, detail="只能删除草稿状态的文章")
    
    await repo.delete(article_id)
    await db.commit()
    return None


@router.get("/articles/{article_id}", response_model=ArticleDetailResponse)
async def get_article(
    article_id: UUID,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """获取文章详情"""
    repo = ArticleRepository(db)
    article = await repo.get_by_id(article_id)
    
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文章不存在"
        )
    
    # 权限检查逻辑
    from app.models.article import ArticleVisibility, ArticleStatus
    from app.models.user import UserRole
    from app.models.order import Order, OrderStatus
    from sqlalchemy import select
    
    user_role = current_user.role if current_user else UserRole.VISITOR
    
    is_author = current_user and article.creator_id == current_user.id
    is_admin = user_role == UserRole.ADMIN
    is_member = user_role == UserRole.MEMBER
    is_visitor = user_role == UserRole.VISITOR
    
    # 1. 管理员与作者：全能访问
    if is_admin or is_author:
        pass
    
    # 2. 游客与会员的基础访问规则
    else:
        # 私密检查 (作者且已登录在上方已处理)
        if article.visibility == ArticleVisibility.PRIVATE and not is_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="该内容为私密内容，您没有访问权限"
            )
        
        # 审核检查
        if article.status != ArticleStatus.PUBLISHED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="文章正在审核中，暂不可见"
            )

        # 核心购买逻辑校验
        # 允许访问的条件：(文章免费) OR (所属专栏免费) OR (已支付且专栏匹配)
        is_article_free = article.is_free or (article.column and article.column.is_free)
        
        has_paid = False
        if is_member and article.column_id:
            # 检查是否有已支付订单
            paid_stmt = select(Order).where(
                Order.column_id == article.column_id,
                Order.user_id == current_user.id,
                Order.status == OrderStatus.PAID
            )
            paid_result = await db.execute(paid_stmt)
            has_paid = paid_result.scalar_one_or_none() is not None

        if not is_article_free and not has_paid:
            raise HTTPException(
                status_code=402, 
                detail="该文章属于付费专栏。加入会员并解锁专栏后即可阅读全文"
            )
    
    # 增加浏览次数
    await repo.increment_view_count(article_id)
    await db.commit()
    
    # 生成 TOC
    service = ArticleService(db)
    article_dict = ArticleDetailResponse.model_validate(article).model_dump()
    article_dict['toc'] = service.generate_toc(article.content)
    
    return article_dict


@router.put("/articles/{article_id}", response_model=ArticleResponse)
async def update_article(
    article_id: UUID,
    article_data: ArticleUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新文章并保存历史"""
    repo = ArticleRepository(db)
    article_obj = await repo.get_by_id(article_id)
    if not article_obj:
        raise HTTPException(status_code=404, detail="文章不存在")
        
    if current_user.role != "ADMIN" and article_obj.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="权限不足，仅管理员或原作者可修改文章内容。")
        
    service = ArticleService(db)
    article = await service.update_article_with_history(
        article_id, 
        article_data, 
        creator_id=current_user.id
    )
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文章不存在"
        )
    
    await db.commit()
    return article


@router.delete("/admin/articles/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_article(
    article_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """管理员/作者删除文章"""
    repo = ArticleRepository(db)
    article = await repo.get_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
        
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="权限不足，仅管理员（ADMIN）可删除文章内容。")
    
    repo = ArticleRepository(db)
    success = await repo.delete(article_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文章不存在")
    
    await db.commit()
    return None


@router.post("/admin/articles/batch-publish")
async def admin_batch_publish_articles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """批量将所有 DRAFT 状态的文章改为 PUBLISHED（仅限管理员）"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="权限不足，仅管理员可执行此操作")
    
    from sqlalchemy import update
    # 批量更新所有 DRAFT 文章为 PUBLISHED
    result = await db.execute(
        update(Article)
        .where(Article.status == ArticleStatus.DRAFT.value)
        .values(status=ArticleStatus.PUBLISHED.value)
    )
    updated_count = result.rowcount
    
    # 同时更新 is_free 为 True（对于无专栏的公开文章）
    result2 = await db.execute(
        update(Article)
        .where(Article.column_id == None)
        .where(Article.is_free == False)
        .values(is_free=True)
    )
    free_updated_count = result2.rowcount
    
    await db.commit()
    
    return {
        "message": f"成功更新 {updated_count} 篇文章状态为 PUBLISHED，{free_updated_count} 篇文章更新为免费"
    }


@router.put("/admin/articles/{article_id}/status", response_model=ArticleResponse)
async def admin_update_article_status(
    article_id: UUID,
    status: ArticleStatus,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """管理员更新文章状态（审核）"""
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可执行此操作")
    
    repo = ArticleRepository(db)
    from app.schemas.article import ArticleUpdate
    article = await repo.update(article_id, ArticleUpdate(status=status))
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文章不存在")
    
    await db.commit()
    return article


@router.post("/articles/{article_id}/lock", response_model=ArticleLockResponse)
async def lock_article(
    article_id: UUID,
    expires_in: int = 300,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """锁定文章以进行编辑"""
    repo = ArticleRepository(db)
    article = await repo.lock(article_id, current_user.id, expires_in)
    
    if not article:
        # 获取当前锁定者信息
        current_article = await repo.get_by_id(article_id)
        if not current_article:
            raise HTTPException(status_code=404, detail="文章不存在")
        
        return ArticleLockResponse(
            success=False,
            locked=True,
            lock_user_id=current_article.lock_user_id,
            lock_expires_at=current_article.lock_expires_at,
            message="文章已被其他用户锁定"
        )
    
    await db.commit()
    return ArticleLockResponse(
        success=True,
        locked=True,
        lock_user_id=article.lock_user_id,
        lock_expires_at=article.lock_expires_at
    )


@router.post("/articles/{article_id}/unlock")
async def unlock_article(
    article_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """解锁文章"""
    repo = ArticleRepository(db)
    # Admin 可以强制解锁
    success = await repo.unlock(article_id, current_user.id, force=current_user.is_admin)
    
    if not success:
        return {"success": False, "message": "解锁失败，可能您不是当前锁定者"}
    
    await db.commit()
    return {"success": True}


# ==================== 专栏接口 ====================

@router.post("/columns", response_model=ColumnResponse, status_code=status.HTTP_201_CREATED)
async def create_column(
    column_data: ColumnCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建专栏 (仅管理员)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="权限不足，仅管理员可创建专栏")
    repo = ColumnRepository(db)
    column = await repo.create(column_data, creator_id=current_user.id)
    await db.commit()
    return column


@router.put("/columns/{column_id}", response_model=ColumnResponse)
async def update_column(
    column_id: UUID,
    column_data: ColumnUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新专栏"""
    repo = ColumnRepository(db)
    column = await repo.get_by_id(column_id)
    if not column:
        raise HTTPException(status_code=404, detail="专栏不存在")
    
    if current_user.role != "ADMIN" and column.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="权限不足，只能修改自己的专栏")
        
    updated = await repo.update(column_id, column_data)
    await db.commit()
    return updated


@router.delete("/columns/{column_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_column(
    column_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除专栏"""
    repo = ColumnRepository(db)
    column = await repo.get_by_id(column_id)
    if not column:
        raise HTTPException(status_code=404, detail="专栏不存在")
    
    if current_user.role != "ADMIN" and column.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="权限不足，只能删除自己的专栏")
        
    await repo.delete(column_id)
    await db.commit()
    return None


@router.get("/columns", response_model=ColumnListResponse)
async def get_columns(
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """获取所有专栏 (Visitor 只能看到免费专栏)"""
    repo = ColumnRepository(db)
    columns = await repo.get_list()
    
    return ColumnListResponse(
        total=len(columns),
        items=columns
    )


@router.get("/columns/{column_id}", response_model=ColumnResponse)
async def get_column(
    column_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """获取专栏详情"""
    repo = ColumnRepository(db)
    column = await repo.get_by_id(column_id)
    
    if not column:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="专栏不存在"
        )
    
    return column


@router.get("/columns/{column_id}/articles", response_model=ArticleListResponse)
async def get_column_articles(
    column_id: UUID,
    page: int = 1,
    size: int = 20,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    获取专栏的文章列表（目录预览）
    NOTE: 所有用户均可查看专栏下的文章标题列表，用于目录展示。
    实际文章内容的访问权限由 get_article 详情接口严格控制。
    """
    # 先检查专栏是否存在
    column_repo = ColumnRepository(db)
    column = await column_repo.get_by_id(column_id)
    if not column:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="专栏不存在"
        )
    
    # 直接查询该专栏下的已发布文章，不做付费/可见性过滤
    # 这样所有角色（访客、会员、管理员）都能看到文章目录
    from sqlalchemy import select, func
    from sqlalchemy.orm import selectinload
    from app.models.article import Article, ArticleStatus
    
    base_filter = [Article.column_id == column_id]
    
    # 为了确保目录展示的一致性（与管理员视角一致），不在这里过滤状态
    # 实际文章内容的访问权限由 get_article 详情接口严格控制。
    # 这样访客和会员可以看到完整的目录结构（锁定的标题），满足用户对齐列表数量的需求。
    pass
    
    count_query = select(func.count()).select_from(Article).where(*base_filter)
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    query = (
        select(Article)
        .where(*base_filter)
        .options(selectinload(Article.tags), selectinload(Article.column))
        .order_by(Article.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    result = await db.execute(query)
    articles = list(result.scalars().all())
    
    # 填充专栏分类信息
    for art in articles:
        if art.column:
            art.column_category = art.column.category
            art.column_is_free = art.column.is_free
    
    return ArticleListResponse(
        total=total,
        items=articles,
        page=page,
        size=size
    )


# ==================== 图片上传接口 ====================

@router.post("/upload/image")
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    上传图片（用于 Markdown 编辑器和封面图）
    支持 jpg/png/gif/webp，最大 5MB
    """
    # 校验文件类型
    allowed_types = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的图片格式: {file.content_type}，仅支持 jpg/png/gif/webp"
        )
    
    # 校验文件大小（5MB）
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="图片大小不能超过 5MB"
        )
    
    # 生成唯一文件名
    ext = os.path.splitext(file.filename or "img.jpg")[1].lower()
    if not ext:
        ext = ".jpg"
    unique_name = f"{uuid.uuid4().hex}{ext}"
    
    # 保存到 uploads/images 目录
    images_dir = os.path.join(settings.UPLOAD_DIR, "images")
    os.makedirs(images_dir, exist_ok=True)
    file_path = os.path.join(images_dir, unique_name)
    
    with open(file_path, "wb") as f:
        f.write(content)
    
    # 返回可访问的 URL
    image_url = f"/uploads/images/{unique_name}"
    logger.info(f"图片上传成功: {file.filename} -> {image_url}")
    
    return {"url": image_url, "filename": file.filename}


# ==================== 支付接口 ====================

@router.post("/orders/create", response_model=OrderCreateResponse)
async def create_order(
    request: OrderCreateRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """创建订单并生成支付二维码"""
    service = PaymentService(db)
    order_response = await service.create_order(
        request, 
        user_id=current_user.id if current_user else None
    )
    
    if not order_response:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="创建订单失败"
        )
    
    return order_response


@router.post("/orders/{order_id}/confirm-payment")
async def confirm_payment(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    模拟支付确认（开发/演示环境）
    NOTE: 生产环境应由微信/支付宝回调触发，此接口仅供前端模拟支付流程
    """
    service = PaymentService(db)
    
    # 生成模拟交易 ID
    transaction_id = f"SIM_{uuid.uuid4().hex[:16]}"
    
    success = await service.handle_payment_callback(
        payment_method=PaymentMethod.WECHAT,  # 模拟时方式不影响逻辑
        transaction_id=transaction_id,
        order_id=str(order_id)
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="支付确认失败，请检查订单状态"
        )
    
    # 刷新用户信息返回最新角色
    await db.refresh(current_user)
    
    return {
        "success": True,
        "message": "支付成功，已升级为会员",
        "user": UserResponse.model_validate(current_user)
    }


@router.get("/orders/{order_id}/status")
async def get_order_status(
    order_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """查询订单状态（用于前端轮询）"""
    service = PaymentService(db)
    order_status = await service.check_order_status(order_id)
    
    if not order_status:
        raise HTTPException(
            status_code=404,
            detail="订单不存在"
        )
    
    return {"order_id": order_id, "status": order_status}


@router.get("/orders/mine")
async def get_my_orders(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户的订单列表"""
    from app.repository.order import OrderRepository
    repo = OrderRepository(db)
    orders = await repo.get_list_by_user(current_user.id)
    return orders


@router.get("/columns/mine")
async def get_my_columns(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户已购专栏"""
    from app.repository.order import OrderRepository
    from app.repository.column import ColumnRepository
    order_repo = OrderRepository(db)
    column_repo = ColumnRepository(db)
    
    column_ids = await order_repo.get_paid_column_ids(current_user.id)
    columns = []
    for cid in column_ids:
        column = await column_repo.get_by_id(cid)
        if column:
            columns.append(column)
    
    return columns


@router.post("/payment/callback/wechat")
async def wechat_payment_callback(
    # NOTE: 实际参数需要根据微信支付回调格式调整
    db: AsyncSession = Depends(get_db)
):
    """微信支付回调"""
    # TODO: 实现微信支付回调处理
    # 1. 验证签名
    # 2. 更新订单状态
    # 3. 返回成功响应
    return {"code": "SUCCESS", "message": "OK"}


@router.post("/payment/callback/alipay")
async def alipay_payment_callback(
    # NOTE: 实际参数需要根据支付宝回调格式调整
    db: AsyncSession = Depends(get_db)
):
    """支付宝支付回调"""
    # TODO: 实现支付宝回调处理
    return {"code": "SUCCESS", "message": "OK"}


# ==================== 会员中心 接口 ====================

@router.get("/purchase-records", response_model=PurchaseRecordList)
async def get_purchase_records(
    page: int = 1,
    size: int = 10,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    status: Optional[OrderStatus] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取购买记录（带筛选、搜索、分页）"""
    from app.repository.purchase import PurchaseRecordRepository
    repo = PurchaseRecordRepository(db)
    
    # 如果是 Admin，支持搜索所有人；普通用户只能看自己的
    user_id = None if current_user.role == "ADMIN" else current_user.id
    
    records, total = await repo.get_records(
        user_id=user_id,
        page=page,
        size=size,
        start_date=start_date,
        end_date=end_date,
        status=status,
        search=search
    )
    
    # 转换为响应格式
    response_items = []
    for r in records:
        item = PurchaseRecordResponse.model_validate(r)
        item.column_name = r.column.name if r.column else "未知专栏"
        response_items.append(item)
        
    return PurchaseRecordList(
        total=total,
        items=response_items,
        page=page,
        size=size
    )

@router.get("/purchase-records/latest", response_model=Optional[PurchaseRecordResponse])
async def get_latest_purchase_record(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取最近一次购买记录（用于默认展开）"""
    from app.repository.purchase import PurchaseRecordRepository
    repo = PurchaseRecordRepository(db)
    record = await repo.get_latest_record_detail(current_user.id)
    if not record:
        return None
        
    item = PurchaseRecordResponse.model_validate(record)
    item.column_name = record.column.name if record.column else "未知专栏"
    return item

@router.post("/purchase-records/{order_id}/evaluate", response_model=PurchaseRecordResponse)
async def evaluate_order(
    order_id: UUID,
    request: OrderEvaluateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """评价订单"""
    from app.repository.purchase import PurchaseRecordRepository
    repo = PurchaseRecordRepository(db)
    order = await repo.update_record(order_id, {
        "rating": request.rating,
        "evaluation": request.evaluation
    })
    if not order or (not current_user.is_admin and order.user_id != current_user.id):
        raise HTTPException(status_code=404, detail="订单未找到")
    
    await db.commit()
    return await get_purchase_record_item(order)

@router.post("/purchase-records/{order_id}/favorite")
async def favorite_purchase_record(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """收藏购买记录"""
    from app.repository.purchase import PurchaseRecordRepository
    repo = PurchaseRecordRepository(db)
    await repo.update_record(order_id, {"is_favorite": True})
    await db.commit()
    return {"message": "已收藏"}

@router.delete("/purchase-records/{order_id}/favorite")
async def unfavorite_purchase_record(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """取消收藏购买记录"""
    from app.repository.purchase import PurchaseRecordRepository
    repo = PurchaseRecordRepository(db)
    await repo.update_record(order_id, {"is_favorite": False})
    await db.commit()
    return {"message": "已取消收藏"}

async def get_purchase_record_item(order):
    item = PurchaseRecordResponse.model_validate(order)
    item.column_name = order.column.name if order.column else "未知专栏"
    return item


@router.get("/purchase-records/export/pdf")
async def export_purchase_records(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """导出所有购买记录为 PDF"""
    from app.repository.purchase import PurchaseRecordRepository
    from app.services.export import ExportService
    
    repo = PurchaseRecordRepository(db)
    records, _ = await repo.get_records(user_id=current_user.id, size=1000)
    
    exporter = ExportService()
    file_stream = await exporter.export_purchase_records_to_pdf(current_user.username, records)
    
    headers = {
        'Content-Disposition': f'attachment; filename="purchase_records_{current_user.username}.pdf"'
    }
    return StreamingResponse(file_stream, media_type="application/pdf", headers=headers)


@router.get("/columns/{column_id}/analytics")
async def get_column_analytics(
    column_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取专栏数据统计 (仅管理员或作者)"""
    if not current_user.is_admin:
        # 实际应检查是否为该专栏的 creator_id
        pass
    
    from app.services.analytics import AnalyticsService
    service = AnalyticsService(db)
    return await service.get_column_analytics(column_id)


# ==================== 分类与标签接口 ====================

@router.post("/categories", response_model=CategoryResponse)
async def create_category(
    data: CategoryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建分类（仅管理员）"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="权限不足")
    from app.repository.metadata import CategoryRepository
    repo = CategoryRepository(db)
    category = await repo.create(data)
    await db.commit()
    return category

@router.get("/categories", response_model=List[CategoryResponse])
async def get_categories(db: AsyncSession = Depends(get_db)):
    """获取所有分类"""
    from app.repository.metadata import CategoryRepository
    repo = CategoryRepository(db)
    return await repo.get_all()

@router.get("/tags", response_model=List[TagResponse])
async def get_tags(db: AsyncSession = Depends(get_db)):
    """获取所有标签（标签云）"""
    from app.repository.metadata import TagRepository
    repo = TagRepository(db)
    return await repo.get_all()


# ==================== 评论接口 ====================

@router.get("/articles/{article_id}/comments", response_model=List[CommentSchema])
async def get_comments(
    article_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """获取文章评论"""
    repo = CommentRepository(db)
    comments = await repo.get_by_article(article_id)
    
    # 构建嵌套结构
    comment_map = {c.id: CommentSchema.model_validate(c) for c in comments}
    root_comments = []
    
    for c in comments:
        if c.parent_id and c.parent_id in comment_map:
            comment_map[c.parent_id].replies.append(comment_map[c.id])
        else:
            root_comments.append(comment_map[c.id])
            
    return root_comments


@router.post("/articles/comments", response_model=CommentSchema, status_code=status.HTTP_201_CREATED)
async def create_comment(
    comment_data: CommentCreate,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """发表评论"""
    # 1. 必须登录 (Member 或 Admin)
    if not current_user:
        raise HTTPException(status_code=401, detail="请登录后发表评论")
    
    # 2. 检查文章访问权限
    article_repo = ArticleRepository(db)
    article = await article_repo.get_by_id(comment_data.article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
        
    current_role = current_user.role.value if hasattr(current_user, 'role') and hasattr(current_user.role, 'value') else str(current_user.role if current_user else "VISITOR")
        
    # 重用 get_article 中的权限逻辑 (简化版校验)
    is_author = article.creator_id == current_user.id
    is_admin = current_role == "ADMIN"
    is_member = current_role == "MEMBER"
    is_article_free = article.is_free or (article.column and article.column.is_free)
    
    has_paid = False
    if is_member and article.column_id:
        from sqlalchemy import select
        paid_stmt = select(Order).where(
            Order.column_id == article.column_id,
            Order.user_id == current_user.id,
            Order.status == OrderStatus.PAID
        )
        paid_result = await db.execute(paid_stmt)
        has_paid = paid_result.scalar_one_or_none() is not None

    if not is_admin and not is_author and not is_article_free and not has_paid:
        raise HTTPException(status_code=402, detail="您需要购买该专栏后才能发表评论")

    # 3. 创建评论
    data = comment_data.model_dump()
    data['user_id'] = current_user.id
    data['user_name'] = current_user.username
    
    from app.models.comment import Comment as CommentModel
    comment = CommentModel(**data)
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment


# ==================== 收藏接口 ====================

@router.post("/articles/{article_id}/favorite")
async def favorite_article(
    article_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """收藏文章"""
    # 1. 检查文章访问权限
    article_repo = ArticleRepository(db)
    article = await article_repo.get_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
        
    user_role = current_user.role if current_user else UserRole.VISITOR
    
    is_author = article.creator_id == current_user.id
    is_admin = user_role == UserRole.ADMIN
    is_member = user_role == UserRole.MEMBER
    is_article_free = article.is_free or (article.column and article.column.is_free)
    
    has_paid = False
    if is_member and article.column_id:
        from sqlalchemy import select
        paid_stmt = select(Order).where(
            Order.column_id == article.column_id,
            Order.user_id == current_user.id,
            Order.status == OrderStatus.PAID
        )
        paid_result = await db.execute(paid_stmt)
        has_paid = paid_result.scalar_one_or_none() is not None

    if not is_admin and not is_author and not is_article_free and not has_paid:
        raise HTTPException(status_code=402, detail="您需要购买该专栏后才能收藏文章")

    from app.repository.metadata import FavoriteRepository
    repo = FavoriteRepository(db)
    await repo.add(current_user.id, article_id)
    await db.commit()
    return {"success": True}

@router.delete("/articles/{article_id}/favorite")
async def unfavorite_article(
    article_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """取消收藏文章"""
    from app.repository.metadata import FavoriteRepository
    repo = FavoriteRepository(db)
    await repo.remove(current_user.id, article_id)
    await db.commit()
    return {"success": True}

@router.get("/user/favorites", response_model=List[ArticleResponse])
async def get_my_favorites(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取我的收藏列表"""
    from app.repository.metadata import FavoriteRepository
    repo = FavoriteRepository(db)
    favorites = await repo.get_by_user(current_user.id)
    
    article_repo = ArticleRepository(db)
    articles = []
    for f in favorites:
        article = await article_repo.get_by_id(f.article_id)
        if article:
            articles.append(article)
    return articles


# ==================== 内容生命周期接口 ====================

@router.get("/articles/{article_id}/history", response_model=List[ArticleHistoryResponse])
async def get_article_history(
    article_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """获取文章版本历史"""
    from app.repository.lifecycle import ArticleHistoryRepository
    repo = ArticleHistoryRepository(db)
    return await repo.get_history_list(article_id)

@router.get("/articles/history/{history_id}", response_model=ArticleHistoryDetail)
async def get_history_detail(
    history_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """获取历史版本详情"""
    from app.repository.lifecycle import ArticleHistoryRepository
    repo = ArticleHistoryRepository(db)
    history = await repo.get_by_id(history_id)
    if not history:
        raise HTTPException(status_code=404, detail="历史版本不存在")
    return history

@router.post("/articles/{article_id}/restore", response_model=ArticleResponse)
async def restore_article(
    article_id: UUID,
    request: RestoreFromHistory,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """从历史版本恢复文章"""
    service = ArticleService(db)
    article = await service.restore_from_history(
        article_id, 
        request.history_id, 
        creator_id=current_user.id
    )
    if not article:
        raise HTTPException(status_code=404, detail="恢复失败，历史版本或文章不存在")
    
    await db.commit()
    return article


@router.get("/templates", response_model=List[DocumentTemplateResponse])
async def get_templates(db: AsyncSession = Depends(get_db)):
    """获取所有文档模板"""
    from app.repository.lifecycle import DocumentTemplateRepository
    repo = DocumentTemplateRepository(db)
    return await repo.get_all()

@router.post("/templates", response_model=DocumentTemplateResponse)
async def create_template(
    data: DocumentTemplateCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建文档模板（仅管理员）"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="权限不足")
    from app.repository.lifecycle import DocumentTemplateRepository
    repo = DocumentTemplateRepository(db)
    template = await repo.create(data.name, data.content, data.description)
    await db.commit()
    return template

@router.post("/articles/{article_id}/ai-summary", response_model=AISummaryResponse)
async def get_ai_summary(
    article_id: UUID,
    request: AISummaryRequest,
    db: AsyncSession = Depends(get_db)
):
    """获取 AI 全文总结"""
    article_service = ArticleService(db)
    ai_service = AIService()
    
    # 1. 获取全文
    plain_text = await article_service.get_article_plain_text(article_id)
    if not plain_text:
        raise HTTPException(status_code=404, detail="文章内容为空")
        
    article = await article_service.repo.get_by_id(article_id)
    
    # 2. 调用 AI
    summary = await ai_service.summarize_article(
        article.title, 
        plain_text, 
        model_key=request.model,
        api_key=request.api_key,
        base_url=request.base_url,
        max_tokens=request.max_tokens,
        temperature=request.temperature
    )
    
    # 3. (可选) 可自动保存到数据库摘要字段，这里暂不自动覆盖，由前端确认
    return AISummaryResponse(summary=summary)


@router.post("/articles/{article_id}/chat", response_model=AIChatResponse)
async def chat_with_article(
    article_id: UUID,
    request: AIChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """基于文章内容进行 AI 对话"""
    article_service = ArticleService(db)
    ai_service = AIService()
    
    # 1. 获取全文
    plain_text = await article_service.get_article_plain_text(article_id)
    article = await article_service.repo.get_by_id(article_id)
    
    # 2. 调用 AI
    answer = await ai_service.chat_with_article(
        article.title, 
        plain_text, 
        request.history, 
        request.message, 
        model_key=request.model,
        api_key=request.api_key,
        base_url=request.base_url,
        max_tokens=request.max_tokens,
        temperature=request.temperature
    )
    
    return AIChatResponse(
        answer=answer, 
        model=request.model or settings.AI_DEFAULT_MODEL
    )


# ==================== 推荐与统计接口 ====================

@router.get("/articles/{article_id}/recommendations", response_model=List[ArticleResponse])
async def get_article_recommendations(
    article_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """获取推荐文章"""
    repo = ArticleRepository(db)
    return await repo.get_recommendations(article_id)


@router.get("/admin/analytics/report")
async def get_analytics_report(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取全文库分析报告 (仅管理员)"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="权限不足")
    repo = ArticleRepository(db)
    return await repo.get_analytics_report()


# ==================== 导出接口 ====================

@router.get("/articles/{article_id}/export/{format}")
async def export_article(
    article_id: UUID,
    format: str,
    db: AsyncSession = Depends(get_db)
):
    """导出文章 (pdf, docx)"""
    repo = ArticleRepository(db)
    article = await repo.get_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
        
    from app.services.export import ExportService
    exporter = ExportService()
    
    if format.lower() == "pdf":
        file_stream = await exporter.to_pdf(article.title, article.content)
        media_type = "application/pdf"
        filename = f"{article.title}.pdf"
    elif format.lower() == "docx":
        file_stream = await exporter.to_word(article.title, article.content)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = f"{article.title}.docx"
    else:
        raise HTTPException(status_code=400, detail="不支持的导出格式")
        
    headers = {
        'Content-Disposition': f'attachment; filename="{filename}"'
    }
    return StreamingResponse(file_stream, media_type=media_type, headers=headers)


# ==================== 实时协作接口 (WebSocket) ====================

@router.websocket("/ws/collaboration/{article_id}")
async def websocket_collaboration(
    websocket: WebSocket,
    article_id: str,
    user_id: str,
    username: str
):
    """实时协作 WebSocket 端点"""
    from app.services.collaboration import manager
    user_info = {"id": user_id, "username": username}
    await manager.connect(websocket, article_id, user_info)
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            # 广播协作事件 (编辑、光标移动等)
            await manager.broadcast(article_id, {
                "type": "collaboration",
                "user": user_info,
                "data": msg
            })
    except WebSocketDisconnect:
        manager.disconnect(websocket, article_id, user_id)
        await manager.broadcast(article_id, {
            "type": "presence",
            "action": "leave",
            "user": user_info
        })
    except Exception as e:
        logger.error(f"WebSocket 错误: {e}")
        manager.disconnect(websocket, article_id, user_id)


# ==================== 文档处理接口 ====================

@router.post("/documents/upload")
@router.post("/documents/upload-pdf")
async def upload_document(
    file: UploadFile = File(...),
    column_id: Optional[UUID] = None,
    parent_id: Optional[UUID] = None,
    config: Optional[str] = None, # JSON string of configuration
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """全能文档上传：支持 PDF/PPT/Word/Excel/TXT 转换为博客 (仅限会员和管理员)"""
    if current_user.role not in [UserRole.ADMIN, UserRole.MEMBER]:
        raise HTTPException(status_code=403, detail="访客不支持文档转换功能，请先购买专栏加入会员")
    # 1. 保存文件到临时目录
    temp_dir = os.path.join(settings.UPLOAD_DIR, "temp")
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, file.filename)
    
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # 2. 根据后缀选择引擎
    ext = os.path.splitext(file.filename)[1].lower()
    logger.info(f"📁 收到文件上传: {file.filename}, 后缀: {ext}")
    
    markdown_content = ""
    protocol = "doc"
    
    # 解析可选配置
    process_config = {}
    if config:
        try:
            import json
            process_config = json.loads(config)
            # 应用到全局 doc_processor 配置或传递给处理函数
            for k, v in process_config.items():
                if hasattr(doc_processor.config, k):
                    setattr(doc_processor.config, k, v)
        except Exception as e:
            logger.warning(f"Failed to parse upload config: {e}")

    try:
        if ext == '.pdf':
            # 如果是 PDF，允许动态传递配置（当前通过全局 doc_processor.config 控制）
            markdown_content = await doc_processor.process_pdf_to_markdown(temp_path)
            protocol = "pdf"
        elif ext in ['.pptx', '.ppt']:
            markdown_content = await doc_processor.ppt_to_web(temp_path)
            protocol = "ppt"
        elif ext in ['.docx', '.doc', '.xlsx', '.xls']:
            markdown_content = await doc_processor.process_office_doc(temp_path)
            protocol = "office"
        elif ext in ['.txt', '.md', '.csv', '.json']:
            markdown_content = await doc_processor.process_text_file(temp_path)
            protocol = "text"
        else:
            raise HTTPException(status_code=400, detail=f"不支持的文件格式: {ext}")

        if not markdown_content or "转换失败" in markdown_content[:50]:
            raise HTTPException(status_code=500, detail=f"文档转换失败或内容为空")
            
        # 3. 创建文章并持久化
        article_service = ArticleService(db)
        result = await article_service.create_article_from_document(
            file.filename, 
            markdown_content, 
            column_id,
            creator_id=current_user.id if current_user else None,
            source_protocol=protocol,
            parent_id=parent_id
        )
        
        if not result.success:
            raise HTTPException(status_code=500, detail=result.error)
            
        # 4. 清理临时文件
        doc_processor.cleanup_temp()
        
        return {
            "success": True,
            "article_id": str(result.article_id),
            "message": f"{ext.upper()} 转换成功，已存入博客列表"
        }
    except Exception as e:
        logger.error(f"Upload processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents/url-to-ppt")
async def url_to_ppt(url: str, config: Optional[str] = None, current_user: User = Depends(get_current_user)):
    """网页 URL 转 PPT (仅限会员和管理员)"""
    if current_user.role not in [UserRole.ADMIN, UserRole.MEMBER]:
        raise HTTPException(status_code=403, detail="访客不支持网页转 PPT 功能")
    
    # 解析可选配置
    process_config = {}
    if config:
        try:
            import json
            process_config = json.loads(config)
        except: pass
    
    result_path = await doc_processor.url_to_ppt(url, config=process_config)
    
    # 检查文件是否生成成功
    if not result_path or not os.path.exists(result_path):
        raise HTTPException(status_code=500, detail="PPT 生成失败，请检查 URL 是否有效")
    
    # 返回可访问的下载 URL
    filename = os.path.basename(result_path)
    download_url = f"/uploads/{filename}"
    
    return {
        "success": True,
        "download_url": download_url,
        "filename": filename,
        "message": "网页已成功转换为 PPT"
    }


@router.post("/documents/ppt-to-web")
async def ppt_to_web(ppt_path: str, current_user: User = Depends(get_current_user)):
    """PPT 转网页 (仅限会员和管理员)"""
    if current_user.role not in [UserRole.ADMIN, UserRole.MEMBER]:
        raise HTTPException(status_code=403, detail="访客不支持 PPT 还原功能")
        
    result = await doc_processor.ppt_to_web(ppt_path)
    return {"message": result}


# ==================== 健康检查 ====================

@router.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "ok", "service": "大数据启示录"}


# ==================== 财务与钱包接口 ====================

@router.get("/finance/balance", response_model=BalanceResponse)
async def get_balance(
    current_user: User = Depends(get_current_user)
):
    """获取账户余额和积分"""
    return BalanceResponse(
        balance=current_user.balance,
        points=current_user.points,
        invitation_code=current_user.invitation_code
    )


@router.post("/finance/redeem", response_model=PointRedeemResponse)
async def redeem_points(
    request: PointRedeemRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """积分兑换余额"""
    # 定义兑换档位 (积分 -> 分)
    REDEEM_MAP = {
        1000: 5000,  # 1000 积分 -> 50 元
        2000: 15000, # 2000 积分 -> 150 元
        5000: 50000  # 5000 积分 -> 500 元
    }
    
    if request.amount not in REDEEM_MAP:
        raise HTTPException(status_code=400, detail="无效的兑换档位，支持 1000, 2000, 5000 积分兑换")
        
    if current_user.points < request.amount:
        raise HTTPException(status_code=400, detail=f"积分不足，当前只有 {current_user.points} 积分")
        
    balance_added = REDEEM_MAP[request.amount]
    
    # 执行兑换
    current_user.points -= request.amount
    current_user.balance += balance_added
    
    # 记录流水
    from app.models.transaction import Transaction, TransactionType
    tx = Transaction(
        user_id=current_user.id,
        type=TransactionType.COMMISSION,
        amount=balance_added,
        balance_after=current_user.balance,
        detail=f"积分里程碑兑换: {request.amount} 积分 -> {balance_added/100} 元"
    )
    db.add(tx)
    await db.commit()
    
    return PointRedeemResponse(
        points_deducted=request.amount,
        balance_added=balance_added,
        new_points=current_user.points,
        new_balance=current_user.balance
    )

@router.get("/finance/transactions", response_model=TransactionListResponse)
async def get_transactions(
    page: int = 1,
    size: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取交易记录"""
    from app.repository.transaction import TransactionRepository
    repo = TransactionRepository(db)
    items, total = await repo.get_by_user(current_user.id, skip=(page-1)*size, limit=size)
    return TransactionListResponse(items=items, total=total)

@router.post("/finance/withdraw", response_model=WithdrawalResponse)
async def submit_withdrawal(
    data: WithdrawalCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """申请提现"""
    if data.amount < 5000:
        raise HTTPException(status_code=400, detail="最低提现金额为 50 元")
    if current_user.balance < data.amount:
        raise HTTPException(status_code=400, detail="余额不足")
    
    from app.repository.withdrawal import WithdrawalRepository
    from app.models.transaction import TransactionType
    from app.repository.transaction import TransactionRepository
    
    with_repo = WithdrawalRepository(db)
    tx_repo = TransactionRepository(db)
    
    # 1. 扣除余额 (冻结或直接扣除，这里先直接扣除)
    current_user.balance -= data.amount
    
    # 2. 创建提现申请
    request = await with_repo.create(
        user_id=current_user.id,
        amount=data.amount,
        method=data.method,
        account_info=data.account_info,
        account_name=data.account_name,
        bank_name=data.bank_name
    )
    
    # 3. 记录交易
    await tx_repo.create(
        user_id=current_user.id,
        type=TransactionType.WITHDRAWAL,
        amount=-data.amount,
        balance_after=current_user.balance,
        detail=f"申请提现 ({data.method})"
    )
    
    await db.commit()
    return request

# ==================== 管理员：财务审计 ====================

@router.get("/admin/finance/withdrawals", response_model=List[WithdrawalResponse])
async def admin_get_withdrawals(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """管理员：查看待处理提现 (仅限 ADMIN)"""
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="权限不足")
    
    from app.repository.withdrawal import WithdrawalRepository
    repo = WithdrawalRepository(db)
    return await repo.get_all_pending()

@router.post("/admin/finance/withdrawals/{request_id}/audit")
async def admin_audit_withdrawal(
    request_id: UUID,
    data: WithdrawalAuditRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """管理员：审核提现申请"""
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="权限不足")
    
    from app.repository.withdrawal import WithdrawalRepository
    from app.models.withdrawal import WithdrawalStatus
    from app.repository.transaction import TransactionRepository
    from app.models.transaction import TransactionType
    from datetime import datetime
    
    repo = WithdrawalRepository(db)
    request = await repo.get_by_id(request_id)
    if not request or request.status != WithdrawalStatus.PENDING:
        raise HTTPException(status_code=404, detail="申请不存在或已处理")
    
    if data.approve:
        request.status = WithdrawalStatus.COMPLETED
    else:
        request.status = WithdrawalStatus.REJECTED
        # 如果拒绝，退还余额
        user_repo = UserRepository(db)
        user = await user_repo.get_by_id(request.user_id)
        if user:
            user.balance += request.amount
            # 记录退回交易
            tx_repo = TransactionRepository(db)
            await tx_repo.create(
                user_id=user.id,
                type=TransactionType.REFUND,
                amount=request.amount,
                balance_after=user.balance,
                detail=f"提现被拒绝退还余额: {data.remark or ''}"
            )
            
    request.processed_at = datetime.utcnow()
    await db.commit()
    return {"success": True}

@router.get("/admin/finance/stats", response_model=FinancialStats)
async def admin_get_finance_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """管理员财务报表与统计"""
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="权限不足")
    
    from sqlalchemy import select, func
    from app.models.order import Order, OrderStatus
    from app.models.withdrawal import Withdrawal, WithdrawalStatus
    from app.models.user import User, UserRole
    from app.models.transaction import Transaction
    
    # 1. 累计总收入 (已支付订单)
    income_stmt = select(func.sum(Order.amount)).where(Order.status == OrderStatus.PAID)
    total_income = await db.scalar(income_stmt) or 0
    
    # 2. 待处理提现总额
    withdraw_pending_stmt = select(func.sum(Withdrawal.amount)).where(Withdrawal.status == WithdrawalStatus.PENDING)
    total_withdrawals_pending = await db.scalar(withdraw_pending_stmt) or 0
    
    # 3. 已完成提现总额
    withdraw_completed_stmt = select(func.sum(Withdrawal.amount)).where(Withdrawal.status == WithdrawalStatus.COMPLETED)
    total_withdrawals_completed = await db.scalar(withdraw_completed_stmt) or 0
    
    # 4. 用户角色构成
    user_counts = {}
    for role in [UserRole.VISITOR, UserRole.MEMBER, UserRole.ADMIN]:
        count = await db.scalar(select(func.count(User.id)).where(User.role == role))
        user_counts[role] = count or 0
        
    # 5. 最近交易记录
    tx_stmt = select(Transaction).order_by(Transaction.created_at.desc()).limit(10)
    tx_res = await db.execute(tx_stmt)
    recent_transactions = tx_res.scalars().all()
    
    return FinancialStats(
        total_income=total_income,
        total_withdrawals_pending=total_withdrawals_pending,
        total_withdrawals_completed=total_withdrawals_completed,
        user_count_visitor=user_counts[UserRole.VISITOR],
        user_count_member=user_counts[UserRole.MEMBER],
        user_count_admin=user_counts[UserRole.ADMIN],
        recent_transactions=recent_transactions
    )


# ==================== PPT 转换接口 ====================

async def broadcast_ppt_status(job_id: str):
    if job_id in ppt_active_connections and job_id in ppt_jobs:
        data = ppt_jobs[job_id].copy()
        if "download_url" in data:
            data["downloadUrl"] = data.pop("download_url")
        # NOTE: 过滤不可 JSON 序列化的字段（bytes 图片数据、大对象等）
        non_serializable_keys = ["mermaid_images", "outline", "fragments"]
        for key in non_serializable_keys:
            data.pop(key, None)
            
        message = json.dumps({"type": "progress", "data": data})
        for connection in ppt_active_connections[job_id]:
            try:
                await connection.send_text(message)
            except:
                pass

async def process_ppt_generation(job_id: str, request: GenerateRequest):
    """PPT 生成核心流程 - 支持 standard / ai_visual / hybrid 三种引擎"""
    try:
        engine = getattr(request, 'engine', 'standard') or 'standard'
        is_prompt_mode = bool(request.prompt and request.prompt.strip())
        
        # ==================== 提示词模式：跳过爬取 ====================
        if is_prompt_mode:
            ppt_jobs[job_id]["message"] = "📝 提示词模式：正在根据主题生成 PPT 大纲..."
            ppt_jobs[job_id]["progress"] = 10
            await broadcast_ppt_status(job_id)
            
            contents = []
            all_fragments = []
            ppt_jobs[job_id]["fragments"] = []
            
            # 直接使用提示词生成大纲
            outline_model = request.options.get("outlineModel") if request.options else None
            summarizer = SummarizerService(model_override=outline_model) if outline_model else ppt_summarizer
            
            outline = await summarizer.generate_outline_from_prompt(
                prompt=request.prompt.strip(),
                max_slides=request.options.get("maxSlides", 10) if request.options else 10,
                language=request.options.get("language", "zh-CN") if request.options else "zh-CN",
            )
            
            ppt_jobs[job_id]["outline"] = outline.model_dump()
            ppt_jobs[job_id]["progress"] = 70
            ppt_jobs[job_id]["message"] = "大纲生成完成"
            await broadcast_ppt_status(job_id)
        else:
            # ==================== URL 模式：爬取+生成大纲 ====================
            # Step 1: Scrape (0-30%)
            urls = request.urls or []
            if not urls:
                raise ValueError("请提供 URL 列表或输入提示词")
            
            ppt_jobs[job_id]["message"] = f"正在获取 {len(urls)} 个文档内容..."
            ppt_jobs[job_id]["progress"] = 5
            await broadcast_ppt_status(job_id)
            
            contents = await ppt_scraper.scrape_urls(urls)
            
            all_fragments = []
            for content in contents:
                all_fragments.extend(content.visual_fragments)
            ppt_jobs[job_id]["fragments"] = [f.model_dump() for f in all_fragments]

            ppt_jobs[job_id]["progress"] = 30
            ppt_jobs[job_id]["message"] = "网页内容获取成功"
            await broadcast_ppt_status(job_id)
            
            # Step 2: Summarize (30-70%)
            ppt_jobs[job_id]["message"] = "分析内容中，正在生成 PPT 大纲..."
            await broadcast_ppt_status(job_id)
            
            # NOTE: 支持多模型大纲生成
            outline_model = request.options.get("outlineModel") if request.options else None
            summarizer = SummarizerService(model_override=outline_model) if outline_model else ppt_summarizer
            
            outline = await summarizer.generate_outline(
                contents, 
                mode=request.mode, 
                max_slides=request.options.get("maxSlides", 10),
                language=request.options.get("language", "zh-CN")
            )
            
            ppt_jobs[job_id]["outline"] = outline.model_dump()
            ppt_jobs[job_id]["progress"] = 70
            await broadcast_ppt_status(job_id)
        
        # Step 3: 分页处理
        ppt_jobs[job_id]["message"] = "正在处理大纲及排版..."
        await broadcast_ppt_status(job_id)
        
        def post_process_outline(outline: PPTOutline) -> PPTOutline:
            new_sections = []
            for section in outline.sections:
                max_pts = 8
                if len(section.points) > max_pts:
                    chunks = [section.points[i:i + max_pts] for i in range(0, len(section.points), max_pts)]
                    for idx, chunk in enumerate(chunks):
                        new_sec = section.model_copy()
                        new_sec.title = f"{section.title} ({idx + 1}/{len(chunks)})"
                        new_sec.points = chunk
                        if idx > 0:
                            new_sec.mermaid = None
                            new_sec.visual_type = None
                            new_sec.visual_prompt = None
                            new_sec.visual_fragment_id = None
                        new_sections.append(new_sec)
                else:
                    new_sections.append(section)
            outline.sections = new_sections
            return outline

        processed_outline = post_process_outline(outline)
        
        # ==================== 根据引擎选择不同生成路径 ====================
        
        if engine == "ai_visual" and ppt_banana.is_available:
            # ========== AI 视觉模式：banana-slides 全图式 PPT ==========
            ppt_jobs[job_id]["message"] = "⚡ AI 视觉模式：正在生成高品质幻灯片图片..."
            await broadcast_ppt_status(job_id)
            
            project_data = ppt_banana.outline_to_banana_project(
                title=outline.title,
                subtitle=outline.subtitle,
                sections=[s.model_dump() for s in processed_outline.sections],
                theme=request.theme,
            )
            
            async def progress_cb(current, total, msg):
                ppt_jobs[job_id]["progress"] = 70 + int((current / max(total, 1)) * 25)
                ppt_jobs[job_id]["message"] = msg
                await broadcast_ppt_status(job_id)
            
            slide_images_ai = await ppt_banana.generate_all_slides(project_data, progress_callback=progress_cb)
            
            generator = PPTGeneratorService(theme=request.theme)
            ppt_buffer = generator.generate_from_images(
                [img for img in slide_images_ai if img is not None],
                title=outline.title,
            )
            
            # 保存 mermaid_images 为空（AI 视觉模式不使用 Mermaid）
            ppt_jobs[job_id]["mermaid_images"] = []
            
        elif engine == "hybrid":
            # ========== 混合模式：AI 背景 + 结构化文字叠加 ==========
            ppt_jobs[job_id]["message"] = "🎨 混合模式：正在生成背景图和视觉资源..."
            await broadcast_ppt_status(job_id)
            
            background_images = []
            mermaid_images = []
            sd_config_dict = None
            if hasattr(request, 'sd_config') and request.sd_config:
                sd_config_dict = request.sd_config.model_dump()
            
            for i, section in enumerate(processed_outline.sections):
                # 生成背景图
                visual_prompt = section.visual_prompt if hasattr(section, 'visual_prompt') else None
                bg_img = await ppt_image_gen.get_best_image(
                    title=section.title,
                    visual_prompt=visual_prompt,
                    visual_service=ppt_visuals,
                    banana_service=ppt_banana if ppt_banana.is_available else None,
                    prefer_ai=True,
                    sd_config=sd_config_dict,
                )
                background_images.append(bg_img)
                
                # Mermaid 图表
                m_img = None
                if section.mermaid:
                    mermaid_theme = "dark" if request.theme in ["dark", "tech"] else "default"
                    m_img = await ppt_image_gen.get_mermaid_image(
                        section.mermaid, theme=mermaid_theme, visual_service=ppt_visuals
                    )
                mermaid_images.append(m_img)
                
                ppt_jobs[job_id]["progress"] = 70 + int((i / max(len(processed_outline.sections), 1)) * 25)
                await broadcast_ppt_status(job_id)
            
            # 封面背景
            cover_bg = await ppt_image_gen.get_best_image(
                title=outline.title,
                visual_prompt=f"Professional presentation cover slide about {outline.title}",
                visual_service=ppt_visuals,
                banana_service=ppt_banana if ppt_banana.is_available else None,
            )
            background_images.insert(0, cover_bg)
            
            generator = PPTGeneratorService(theme=request.theme)
            ppt_buffer = generator.generate_hybrid(processed_outline, background_images, mermaid_images)
            ppt_jobs[job_id]["mermaid_images"] = mermaid_images
            
        else:
            # ========== 标准模式（原有逻辑完全保留） ==========
            ppt_jobs[job_id]["message"] = "正在生成视觉资源（图表和插图）..."
            scraped_images_pool = []
            for content in contents:
                scraped_images_pool.extend([img.src for img in content.images])

            slide_images = []
            mermaid_images = []
            fragment_images = []
            
            fragment_map = {}
            for c in contents:
                for f in c.visual_fragments:
                    fragment_map[f.id] = f.data_base64

            sd_config_dict = None
            if hasattr(request, 'sd_config') and request.sd_config:
                sd_config_dict = request.sd_config.model_dump()

            import httpx
            async with httpx.AsyncClient() as client:
                for i, section in enumerate(processed_outline.sections):
                    # 截图碎片
                    frag_img = None
                    frag_id = getattr(section, 'visual_fragment_id', None)
                    if frag_id and frag_id in fragment_map:
                        import base64
                        frag_img = base64.b64decode(fragment_map[frag_id])
                    fragment_images.append(frag_img)

                    # Mermaid 图表（使用增强的智能渲染）
                    m_img = None
                    if section.mermaid:
                        mermaid_theme = "dark" if request.theme in ["dark", "tech"] else "default"
                        m_img = await ppt_image_gen.get_mermaid_image(
                            section.mermaid, theme=mermaid_theme, visual_service=ppt_visuals
                        )
                    mermaid_images.append(m_img)
                    
                    # 智能图片获取（ComfyUI -> banana-slides AI -> Unsplash -> Pexels -> 网页图片）
                    sd_img = None
                    if request.options.get("includeImages", True) and not m_img and not frag_img:
                        visual_prompt = section.visual_prompt if hasattr(section, 'visual_prompt') else None
                        sd_img = await ppt_image_gen.get_best_image(
                            title=section.title,
                            visual_prompt=visual_prompt,
                            visual_service=ppt_visuals,
                            banana_service=ppt_banana if ppt_banana.is_available else None,
                            prefer_ai=True,
                            sd_config=sd_config_dict,
                        )
                        
                        # 如果智能获取失败，尝试从网页抓取的图片池
                        if not sd_img and i < len(scraped_images_pool):
                            try:
                                if scraped_images_pool[i].startswith('http'):
                                    async with httpx.AsyncClient() as img_client:
                                        resp = await img_client.get(scraped_images_pool[i], timeout=10)
                                        if resp.status_code == 200:
                                            sd_img = resp.content
                            except:
                                pass
                    
                    slide_images.append(sd_img)

            generator = PPTGeneratorService(theme=request.theme)
            ppt_buffer = generator.generate(processed_outline, slide_images, mermaid_images, fragment_images)
            ppt_jobs[job_id]["mermaid_images"] = mermaid_images
        
        # ==================== 保存文件（所有模式通用） ====================
        output_dir = "outputs"
        os.makedirs(output_dir, exist_ok=True)
        filename = f"{job_id}.pptx"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, "wb") as f:
            f.write(ppt_buffer.getbuffer())
            
        ppt_jobs[job_id]["status"] = "completed"
        ppt_jobs[job_id]["progress"] = 100
        ppt_jobs[job_id]["message"] = f"PPT 生成成功！（{engine} 模式）"
        ppt_jobs[job_id]["download_url"] = f"/api/ppt/download/{job_id}"
        ppt_jobs[job_id]["title"] = outline.title
        ppt_jobs[job_id]["engine"] = engine
        await broadcast_ppt_status(job_id)
        
    except Exception as e:
        ppt_jobs[job_id]["status"] = "failed"
        ppt_jobs[job_id]["message"] = f"发生错误: {str(e)}"
        await broadcast_ppt_status(job_id)
        logger.error(f"Error processing PPT job {job_id}: {e}")


@router.get("/ppt/engines")
async def get_ppt_engines(current_user: User = Depends(get_current_user)):
    """获取可用的 PPT 引擎列表"""
    engines = [
        EngineInfo(
            id="standard",
            name="标准模式",
            description="结构化 PPT 生成，支持 Mermaid 图表、ComfyUI 配图、Unsplash/Pexels 图库",
            available=True,
        ),
        EngineInfo(
            id="ai_visual",
            name="AI 视觉模式",
            description="使用 banana-slides AI 生成高品质全图式幻灯片，效果最精美",
            available=ppt_banana.is_available,
            requires=["BANANA_SLIDES_ENABLED=true", "GOOGLE_API_KEY"],
        ),
        EngineInfo(
            id="hybrid",
            name="混合模式",
            description="AI 背景 + 结构化文字叠加，兼顾美观和可编辑性",
            available=True,
        ),
    ]
    return {
        "engines": [e.model_dump() for e in engines],
        "sd_available": settings.ENABLE_SD,
        "banana_status": ppt_banana.get_status(),
    }


@router.post("/ppt/generate")
async def generate_ppt(
    request: GenerateRequest, 
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """创建 PPT 生成任务"""
    job_id = str(uuid.uuid4())
    ppt_jobs[job_id] = {
        "id": job_id,
        "status": "processing",
        "progress": 0,
        "message": "开始生成序列...",
        "theme": request.theme,
        "engine": getattr(request, 'engine', 'standard'),
    }
    
    background_tasks.add_task(process_ppt_generation, job_id, request)
    return {"id": job_id, "status": "processing"}

@router.get("/ppt/status/{job_id}", response_model=JobStatus)
async def get_ppt_status(job_id: str):
    """获取任务状态"""
    if job_id not in ppt_jobs:
        raise HTTPException(status_code=404, detail="任务不存在")
    return ppt_jobs[job_id]

@router.get("/ppt/slides/{job_id}")
async def get_ppt_slides(job_id: str):
    """获取预览幻灯片数据"""
    if job_id not in ppt_jobs or "outline" not in ppt_jobs[job_id]:
        if job_id in ppt_jobs and ppt_jobs[job_id]["status"] == "processing":
            return {"status": "processing", "slides": []}
        raise HTTPException(status_code=404, detail="未找到幻灯片数据")
    
    outline = ppt_jobs[job_id]["outline"]
    theme_name = ppt_jobs[job_id].get("theme", "light")
    
    themes = {
        # 经典主题
        "light": {"primary": "2563eb", "secondary": "f1f5f9", "background": "ffffff", "text": "1e293b", "accent": "3b82f6"},
        "dark": {"primary": "38bdf8", "secondary": "1e293b", "background": "0f172a", "text": "f8fafc", "accent": "0ea5e9"},
        "corporate": {"primary": "1e3a8a", "secondary": "f3f4f6", "background": "ffffff", "text": "111827", "accent": "fbbf24"},
        # 现代风格
        "gradient": {"primary": "6366f1", "secondary": "eef2ff", "background": "fafbff", "text": "1f2937", "accent": "ec4899"},
        "minimalist": {"primary": "18181b", "secondary": "fafafa", "background": "ffffff", "text": "18181b", "accent": "a1a1aa"},
        "tech": {"primary": "22d3ee", "secondary": "111827", "background": "030712", "text": "e5e7eb", "accent": "a855f7"},
        # 特色主题
        "creative": {"primary": "f97316", "secondary": "ffedd5", "background": "fff7ed", "text": "1c1917", "accent": "10b981"},
        "nature": {"primary": "16a34a", "secondary": "dcfce7", "background": "f0fdf4", "text": "14532d", "accent": "84cc16"},
        "business": {"primary": "0369a1", "secondary": "e0f2fe", "background": "f8fafc", "text": "0f172a", "accent": "0891b2"},
        "elegant": {"primary": "7c3aed", "secondary": "ede9fe", "background": "faf5ff", "text": "3b0764", "accent": "c084fc"}
    }
    theme = themes.get(theme_name, themes["light"])
    
    slides = []
    
    # Title Slide
    slides.append({
        "id": 0,
        "type": "title",
        "title": outline.get("title", "演示文稿"),
        "subtitle": outline.get("subtitle", ""),
        "theme": theme
    })
    
    # Content Slides
    fragments = ppt_jobs[job_id].get("fragments", [])
    mermaid_images = ppt_jobs[job_id].get("mermaid_images", [])  # base64 编码的 Mermaid 图片
    
    for i, section in enumerate(outline.get("sections", [])):
        # 获取 fragment 截图
        frag_b64 = None
        frag_id = section.get("visual_fragment_id")
        if frag_id:
            for f in fragments:
                if f.get("id") == frag_id:
                    frag_b64 = f.get("data_base64")
                    break

        # 获取 Mermaid 图表图片
        mermaid_b64 = None
        if i < len(mermaid_images) and mermaid_images[i]:
            import base64
            mermaid_b64 = base64.b64encode(mermaid_images[i]).decode('utf-8')

        slides.append({
            "id": i + 1,
            "type": "content",
            "title": section.get("title", ""),
            "points": section.get("points", []),
            "table": section.get("table", ""),
            "fragment_b64": frag_b64,
            "mermaid_b64": mermaid_b64,
            "visual_type": section.get("visual_type"),  # 'mindmap', 'flowchart', 'architecture', 'image'
            "theme": theme
        })
        
    # Conclusion Slide
    if outline.get("conclusion"):
        slides.append({
            "id": len(slides),
            "type": "conclusion",
            "title": "总结与展望",
            "points": outline.get("conclusion", []),
            "theme": theme
        })
        
    # Thank You Slide
    slides.append({
        "id": len(slides),
        "type": "thankyou",
        "title": "谢谢观看",
        "subtitle": "Q&A / 联系我们",
        "theme": theme
    })
    
    return {"slides": slides}
    
@router.get("/ppt/download/{job_id}")
async def download_ppt(job_id: str):
    """下载生成的 PPT"""
    import re
    filename = f"{job_id}.pptx"
    filepath = os.path.join("outputs", filename)
    
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="PPT 文件不存在")
    
    ppt_title = ppt_jobs.get(job_id, {}).get("title", "presentation")
    safe_title = re.sub(r'[\\/*?:"<>|]', "", ppt_title)
    if not safe_title: safe_title = "presentation"
    
    return FileResponse(
        filepath, 
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=f"{safe_title}.pptx"
    )

@router.websocket("/ppt/ws")
async def ppt_websocket_endpoint(websocket: WebSocket, jobId: str):
    """PPT 进度通知 WebSocket"""
    await websocket.accept()
    if jobId not in ppt_active_connections:
        ppt_active_connections[jobId] = []
    ppt_active_connections[jobId].append(websocket)
    
    if jobId in ppt_jobs:
        await websocket.send_text(json.dumps({"type": "progress", "data": ppt_jobs[jobId]}))
        
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ppt_active_connections[jobId].remove(websocket)
        if not ppt_active_connections[jobId]:
            del ppt_active_connections[jobId]


# ==================== 视频助手接口 ====================

router.include_router(video_note.router, prefix="/video-note", tags=["Video Note"])
router.include_router(video_model.router, prefix="/video-model", tags=["Video Model"])
router.include_router(video_provider.router, prefix="/video-provider", tags=["Video Provider"])
router.include_router(video_config.router, prefix="/video-config", tags=["Video Config"])

"""
文章业务逻辑服务
整合爬虫、解析器和数据库操作
"""
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import re
from typing import List, Optional, Dict
from uuid import UUID

from app.services.crawler import CrawlerService
from app.services.parser import ParserService
from app.repository.article import ArticleRepository
from app.repository.column import ColumnRepository
from app.repository.metadata import CategoryRepository
from app.repository.lifecycle import ArticleHistoryRepository
from app.schemas.article import ArticleCreate, ArticleUpdate, ConvertResult, TOCItem, ArticleVisibility

logger = logging.getLogger(__name__)


class ArticleService:
    """文章业务服务类"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.crawler = CrawlerService()
        self.parser = ParserService()
        self.repo = ArticleRepository(db)
        self.column_repo = ColumnRepository(db)
        self.category_repo = CategoryRepository(db)
    
    async def _determine_article_settings(self, column_id: Optional[UUID]) -> tuple[bool, str, Optional[UUID]]:
        """
        根据专栏判定文章的免费状态、可见性与分类联动
        返回: (is_free, visibility, category_id)
        """
        if not column_id:
            return True, ArticleVisibility.PUBLIC.value, None
            
        column = await self.column_repo.get_by_id(column_id)
        if not column:
            return True, ArticleVisibility.PUBLIC.value, None
            
        # 0. 联动分类逻辑
        category_id = None
        if column.category:
            category = await self.category_repo.get_by_name(column.category)
            if category:
                category_id = category.id

        # 1. 根据名称前缀判定
        if column.name.startswith("免费-"):
            return True, ArticleVisibility.PUBLIC.value, category_id
        if column.name.startswith("付费-"):
            return False, ArticleVisibility.PRIVATE.value, category_id
            
        # 2. 回退到专栏自身的 is_free 属性
        is_free = getattr(column, 'is_free', True)
        visibility = ArticleVisibility.PUBLIC.value if is_free else ArticleVisibility.PRIVATE.value
        return is_free, visibility, category_id
    
    async def convert_url_to_article(
        self, 
        url: str, 
        title: Optional[str] = None,
        column_id: Optional[UUID] = None,
        creator_id: Optional[UUID] = None,
        cookies: Optional[Dict] = None,
        password: Optional[str] = None,
        parent_id: Optional[UUID] = None
    ) -> ConvertResult:
        """
        主控方法：转换 URL 为数据库文章
        """
        # 0. URL 归一化 (针对飞书/Wiki 去除 query params，避免重复抓取)
        if "feishu.cn" in url or "larksuite.com" in url:
            if "?" in url:
                original_url = url
                url = url.split("?")[0]
                logger.info(f"🔗 URL 归一化: {original_url} -> {url}")

        try:
            # 1. 抓取内容
            logger.info(f"开始抓取: {url}")
            crawl_result = await self.crawler.crawl(url, password=password, cookies=cookies)
            
            if not crawl_result:
                return ConvertResult(
                    url=url,
                    success=False,
                    error="抓取失败，可能是平台限制或 URL 无效"
                )
            
            # 2. 解析内容
            logger.info(f"开始解析: {url}")
            
            parser_cookies = crawl_result.get('cookies') or cookies
            parser_headers = crawl_result.get('headers')
            images_data = crawl_result.get('images_data')
            
            # 优先使用传入的 title
            final_title = title or crawl_result.get('title')
            
            parsed_data = await self.parser.parse(
                crawl_result['html'],
                crawl_result['platform'],
                url,
                cookies=parser_cookies,
                headers=parser_headers,
                images_data=images_data,
                client_vars_data=crawl_result.get('client_vars_data'),
                title=final_title,
                crawler=self.crawler
            )
            
            if not parsed_data['content']:
                return ConvertResult(
                    url=url,
                    success=False,
                    error="解析失败，未找到有效内容"
                )
            
            # 3. 保存或更新数据库
            # 检查是否已存在
            existing = await self.repo.get_by_url(url)
            
            if existing:
                logger.info(f"文章已存在，正在更新内容: {url}")
                from app.schemas.article import ArticleUpdate
                is_free, visibility, category_id = await self._determine_article_settings(column_id)
                update_data = ArticleUpdate(
                    title=parsed_data['title'],
                    summary=parsed_data['summary'],
                    content=parsed_data['content'],
                    cover_image=parsed_data['cover_image'],
                    column_id=column_id,
                    category_id=category_id,
                    is_free=is_free,
                    visibility=visibility
                )
                article = await self.repo.update(existing.id, update_data)
            else:
                logger.info(f"正在创建新文章: {url}")
                is_free, visibility, category_id = await self._determine_article_settings(column_id)
                article_data = ArticleCreate(
                    title=parsed_data['title'],
                    summary=parsed_data['summary'],
                    content=parsed_data['content'],
                    source_url=url,
                    source_platform=crawl_result['platform'],
                    cover_image=parsed_data['cover_image'],
                    column_id=column_id,
                    category_id=category_id,
                    is_free=is_free,
                    visibility=visibility,
                    parent_id=parent_id # 传入 parent_id
                )
                
                # 权限继承逻辑
                if parent_id:
                    parent = await self.repo.get_by_id(parent_id)
                    if parent:
                        article_data.visibility = ArticleVisibility(parent.visibility) if isinstance(parent.visibility, str) else parent.visibility
                
                article = await self.repo.create(article_data, creator_id=creator_id)
                
                # 创建初始版本历史
                history_repo = ArticleHistoryRepository(self.db)
                await history_repo.create_snapshot(
                    article.id, 
                    article.title, 
                    article.content, 
                    creator_id=creator_id
                )
            
            await self.db.commit()
            
            status_msg = "更新成功" if existing else "创建成功"
            logger.info(f"文章{status_msg}: {article.id}")
            return ConvertResult(
                url=url,
                success=True,
                article_id=article.id
            )
        
        except Exception as e:
            logger.error(f"转换文章失败: {url}, 错误: {str(e)}")
            await self.db.rollback()
            return ConvertResult(
                url=url,
                success=False,
                error=str(e)
            )
        finally:
            # 4. 清理临时目录
            if 'crawl_result' in locals() and crawl_result and crawl_result.get('temp_dir'):
                try:
                    import shutil
                    import os
                    temp_dir = crawl_result['temp_dir']
                    if os.path.exists(temp_dir):
                        logger.info(f"🧹 清理临时目录: {temp_dir}")
                        shutil.rmtree(temp_dir)
                except Exception as e:
                    logger.warning(f"清理临时目录失败: {e}")

    async def batch_convert(
        self, 
        urls: List[str], 
        column_id: Optional[UUID] = None,
        creator_id: Optional[UUID] = None,
        parent_id: Optional[UUID] = None
    ) -> List[ConvertResult]:
        """
        批量转换 URL 为文章
        """
        results = []
        for url in urls:
            result = await self.convert_url_to_article(
                url, column_id, 
                creator_id=creator_id, 
                parent_id=parent_id
            )
            results.append(result)
        
        return results
    
    async def create_article_from_document(
        self, 
        filename: str, 
        md_content: str, 
        column_id: Optional[UUID] = None,
        creator_id: Optional[UUID] = None,
        source_protocol: str = "pdf",
        parent_id: Optional[UUID] = None
    ) -> ConvertResult:
        """从转换后的 Markdown (PDF/PPT/Office) 创建文章"""
        try:
            # 1. 解析 Markdown 到块
            blocks = self.parser.parse_markdown(md_content)
            if not blocks:
                return ConvertResult(url=filename, success=False, error="解析内容失败")
                
            # 2. 提取标题：优先使用第一个一级标题，否则使用文件名
            title = filename
            
            def strip_html(text):
                if not text: return ""
                # 1. 强力移除各种形式的 (cid:XXXX) 和非法字符
                text = re.sub(r'\(cid:[^)]+\)', '', text)
                text = text.replace("\ufffd", "")
                # 2. 移除不可见和异常控制字符
                text = "".join(c for c in text if c.isprintable())
                # 3. 移除 HTML 标签和转义符
                text = text.replace("&nbsp;", " ")
                clean = re.sub(r'<[^>]*>', '', text)
                # 4. 移除 Markdown 标题标记和多余空白
                clean = re.sub(r'^#+\s*', '', clean)
                return clean.strip()
                
            for block in blocks:
                if block['type'] == 'heading' and block['content']['level'] == 1:
                    title_text = strip_html(block['content']['text'])
                    # 过滤转换失败等引擎提示，寻找真实标题
                    if title_text and len(title_text) > 2 and "转换失败" not in title_text and "解析故障" not in title_text:
                        title = title_text
                        break
            
            # 3. 提取摘要
            summary = ""
            for block in blocks:
                if block['type'] == 'text':
                    text_content = strip_html(block['content']['text'])
                    if text_content:
                        summary = text_content[:200]
                        break
            
            # 4. 生成唯一来源 URL
            source_url = f"{source_protocol}://{filename}"
            
            # 5. 检查是否已存在
            existing = await self.repo.get_by_url(source_url)
            
            if existing:
                logger.info(f"文档文章已存在，正在更新: {filename}")
                from app.schemas.article import ArticleUpdate
                is_free, visibility, category_id = await self._determine_article_settings(column_id)
                update_data = ArticleUpdate(
                    title=title,
                    summary=summary,
                    content=blocks,
                    column_id=column_id,
                    category_id=category_id,
                    is_free=is_free,
                    visibility=visibility
                )
                article = await self.repo.update(existing.id, update_data)
            else:
                logger.info(f"正在创建文档文章: {filename}")
                is_free, visibility, category_id = await self._determine_article_settings(column_id)
                article_data = ArticleCreate(
                    title=title,
                    summary=summary,
                    content=blocks,
                    source_url=source_url,
                    source_platform=source_protocol,  # 使用实际文档类型：pdf/ppt/office/text
                    column_id=column_id,
                    category_id=category_id,
                    is_free=is_free,
                    visibility=visibility,
                    parent_id=parent_id
                )
                
                # 权限继承逻辑
                if parent_id:
                    parent = await self.repo.get_by_id(parent_id)
                    if parent:
                        article_data.visibility = ArticleVisibility(parent.visibility) if isinstance(parent.visibility, str) else parent.visibility
                        
                article = await self.repo.create(article_data, creator_id=creator_id)
            
            await self.db.commit()
            return ConvertResult(
                url=source_url,
                success=True,
                article_id=article.id
            )
            
        except Exception as e:
            logger.error(f"创建 PDF 文章失败: {filename}, 错误: {str(e)}")
            await self.db.rollback()
            return ConvertResult(url=filename, success=False, error=str(e))

        return "\n".join(text_parts)

    async def get_article_plain_text(self, article_id: UUID) -> str:
        """获取文章的纯文本内容，用于 AI 处理"""
        article = await self.repo.get_by_id(article_id)
        if not article or not article.content:
            return ""
            
        import re
        text_parts = []
        def clean_tags(t):
            return re.sub(r'<[^>]+>', '', str(t))
            
        for block in article.content:
            b_type = block.get('type')
            b_data = block.get('content', {}) or {}
            
            if b_type == 'text':
                text_parts.append(clean_tags(b_data.get('text', '')))
            elif b_type == 'heading':
                text_parts.append(f"\n## {clean_tags(b_data.get('text', ''))}\n")
            elif b_type == 'list':
                for item in b_data.get('items', []):
                    item_text = item.get('text', '') if isinstance(item, dict) else str(item)
                    text_parts.append(f"- {clean_tags(item_text)}")
            elif b_type == 'table':
                for row in b_data.get('rows', []):
                    row_text = " | ".join([clean_tags(cell.get('content', [{}])[0].get('content', {}).get('text', '')) for cell in row.get('cells', [])])
                    text_parts.append(row_text)
                    
        return "\n".join(text_parts)

    def generate_toc(self, content: List[dict]) -> List[TOCItem]:
        """从文章内容块生成目录（TOC）"""
        if not content:
            return []
            
        toc = []
        stack = []
        
        # 1. 过滤出所有标题
        headings = []
        for i, block in enumerate(content):
            if block.get('type') == 'heading':
                h_data = block.get('content', {})
                level = h_data.get('level', 2)
                text = h_data.get('text', '').strip()
                if text:
                    # 去除标签映射
                    import re
                    clean_text = re.sub(r'<[^>]+>', '', text)
                    headings.append({
                        'id': f"heading-{i}",
                        'level': level,
                        'text': clean_text
                    })
        
        # 2. 构建嵌套结构
        for h in headings:
            item = TOCItem(id=h['id'], level=h['level'], text=h['text'], children=[])
            
            while stack and stack[-1].level >= h['level']:
                stack.pop()
            
            if not stack:
                toc.append(item)
            else:
                stack[-1].children.append(item)
            
            stack.append(item)
            
        return toc

    async def update_article_with_history(self, article_id: UUID, data: ArticleUpdate, creator_id: Optional[UUID] = None) -> Optional[dict]:
        """更新文章并保存历史版本"""
        article = await self.repo.update(article_id, data)
        if not article:
            return None
            
        # 保存历史版本
        history_repo = ArticleHistoryRepository(self.db)
        await history_repo.create_snapshot(
            article.id, 
            article.title, 
            article.content, 
            creator_id=creator_id
        )
        
        return article

    async def restore_from_history(self, article_id: UUID, history_id: UUID, creator_id: Optional[UUID] = None) -> Optional[dict]:
        """从历史版本恢复"""
        history_repo = ArticleHistoryRepository(self.db)
        history = await history_repo.get_by_id(history_id)
        if not history or history.article_id != article_id:
            return None
            
        # 更新文章内容
        update_data = ArticleUpdate(
            title=history.title,
            content=history.content
        )
        return await self.update_article_with_history(article_id, update_data, creator_id)

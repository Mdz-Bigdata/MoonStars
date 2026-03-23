import asyncio
from contextlib import asynccontextmanager
import base64
import hashlib
import json
import logging
import os
import re
import time
from typing import Dict, List, Optional, Set, Any
from urllib.parse import urlparse

import aiofiles
from playwright.async_api import async_playwright, Page, BrowserContext

# 设置日志
logger = logging.getLogger("app.services.crawler")

from app.core.config import settings

class CrawlerService:
    def __init__(self):
        # 飞书资源标识符模式
        self.token_patterns = [
            r'/obj/([a-zA-Z0-9_-]{20,})',
            r'token=([a-zA-Z0-9_-]{20,})',
            r'/([a-zA-Z0-9_-]{20,})(?:\?|$|/)'
        ]
        # 🛡️ 强制在项目目录下建立临时文件夹，避免 Playwright 在系统临时目录遇到 EPERM 权限问题
        self.local_tmp = os.path.join(os.getcwd(), "tmp", "playwright")
        os.makedirs(self.local_tmp, exist_ok=True)
        os.environ["TMPDIR"] = self.local_tmp

    async def crawl(self, url: str, password: Optional[str] = None, cookies: Optional[Dict] = None) -> Optional[Dict]:
        """抓取调度器 (Version: 2026.01.27.01)"""
        if "feishu.cn" in url or "larksuite.com" in url:
            return await self.crawl_feishu(url, password=password, cookies=cookies)
        
        # 对于其他平台使用通用抓取
        logger.info(f"🌐 识别到非飞书域名，启动通用抓取: {url}")
        return await self.crawl_generic(url, password=password, cookies=cookies)

    @asynccontextmanager
    async def crawl_raw_page(self, url: str):
        """核心能力：提供可操作的 Playwright 页面上下文"""
        os.environ["TMPDIR"] = self.local_tmp # 二次确保环境变量已生效
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = await context.new_page()
            try:
                # 稳定加载，带重试
                for attempt in range(3):
                    try:
                        await page.goto(url, wait_until='networkidle', timeout=60000)
                        break
                    except Exception as e:
                        if attempt == 2: raise e
                        await asyncio.sleep(2)
                yield page
            finally:
                await browser.close()

    async def crawl_generic(self, url: str, password: Optional[str] = None, cookies: Optional[Dict] = None) -> Optional[Dict]:
        """通用抓取引擎 - 支持微信、语雀及其他公开网页"""
        logger.info(f"🚀 开始通用抓取: {url}")
        
        # 识别平台
        platform = "other"
        if "mp.weixin.qq.com" in url:
            platform = "wechat"
        elif "yuque.com" in url:
            platform = "yuque"
            
        os.environ["TMPDIR"] = self.local_tmp
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={'width': 1280, 'height': 800},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                
                # 注入 Cookies
                if cookies:
                    browser_cookies = []
                    for name, value in cookies.items():
                        browser_cookies.append({
                            'name': name,
                            'value': value,
                            'url': url
                        })
                    await context.add_cookies(browser_cookies)
                
                page = await context.new_page()
                
                # 设置图片捕获 - 使用真正的临时目录，避免与解析后的永久目录冲突
                captured_resources = {}
                import uuid
                temp_id = str(uuid.uuid4())[:8]
                temp_dir = os.path.join(settings.UPLOAD_DIR, "temp", temp_id)
                os.makedirs(temp_dir, exist_ok=True)
                
                async def handle_response(response):
                    try:
                        ct = response.headers.get('content-type', '').lower()
                        if 'image' not in ct: return
                        
                        body = await response.body()
                        if len(body) < 500: return # 忽略太小的图标
                        
                        r_url = response.url
                        ext = ct.split('/')[-1].split(';')[0] or 'png'
                        file_hash = hashlib.md5(r_url.encode()).hexdigest()
                        target_path = os.path.join(temp_dir, f"{file_hash}.{ext}")
                        
                        if not os.path.exists(target_path):
                            async with aiofiles.open(target_path, 'wb') as f:
                                await f.write(body)
                        
                        captured_resources[r_url] = target_path
                    except: pass

                page.on("response", handle_response)
                
                # 导航
                await page.goto(url, wait_until='networkidle', timeout=60000)
                await page.wait_for_timeout(2000) # 给点额外时间加载动态内容
                
                # 获取真实标题
                title = await self._get_fast_title(page)
                
                html_content = await page.content()
                cookies = {c['name']: c['value'] for c in await context.cookies()}
                
                await browser.close()
                
                logger.info(f"✅ 通用抓取成功: {title}, 捕获图片: {len(captured_resources)}")
                return {
                    'html': html_content,
                    'title': title,
                    'platform': platform,
                    'cookies': cookies,
                    'images_data': captured_resources,
                    'temp_dir': temp_dir
                }
                
            except Exception as e:
                logger.error(f"❌ 通用抓取失败: {e}")
                # NOTE: Playwright 不可用时降级到 trafilatura + httpx 静态抓取
                logger.info("🔄 降级到 trafilatura 静态抓取模式...")
                return await self._crawl_generic_static(url)

    async def _crawl_generic_static(self, url: str) -> Optional[Dict]:
        """
        静态降级抓取方案：当 Playwright 不可用时使用 httpx + trafilatura。
        不支持 JavaScript 渲染，但能处理大部分静态网页和微信公众号文章。
        """
        import httpx
        import trafilatura
        from bs4 import BeautifulSoup

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            }
            async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                html_content = response.text

            # 使用 trafilatura 提取正文
            content = trafilatura.extract(
                html_content,
                include_links=False,
                include_images=False,
                include_tables=True,
            ) or ""

            # 使用 BeautifulSoup 提取标题
            soup = BeautifulSoup(html_content, 'lxml')
            title = ""
            # 尝试多种标题源
            for selector in ['h1', 'title', 'meta[property="og:title"]']:
                el = soup.select_one(selector)
                if el:
                    title = el.get('content', '') if el.name == 'meta' else el.get_text(strip=True)
                    if title:
                        break
            title = title or "未命名文档"

            # 识别平台
            platform = "other"
            if "mp.weixin.qq.com" in url:
                platform = "wechat"
            elif "yuque.com" in url:
                platform = "yuque"

            logger.info(f"✅ 静态降级抓取成功: {title}, 内容长度: {len(content)} 字符")
            return {
                'html': html_content,
                'title': title,
                'platform': platform,
                'cookies': {},
                'images_data': {},
                'temp_dir': None,
            }
        except Exception as e2:
            logger.error(f"❌ 静态降级也失败: {e2}")
            return None

    async def crawl_feishu(self, url: str, password: Optional[str] = None, cookies: Optional[Dict] = None) -> Optional[Dict]:
        """抓取飞书文档 (极致高保真版)"""
        logger.info(f"🚀 [Performance-Mode] 开始抓取飞书文档: {url}")
        
        os.environ["TMPDIR"] = self.local_tmp
        async with async_playwright() as p:
            max_retries = 3
            retry_delays = [5, 10, 15]  # 增加重试间隔
            
            for attempt in range(max_retries):
                logger.info(f"🔄 启动浏览器会话 (第 {attempt+1} 次尝试)...")
                browser = None
                try:
                    # 增强反检测参数（参考用户代码 feishu_content_capture.py）
                    browser = await p.chromium.launch(
                        headless=True,
                        args=[
                            '--disable-gpu',
                            '--disable-dev-shm-usage',
                            '--no-sandbox',
                            '--disable-web-security',
                            '--disable-features=IsolateOrigins,site-per-process',
                            '--disable-background-timer-throttling',
                            # ⚠️ 移除禁用 GPU/WebGL 的参数以支持画板渲染
                            '--blink-settings=imagesEnabled=true',
                            # 反检测参数
                            '--disable-blink-features=AutomationControlled',
                        ]
                    )
                    context = await browser.new_context(
                        viewport={'width': 1920, 'height': 2000},
                        device_scale_factor=2,
                        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        locale='zh-CN'
                    )
                    
                    # 注入 Cookies
                    if cookies:
                        browser_cookies = []
                        for name, value in cookies.items():
                            browser_cookies.append({
                                'name': name,
                                'value': value,
                                'url': url
                            })
                        await context.add_cookies(browser_cookies)
                    
                    # 性能优化：拦截多余请求
                    await context.route("**/*", lambda route: self._filter_requests(route))
                    
                    page = await context.new_page()
                    
                    # 1. 快速加载页面以获取标题 (增强重试策略)
                    logger.info(f"⏳ 正在打开页面: {url}")
                    for g_attempt in range(3):
                        try:
                            # 极致兼容：使用 'commit' 策略，只要服务器响应就立即开始后续探测
                            # 这能有效解决重型飞书页面在加载背景资源（如埋点、大图）时导致的 timeout
                            wait_until = 'commit'
                            await page.goto(url, wait_until=wait_until, timeout=60000)
                            logger.info(f"✅ 页面提交成功 (方式: {wait_until})")
                            
                            # 等待关键元素出现，确保文档已初步渲染
                            # 极致等待：给关键元素 120 秒时间（飞书 Wiki 确实非常慢）
                            critical_selectors = [
                                'h1.page-block-content', 
                                '.wiki-title', 
                                '.doc-title', 
                                '.docx-container', 
                                '.wiki-content', 
                                '.wiki-content-wrapper',
                                '.wiki-body-content',
                                '.page-block-children-content',
                                '.lark-editor-container',
                                '.suite-doc-view',
                                '.wiki-viewer',
                                '.docx-viewer',
                                '[data-block-id]',
                                '[class*="docx-"]',
                                '[class*="wiki-content"]',
                                '#app',
                                'body.ready'
                            ]
                            
                            logger.info("⏳ 等待关键文档元素渲染 (120s 超时)...")
                            try:
                                combined_selector = ", ".join(critical_selectors)
                                # 💡 降低超时并改用更灵活的状态检测，避免长时间等待不可见元素
                                await page.wait_for_selector(combined_selector, timeout=120000, state='attached')
                                logger.info("✅ 关键文档元素已加载")
                            except Exception as se:
                                # 💡 二次确认：即使 timeout，如果页面已经有内容块了也直接开始
                                has_content = await page.query_selector('[data-block-id]')
                                if has_content:
                                    logger.info("✅ 检测到已有内容块，跳过等待直接开始")
                                else:
                                    logger.info(f"💡 等待超时或元素尚未完全显示 ({str(se)[:40]})，尝试直接继续抓取...")
                                    # 强制等待一会儿
                                    await page.wait_for_timeout(10000)

                            # 🚀 自动滚动到底部以触发懒加载 (Wiki 长文档必须)
                            logger.info("🖱️ 正在模拟滚动以触发懒加载...")
                            try:
                                await page.evaluate("""
                                    async () => {
                                        await new Promise((resolve) => {
                                            let totalHeight = 0;
                                            let distance = 800;
                                            let timer = setInterval(() => {
                                                let scrollHeight = document.body.scrollHeight;
                                                window.scrollBy(0, distance);
                                                totalHeight += distance;
                                                if(totalHeight >= scrollHeight){
                                                    clearInterval(timer);
                                                    resolve();
                                                }
                                            }, 200);
                                        });
                                        window.scrollTo(0, 0); // 回到顶部
                                    }
                                """)
                                await page.wait_for_timeout(3000) # 等待资源渲染
                                logger.info("✅ 滚动完成")
                            except Exception as e:
                                logger.warning(f"⚠️ 模拟滚动失败: {e}")

                            # 密码处理逻辑 (如果有密码)
                            if password:
                                try:
                                    # 针对飞书密码输入框的常见选择器
                                    # 注意：实际选择器可能随页面更新而变化
                                    password_selectors = [
                                        'input[type="password"]',
                                        '.password-input input',
                                        '[placeholder*="密码"]',
                                        '[placeholder*="password"]'
                                    ]
                                    
                                    password_input = None
                                    for sel in password_selectors:
                                        if await page.locator(sel).count() > 0:
                                            password_input = page.locator(sel).first
                                            break
                                            
                                    if password_input:
                                        logger.info("🔑 探测到密码输入框，正在尝试输入密码...")
                                        await password_input.fill(password)
                                        await page.keyboard.press("Enter")
                                        # 等待密码提交后的页面加载
                                        await page.wait_for_timeout(3000)
                                        await page.wait_for_load_state('networkidle', timeout=10000)
                                except Exception as pe:
                                    logger.warning(f"⚠️ 密码处理过程中出现异常: {pe}")
                            
                            break
                        except Exception as ge:
                            if g_attempt == 2: raise ge
                            logger.warning(f"⚠️ Page.goto 失败 ({wait_until}), 正在重试 ({g_attempt+1}/3)...")
                            await asyncio.sleep(5)  # 增加到 5 秒
                    
                    await page.wait_for_timeout(3000)
                    
                    # 2. 提取标题并构建最终存储路径
                    title = await self._get_fast_title(page)
                    platform_name = "feishu"  # 从 URL 提取
                    safe_title = re.sub(r'[\\/:*?"<>|]', '', title).strip()[:100] or "未命名文档"
                    
                    # 最终目录：uploads/feishu/{safe_title}/
                    final_dir = os.path.join(settings.UPLOAD_DIR, platform_name, safe_title)
                    os.makedirs(final_dir, exist_ok=True)
                    logger.info(f"📁 资源保存目录: {final_dir}")
                    
                    captured_resources: Dict[str, str] = {}
                    
                    # 网络拦截：自动捕获图片
                    async def handle_response(response):
                        try:
                            ct = response.headers.get('content-type', '').lower()
                            if 'image' not in ct: return
                            
                            body = await response.body()
                            if len(body) < 1000: return
                            
                            r_url = response.url
                            token = self._extract_token_from_url(r_url)
                            ext = ct.split('/')[-1].split(';')[0] or 'png'
                            
                            file_hash = hashlib.md5((token or r_url).encode()).hexdigest()
                            target_path = os.path.join(final_dir, f"{file_hash}.{ext}")
                            
                            # 避免重复下载
                            if os.path.exists(target_path) and os.path.getsize(target_path) > 1000:
                                logger.debug(f"♻️ 复用已存在资源: {file_hash}.{ext}")
                                if token and len(token) > 10:
                                    captured_resources[token] = target_path
                                captured_resources[r_url] = target_path
                                return
                            
                            async with aiofiles.open(target_path, 'wb') as f:
                                await f.write(body)
                                
                            if token and len(token) > 10:
                                captured_resources[token] = target_path
                            captured_resources[r_url] = target_path
                        except: pass

                    page.on("response", handle_response)
                    
                    # 稳定加载，使用 networkidle 增强
                    try:
                        await page.wait_for_load_state('networkidle', timeout=60000)
                    except:
                        logger.info("ℹ️ Networkidle 未完全就绪，组件识别可能已经完成，继续执行...")
                    
                    # 3. 极致滚动策略 (流式激活)
                    # 🚀 在开始滚动前，先确保页面已经达到一定的渲染深度
                    await page.wait_for_timeout(2000)
                    discovered_bids = await self._scroll_to_load_all(page)
                    
                    # 4. 深度捕捉复杂组件 (二阶段逻辑)
                    await self._capture_complex_blocks(page, captured_resources, discovered_bids, final_dir)
                    
                    # 5. 提取核心元数据（避免重复提取标题）
                    client_vars = await page.evaluate("""
                        () => {
                            const sources = [window.clientVars, window.WIKI_DATA, window.WIKI_INITIAL_STATE, window.DATA];
                            for (const src of sources) {
                                if (src && typeof src === 'object') {
                                    if (src.clientVars) return JSON.stringify(src.clientVars);
                                    return JSON.stringify(src);
                                }
                            }
                            return '{}';
                        }
                    """)
                    
                    cookies = {c['name']: c['value'] for c in await context.cookies()}
                    html_content = await page.content()
                    
                    await browser.close()
                    
                    logger.info(f"✅ 抓取成功: {title}, 捕获资源: {len(captured_resources)}")
                    return {
                        'html': html_content,
                        'title': title,
                        'platform': 'feishu',
                        'cookies': cookies,
                        'images_data': captured_resources,
                        'client_vars_data': client_vars,
                        'temp_dir': final_dir  # 使用最终目录而非临时目录
                    }
                    
                except Exception as e:
                    logger.error(f"❌ 第 {attempt+1} 次抓取异常: {e}")
                    if browser:
                        try: await browser.close()
                        except: pass
                    
                    if attempt < max_retries - 1:
                        delay = retry_delays[attempt]
                        logger.info(f"⏳ 等待 {delay} 秒后重试...")
                        await asyncio.sleep(delay)
                    else:
                        return None

        return None

    def _filter_requests(self, route):
        """过滤统计、广告、监控请求以提升性能"""
        url = route.request.url.lower()
        blocked_domains = [
            'analytics', 'metrics', 'log-report', 'monitoring', 
            'facebook', 'google-analytics'
        ]
        # 放宽过滤，防止误伤飞书内部资源 (如 spreadsheet 组件所需的 api/v1/xxx)
        if any(domain in url for domain in blocked_domains):
            return route.abort()
        return route.continue_()

    async def _get_fast_title(self, page: Page) -> str:
        """高性能标题提取"""
        selectors = ['h1.page-block-content', '.wiki-title', '.doc-title', 'h1']
        for sel in selectors:
            try:
                el = await page.query_selector(sel)
                if el:
                    t = await el.inner_text()
                    if t and t.strip(): return t.strip()
            except: pass
        return await page.title()

    async def _scroll_to_load_all(self, page: Page) -> List[str]:
        """智能探测滚动加载所有内容并返回可见 ID (深度扫描版)"""
        logger.info("📜 正在智能扫描文档 (深度模式)...")
        discovered_bids = []
        
        # 1. 探测滚动容器 (支持 DocX, Sheet, Bitable, Wiki)
        scroll_container_js = """
            () => {
                const selectors = [
                    '.wiki-content', '.wiki-content-wrapper', '.wiki-body-content', 
                    '.sheet-viewer', '.bitable-viewer', '.doc-viewer', '.bitable-app-container',
                    '#spreadsheet-container', '#spread-sheet-container',
                    '.page-block-children-content', '.suite-doc-view', '.docx-container', 
                    '.wiki-body', '.main-content', '[class*="scroll"]', '[class*="wiki-content"]',
                    '.bear-web-x-container'
                ];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el && el.scrollHeight > el.clientHeight) return sel;
                }
                return 'body';
            }
        """
        scroll_sel = await page.evaluate(scroll_container_js)
        
        # 获取真实总高度 (增强鲁棒性)
        get_height_js = f"""
            () => {{
                const el = document.querySelector('{scroll_sel}');
                if (!el || el === document.body) {{
                    const body = document.body;
                    const doc = document.documentElement;
                    return Math.max(
                        (body ? body.scrollHeight : 0), 
                        (doc ? doc.scrollHeight : 0),
                        (body ? body.offsetHeight : 0), 
                        (doc ? doc.offsetHeight : 0)
                    );
                }}
                return el.scrollHeight || 0;
            }}
        """
        
        last_height = 0
        current_scroll = 0
        try:
            total_height = await page.evaluate(get_height_js)
        except:
            total_height = 2000 # 兜底高度
            
        viewport_height = 1000 # 步长
        view_height = await page.evaluate("() => window.innerHeight")
        
        logger.info(f"   📏 初始总高度: {total_height}, 视口高度: {view_height}")
        
        # 深度扫描：最多滚动 50 次或直到到底
        for i in range(50):
            # 记录当前可见的 IDs (跨 frame 探测：遍历所有 frame 分别执行)
            new_bids = []
            for frame in page.frames:
                try:
                    # 在每个 frame 中分别寻找 ID
                    frame_bids = await frame.evaluate("""() => {
                        const ids = new Set();
                        document.querySelectorAll('[data-record-id]').forEach(el => ids.add(el.getAttribute('data-record-id')));
                        document.querySelectorAll('[data-block-id]').forEach(el => ids.add(el.getAttribute('data-block-id')));
                        return Array.from(ids);
                    }""")
                    if frame_bids:
                        new_bids.extend(frame_bids)
                except: continue
            for bid in new_bids:
                if bid not in discovered_bids: discovered_bids.append(bid)

            # 滚动
            current_scroll += viewport_height
            try:
                if scroll_sel == 'body':
                    await page.evaluate(f"window.scrollTo(0, {current_scroll})")
                else:
                    await page.evaluate(f"(s) => {{ const el = document.querySelector(s); if(el) el.scrollTop = {current_scroll}; }}", scroll_sel)
            except: pass
            
            await page.wait_for_timeout(400) # 给点时间渲染
            
            # 检查高度是否增加（懒加载）
            try:
                new_height = await page.evaluate(get_height_js)
            except:
                new_height = last_height
                
            if i % 5 == 0: logger.info(f"   ⏳ 扫描中... {current_scroll}/{new_height}")
            
            if current_scroll > new_height + 2000: # 已经滚到底部且超出一段距离
                if new_height == last_height: break # 高度没变，真的到底了
            
            # 🛡️ 容错处理：如果总高度为 0，给一个基础高度引导扫描
            if (new_height == 0 or new_height < view_height) and i > 5:
                logger.warning(f"⚠️ 容器 {scroll_sel} 高度识别异常 ({new_height}), 使用 5000px 兜底高度进行扫描")
                new_height = 5000
            
            last_height = new_height
            
        logger.info(f"✅ 扫描完成，发现 {len(discovered_bids)} 个组件 ID")
        return discovered_bids

    async def _capture_complex_blocks(self, page: Page, captured_resources: Dict, discovered_bids: List[str], temp_dir: str):
        """虚拟滚动优化组件捕获引擎 (Capture Engine V14.0)"""
        logger.info("🎯 开始实施 Capture Engine V14.0 组件捕获流程...")
        
        # 1. 注入 CSS 优化布局并隐藏工具栏
        try:
            await page.add_style_tag(content="""
                .component-toolbar,
                .mindmap-zoom-control,
                .whiteboard-toolbox,
                .board-toolbar,
                .board-minimap,
                .whiteboard-minimap,
                .canvas-toolbar,
                .diagram-toolbar,
                .wiki-header,
                .wiki-sidebar-wrapper,
                .suite-header,
                .suite-sidebar,
                .docx-block-menu,
                .block-header,
                [class*="toolbar"],
                [class*="toolbox"],
                [class*="minimap"],
                [class*="zoom-control"],
                [aria-label*="采集"],
                [title*="采集"] {
                    display: none !important;
                    visibility: hidden !important;
                }
                .docx-sheet-block {
                    padding: 0 !important;
                    margin: 0 !important;
                }
            """)
        except Exception as e:
            logger.warning(f"⚠️ 注入CSS失败: {str(e)[:30]}")

        # 2. 逐段扫描并捕获复杂组件（核心策略变更）
        # 不能一次性检测所有组件，因为飞书使用虚拟滚动只渲染可视区域的组件
        logger.info("📜 逐段扫描并捕获复杂组件...")
        
        sheet_selectors = [
            ".docx-sheet-block", 
            ".bitable-container", 
            ".docx-table-block",
            "div[data-block-type='sheet']",
            "div[data-block-type='bitable']"
        ]
        board_selectors = [
            ".docx-whiteboard-block", 
            ".docx-board-block", 
            ".whiteboard-container",
            ".board-container", 
            ".docx-canvas-block",
            ".docx-diagram-block", 
            ".docx-mindmap-block",
            ".wiki-whiteboard-block",
            ".wiki-board-block",
            ".wiki-mindmap-block",
            "div[class*='whiteboard']",
            "div[class*='mindmap']",
            "div[class*='diagram']",
            "div[data-block-type='whiteboard']",
            "div[data-block-type='mindmap']",
            "div[data-block-type='diagram']",
            "div[data-block-type='board']",
            "div[data-record-type='whiteboard']",
            "div[data-record-type='board']",
            "div[data-record-type='mindmap']",
            "div[data-record-type='sheet']",
            "div[data-record-type='bitable']"
        ]
        all_selectors = sheet_selectors + board_selectors
        combined_selector = ", ".join(all_selectors)
        
        # 找到飞书文档的滚动容器
        scroll_container_js = """
            () => {
                const scroller = document.querySelector('.scroller');
                if (scroller && scroller.scrollHeight > scroller.clientHeight) {
                    return { selector: '.scroller', height: scroller.scrollHeight, clientHeight: scroller.clientHeight };
                }
                
                const selectors = [
                    '.wiki-content-wrapper', '.wiki-content', '#spreadsheet-container', '#spread-sheet-container',
                    '.bitable-app-container', '.sheet-viewer', '.bitable-viewer',
                    '.page-block-children-content', '.suite-doc-view', '.docx-container', 
                    '.wiki-body', '.main-content', '.content-wrapper', '.bear-web-x-container'
                ];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el && el.scrollHeight > el.clientHeight) {
                        return { selector: sel, height: el.scrollHeight, clientHeight: el.clientHeight };
                    }
                }
                
                const allDivs = document.querySelectorAll('div');
                let bestDiv = null;
                let maxHeight = 0;
                for (const div of allDivs) {
                    if (div && div.scrollHeight > maxHeight && div.scrollHeight > window.innerHeight * 2) {
                        maxHeight = div.scrollHeight;
                        bestDiv = div;
                    }
                }
                if (bestDiv) {
                    const id = bestDiv.id ? '#' + bestDiv.id : '';
                    const cls = bestDiv.className ? '.' + bestDiv.className.split(' ').join('.') : '';
                    return { selector: id || cls || 'div', height: maxHeight, clientHeight: bestDiv.clientHeight };
                }

                const bodyHeight = (document.body ? document.body.scrollHeight : 0);
                
                // 🛡️ 深度探测：如果 body 高度为 0，看看是不是有全屏 iframe
                if (bodyHeight < window.innerHeight) {
                    const frames = document.querySelectorAll('iframe');
                    for (const f of frames) {
                        try {
                            if (f.contentDocument && f.contentDocument.body.scrollHeight > window.innerHeight) {
                                return { selector: 'iframe', height: f.contentDocument.body.scrollHeight, clientHeight: window.innerHeight };
                            }
                        } catch(e) {}
                    }
                }

                return { 
                    selector: 'body', 
                    height: (bodyHeight > 0 ? bodyHeight : window.innerHeight), 
                    clientHeight: window.innerHeight 
                };
            }
        """
        
        container_info = await page.evaluate(scroll_container_js)
        scroll_selector = container_info['selector']
        total_height = container_info['height']
        viewport_height = container_info['clientHeight']
        
        logger.info(f"   📏 滚动容器: {scroll_selector}, 总高度: {total_height}, 可视高度: {viewport_height}")
        
        # 滚动函数（在正确的容器内滚动）
        async def scroll_to(y):
            if scroll_selector == 'body':
                await page.evaluate(f"window.scrollTo(0, {y})")
            else:
                await page.evaluate(f"document.querySelector('{scroll_selector}').scrollTop = {y}")
        
        # 探测是否是飞书
        is_feishu = "feishu.cn" in page.url or "larksuite.com" in page.url
        # 先做完整滚动来激活所有懒加载内容
        logger.info("📜 第一轮：增量滚动激活懒加载内容...")
        current_y = 0
        scroll_step = 1200 # 增大步长以提升长文档性能
        while current_y < total_height and current_y < 100000: # 🛡️ 对超长文档设置保护性上限
            await scroll_to(current_y)
            # 🚀 针对飞书增加滚动等待，确保 Lazy Load 资源加载
            scroll_wait = 600 if is_feishu else 300
            await page.wait_for_timeout(scroll_wait)
            current_y += scroll_step
            # 动态更新高度
            new_info = await page.evaluate(scroll_container_js)
            if new_info['height'] > total_height:
                total_height = new_info['height']
                logger.info(f"   📈 高度增长: {total_height}")
        
        # 飞书有时需要多次滚动到底部才能加载完整
        for _ in range(3):
            await scroll_to(total_height)
            await page.wait_for_timeout(1000)
            new_info = await page.evaluate(scroll_container_js)
            if new_info['height'] > total_height:
                total_height = new_info['height']
                logger.info(f"   📈 高度再次增长: {total_height}")
            else:
                break
        
        await scroll_to(0)
        await page.wait_for_timeout(1000)
        
        scroll_step = viewport_height * 0.5
        
        captured_bids = set()
        captured_boxes = [] # 用于坐标去重
        captured_count = 0
        scroll_count = 0
        current_scroll = 0
        
        # 返回顶部开始扫描
        await scroll_to(0)
        await page.wait_for_timeout(500)
        
        logger.info("📜 第二轮：逐段扫描并捕获...")
        
        # 逐段扫描整个文档
        # 🚀 针对飞书等重型文档增加初期加载稳定性
        is_feishu_url = "feishu.cn" in page.url or "larksuite.com" in page.url
        if is_feishu_url:
            logger.info("ℹ️ 检测到飞书域名，增加初始渲染等待...")
            await page.wait_for_timeout(3000)
            # 探测是否有“加载中”遮罩
            try:
                await page.wait_for_selector(".ud-modal-overlay, .loading-mask", state="hidden", timeout=10000)
            except: pass

        while current_scroll < total_height and scroll_count < 100:
            scroll_count += 1
            
            # 滚动到当前位置
            await scroll_to(current_scroll)
            # 🚀 针对电子表格等复杂组件，增加渲染深度检测
            if is_feishu_url:
                try:
                    # 轮询检测是否依然存在加载遮罩，或是否有 canvas 已经渲染出有效宽度
                    await page.wait_for_function("""() => {
                        const loading = document.querySelector('.ud-modal-overlay, .loading-mask, .docx-sheet-loading-placeholder, .bitable-loading-mask');
                        if (loading) return false;
                        const canvasses = document.querySelectorAll('.docx-sheet-block canvas, .bitable-container canvas');
                        if (canvasses.length > 0) {
                            return Array.from(canvasses).some(c => c.width > 100);
                        }
                        // 如果没有 canvas，可能是普通的 docx table，直接验证
                        return document.querySelectorAll('.docx-table-block, .bitable-grid-view, .wiki-content').length > 0;
                    }""", timeout=5000)
                except:
                    # 如果超时，仍强制等待一会儿作为最后兜底
                    await page.wait_for_timeout(1000)
            
            await page.wait_for_timeout(500)  # 最后的布局稳定等待
            
            # 检测当前可见区域的复杂组件 (跨框架探测)
            visible_elements_data = []
            for frame in page.frames:
                try:
                    els = await frame.query_selector_all(combined_selector)
                    for el in els:
                        visible_elements_data.append((el, frame))
                except: pass
            
            # 排序：按元素在页面中的 Y 坐标排序，确保捕获顺序与显示顺序一致
            if visible_elements_data:
                # 注意：bounding_box() 返回的是相对于主框架视口的坐标
                elements_with_pos = []
                for el, frame in visible_elements_data:
                    box = await el.bounding_box()
                    if box:
                        elements_with_pos.append(((el, frame), box['y']))
                
                # 按 Y 坐标排序
                elements_with_pos.sort(key=lambda x: x[1])
                visible_elements_data = [x[0] for x in elements_with_pos]
                
                logger.info(f"   📍 位置 {scroll_count}: 检测到 {len(visible_elements_data)} 个复杂组件 (含 iframe)")
            
            for el, frame in visible_elements_data:
                try:
                    box = await el.bounding_box()
                    if not box or box['width'] < 20 or box['height'] < 20:
                        continue
                        
                    # 坐标去重：仅当没有 BID 时作为兜底
                    center_x = box['x'] + box['width'] / 2
                    center_y = box['y'] + box['height'] / 2
                    is_duplicate_pos = False
                    for seen_box in captured_boxes:
                        seen_center_x = seen_box['x'] + seen_box['width'] / 2
                        seen_center_y = seen_box['y'] + seen_box['height'] / 2
                        # 如果中心点距离小于 10 像素，则视为同一个组件
                        if abs(seen_center_x - center_x) < 10 and abs(seen_center_y - center_y) < 10:
                            is_duplicate_pos = True
                            break
                    
                    # 获取 BID
                    bid = (
                        await el.get_attribute('data-record-id') or 
                        await el.get_attribute('data-block-id') or
                        await el.get_attribute('data-id') or
                        await el.get_attribute('id')
                    )
                    
                    # 排除评论块和其他干扰项
                    class_name = (await el.get_attribute('class') or "").lower()
                    if 'comment' in class_name or 'hover' in class_name:
                        continue

                    # 改进去重逻辑：如果有了 BID，就主要靠 BID 去重
                    if bid and bid in captured_bids:
                        continue
                        
                    # 如果没有 BID，或者 BID 是动态生成的，才使用坐标去重
                    if is_duplicate_pos and not bid:
                        continue
                    
                    # 特殊处理：如果坐标完全重合且 BID 不同，可能是一个组件的多个层级，保留 BID 那个
                    if is_duplicate_pos and bid:
                        # 检查是否是同一个位置但更好的 BID
                        logger.info(f"   📍 发现重合位置但有新 BID: {bid}")
                    
                    # 记录位置以去重
                    captured_boxes.append(box)
                    
                    # 确定组件类型
                    class_name = (await el.get_attribute('class') or "").lower()
                    data_type = (await el.get_attribute('data-block-type') or "").lower()
                    data_record_type = (await el.get_attribute('data-record-type') or "").lower()
                    
                    # 增加对 whiteboard 的明确识别
                    if any(kw in class_name or kw in data_type or kw in data_record_type for kw in ['sheet', 'bitable', 'spreadsheet']):
                        comp_type = 'sheet'
                        file_prefix = 'complex_sheet_'
                        wait_time = 5000 # 飞书表格渲染极其缓慢
                    elif any(kw in class_name or kw in data_type or kw in data_record_type for kw in ['whiteboard', 'mindmap', 'board', 'canvas', 'diagram', 'wiki']):
                        # Wiki 容器也可能包含复杂表格，尝试作为 board 处理或 fallback
                        comp_type = 'board'
                        file_prefix = 'complex_board_'
                        wait_time = 4000
                    else:
                        comp_type = 'board'
                        file_prefix = 'complex_board_'
                        wait_time = 3000
                    
                    logger.info(f"   🎯 准备捕获 {comp_type}: bid={bid}, class={class_name[:30]}, type={data_type}")
                    
                    # 定义强制渲染 CSS
                    bypass_css = """
                        .grid-container, .bitable-container, .document-sheet-ssr-content, 
                        .document-sheet-view, .sheet-scroller, .bitable-grid-container, .suite-sheet-view, .sheet-container { 
                            height: auto !important; 
                            max-height: none !important; 
                            overflow: visible !important; 
                        }
                        /* 🚀 针对 docx-sheet-block 保持原始溢出行为，但允许大视口渲染 */
                        .docx-sheet-block {
                             max-height: none !important;
                        }
                        .canvas-container, .board-container, .whiteboard-container {
                            overflow: visible !important;
                        }
                        /* 🚀 移除水印、加载遮罩、以及各种新用户指引导航 */
                        .docx-sheet-tabbar, .bitable-footer, .sheet-tabs-container, 
                        .bear-watermark, .watermark-container, [class*='watermark'],
                        .embed-sheet-dialog-overlay, .loading-mask, .loading-indicator,
                        .ud-modal-overlay, .ud-modal-wrapper, .wiki-visitor-guide,
                        .wiki-guide-mask, .guide-mask, .user-guide-container,
                        .docs-sheet-loading-placeholder, .bitable-loading-placeholder,
                        .loading-spinner { 
                            display: none !important; 
                            opacity: 0 !important;
                            visibility: hidden !important;
                        }
                    """


                    # 🚀 强制注入 CSS 绕过飞书虚拟列表限制 (主页面)
                    await page.add_style_tag(content=bypass_css)
                    
                    # 🚀 同时也注入到所有 iframe 中，处理嵌入式表格
                    for frame in page.frames:
                        try:
                            await frame.add_style_tag(content=bypass_css)
                        except: pass

                    import random
                    rand_suffix = random.randint(100, 999)
                    # 使用序号前缀确保排序正确
                    seq_prefix = f"{captured_count + 1:03d}"
                    file_suffix = bid[:16] if bid else f"unknown_{int(time.time())}"
                    filename = f"{file_prefix}{seq_prefix}_{file_suffix}_{rand_suffix}.png"
                    temp_path = os.path.join(temp_dir, filename)
                    
                    # 检查是否已存在
                    if os.path.exists(temp_path) and os.path.getsize(temp_path) > 5000:
                        if bid:
                            captured_resources[bid] = temp_path
                            captured_bids.add(bid)
                        captured_count += 1
                        continue
                    
                    # 滚动到元素起始位置并等待渲染 (不再居中，避免顶端截断)
                    await page.evaluate("(el) => el.scrollIntoView({behavior: 'instant', block: 'start'})", el)
                    
                    # 🚀 深度滚动预热：快速滚动一次以触发所有懒加载资源
                    if comp_type == 'sheet':
                        await page.evaluate("""(element) => {
                            const scroller = element.querySelector('.notion-scroller, .grid-container, .canvas-container, .board-container, .whiteboard-container, .docx-sheet-block, .bitable-container, .sheet-scroller, .document-sheet-view') || element;
                            scroller.scrollTop = scroller.scrollHeight;
                        }""", el)
                        await page.wait_for_timeout(1000)

                    # 🚀 强制重置内部滚动条，确保从起始位置开始截图
                    await page.evaluate("""(element) => {
                        const scrollers = element.querySelectorAll('.notion-scroller, .grid-container, .canvas-container, .board-container, .whiteboard-container, .docx-sheet-block, .bitable-container, .document-sheet-ssr-content, .sheet-scroller, .document-sheet-view, .bitable-grid-container, .suite-sheet-view, .sheet-container');
                        scrollers.forEach(s => {
                            s.scrollTop = 0;
                            s.scrollLeft = 0;
                        });
                        // 特殊处理根元素
                        element.scrollTop = 0;
                        element.scrollLeft = 0;
                    }""", el)
                    
                    # 🚀 智能等待组件渲染完成 (Polling)
                    if comp_type == 'sheet':
                        logger.info(f"   ⏳ 正在探测组件渲染状态 (BID: {bid})...")
                        for i in range(15): # 最多等待 15s
                            is_ready = await page.evaluate("""(element) => {
                                // 1. 检查飞书特有的加载完成标识
                                const isLoadedClass = !!element.querySelector('.spread-loaded, .bitable-loaded, .faster.spread-loaded');
                                
                                // 2. 检查是否有 Canvas 且尺寸正常 (Canvas 是飞书 Sheet/Bitable 的核心渲染方式)
                                const canvas = element.querySelector('canvas.spreadsheet-canvas, canvas.canvas, .canvas-container canvas');
                                const hasValidCanvas = canvas && canvas.width > 200 && canvas.height > 100;
                                
                                // 3. 检查是否没有明显的加载遮罩
                                const hasLoadingMask = !!element.querySelector('.embed-sheet-dialog-overlay, .loading-mask, .loading-indicator, .ud-loading-outter-container');
                                
                                // 4. 检查是否有 SSR 模式下的内容块或 Grid 单元格 (Wiki 常见)
                                const hasCells = !!element.querySelector('.document-sheet-ssr-content, .grid-cell, .table-cell-text, .bitable-grid-container [role="gridcell"]');
                                
                                return (isLoadedClass || hasValidCanvas || hasCells) && !hasLoadingMask;
                            }""", el)
                            
                            if is_ready:
                                logger.info(f"   ✅ 检测到渲染完成 (耗时 {i+1}s)")
                                break
                            await page.wait_for_timeout(1000)
                            
                    # 给组件最后的 1s 缓冲时间
                    await page.wait_for_timeout(1000)
                    
                    # 再次获取元素位置，确保在滚动后的最新坐标
                    try:
                        # 截图 (尝试高保真截图)
                        full_box = await page.evaluate("""({element, comp_type}) => {
                            if (!element) return null;
                            const rect = element.getBoundingClientRect();
                            const scrollX = window.scrollX || window.pageXOffset;
                            const scrollY = window.pageYOffset || window.scrollY;
                            
                            let fullWidth = rect.width;
                            let fullHeight = rect.height;
                            
                            const scroller = element.querySelector('.notion-scroller') || 
                                           element.querySelector('.grid-container') || 
                                           element.querySelector('.canvas-container') ||
                                           element.querySelector('.board-container') ||
                                           element.querySelector('.whiteboard-container') ||
                                           element.querySelector('.docx-sheet-block') ||
                                           element.querySelector('.bitable-container') ||
                                           element.querySelector('.document-sheet-ssr-content') ||
                                           element.querySelector('.sheet-scroller') ||
                                           element.querySelector('.document-sheet-view') ||
                                           element.querySelector('.bitable-grid-container') ||
                                           element.querySelector('.suite-sheet-view') ||
                                           element.querySelector('.sheet-container') ||
                                           element;
                            
                            if (scroller) {
                                fullWidth = Math.max(fullWidth, scroller.scrollWidth || 0);
                                fullHeight = Math.max(fullHeight, scroller.scrollHeight || 0);
                            }
                            
                            const svg = element.querySelector('svg');
                            if (svg) {
                                try {
                                    const svgRect = svg.getBBox ? svg.getBBox() : svg.getBoundingClientRect();
                                    fullWidth = Math.max(fullWidth, svgRect.width);
                                    fullHeight = Math.max(fullHeight, svgRect.height);
                                } catch(e) {}
                            }
                            
                            // 🚀 保持裁剪紧凑
                            const padding = 0;
                            return {
                                x: Math.max(0, rect.left + scrollX - padding),
                                y: Math.max(0, rect.top + scrollY - padding),
                                width: Math.max(1, Math.min(fullWidth + padding * 2, 8000)), 
                                height: Math.max(1, Math.min(fullHeight + padding * 2, 30000)) 
                            };
                        }""", { "element": el, "comp_type": comp_type })
                        
                        if full_box:
                            # 🚀 优化：针对超大组件动态调整视口 (同步上限到 30000px)
                            current_viewport = page.viewport_size
                            if full_box['height'] > (current_viewport.get('height') or 0):
                                target_h = int(full_box['y'] + full_box['height'] + 1000)
                                logger.info(f"   📐 调整视口以捕获巨型组件: {target_h}px")
                                await page.set_viewport_size({
                                    'width': current_viewport.get('width') or 1280,
                                    'height': min(target_h, 30000) # Sync limit to 30000px
                                })
                                await page.wait_for_timeout(1500)

                            await page.screenshot(path=temp_path, clip=full_box, timeout=25000)
                            
                            # 截图后恢复视口
                            if full_box['height'] > (current_viewport.get('height') or 0):
                                await page.set_viewport_size(current_viewport)
                            
                            logger.info(f"📸 保存{comp_type}: {filename} (高保真, 尺寸: {int(full_box['width'])}x{int(full_box['height'])})")
                            success = True
                    except Exception as e:
                        logger.warning(f"      ❌ 高保真截图失败: {str(e)[:40]}")
                        # 备用方案
                        try:
                            await el.screenshot(path=temp_path, timeout=8000)
                            success = True
                            logger.info(f"📸 保存{comp_type}: {filename} (元素截图)")
                        except: pass
                    
                    # 记录映射
                    if bid:
                        captured_resources[bid] = temp_path
                        captured_resources[bid[:16] if len(bid) > 16 else bid] = temp_path
                        captured_resources[os.path.basename(temp_path)] = temp_path
                        captured_bids.add(bid)
                        logger.info(f"   ✅ 映射 BID: {bid}")
                    
                    captured_count += 1
                    
                except Exception as e:
                    logger.warning(f"⚠️ 组件处理失败: {str(e)[:40]}")
            
            current_scroll += scroll_step
        
        logger.info(f"🎉 逐段扫描完成: 扫描 {scroll_count} 个区域，捕获 {captured_count} 个复杂组件")
        
        # 回到顶部
        await page.evaluate("window.scrollTo(0, 0)")
        
        # 3. 统计结果
        logger.info("🔍 复杂组件捕获统计...")
        # 扫描完毕



    def _extract_token_from_url(self, url: str) -> str:
        # 增加缓存机制，防止重复 MD5 计算
        if not hasattr(self, '_token_cache'): self._token_cache = {}
        if url in self._token_cache: return self._token_cache[url]
        
        token = None
        for pattern in self.token_patterns:
            match = re.search(pattern, url)
            if match: 
                token = match.group(1)
                break
        
        if not token:
            token = hashlib.md5(url.encode()).hexdigest()
        
        self._token_cache[url] = token
        return token

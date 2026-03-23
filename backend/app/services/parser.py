"""
内容解析服务
将抓取到的 HTML/JSON 解析为结构化的内容块
重构版本 - 2026.01.16
"""
from bs4 import BeautifulSoup, NavigableString, Tag
import logging
import re
import os
import aiofiles
import hashlib
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
import httpx
import base64
import json
import asyncio
import copy

from app.core.config import settings
from app.services.feishu import FeishuSDK, FeishuParser

logger = logging.getLogger(__name__)


class ParserService:
    """内容解析服务类"""
    
    def __init__(self):
        self.upload_dir = settings.UPLOAD_DIR
        os.makedirs(self.upload_dir, exist_ok=True)
        # 当前文档的存储路径（会在解析时设置）
        self.current_rel_path = ""
        self.current_abs_path = ""
        self._client = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://mp.weixin.qq.com/'
        }

    async def _get_client(self):
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(verify=False, timeout=15.0)
        return self._client

    def _sanitize(self, t: str) -> str:
        """全局文本净化：清除对 DB 有害的字符"""
        if not t: return ""
        return t.replace("\u0000", "").replace("\x00", "")
    
    
    async def parse(self, html: str, platform: str, source_url: str, **kwargs) -> Dict[str, Any]:
        """统一解析接口"""
        if platform == 'feishu':
            return await self._parse_feishu(html, source_url, **kwargs)
        elif platform == 'wechat':
            return await self._parse_wechat(html, source_url, **kwargs)
        elif platform == 'yuque':
            return await self._parse_yuque(html, source_url, **kwargs)
        
        # 其他平台使用通用解析
        soup = BeautifulSoup(html, 'html.parser')
        title_tag = soup.find('h1') or soup.find('title')
        title = title_tag.get_text().strip() if title_tag else "未命名文章"
        
        return {
            'title': title,
            'summary': title,
            'content': [{'type': 'text', 'content': {'text': '暂不支持该平台的深度解析'}}],
            'cover_image': None
        }

    def parse_markdown(self, md_content: str) -> List[Dict[str, Any]]:
        """将 Markdown 内容转换为结构化块"""
        if not md_content:
            return []
            
        blocks = []
        lines = md_content.split('\n')
        current_text_buffer = []
        in_code_block = False
        code_buffer = []
        code_lang = "text"
        
        def flush_text():
            if current_text_buffer:
                text = "\n".join(current_text_buffer).strip()
                if text:
                    blocks.append({'type': 'text', 'content': {'text': text}})
                current_text_buffer.clear()

        for line in lines:
            # Code block detection
            if line.strip().startswith('```'):
                if not in_code_block:
                    flush_text()
                    in_code_block = True
                    code_lang = line.strip().replace('```', '').strip() or 'text'
                    code_buffer = []
                else:
                    in_code_block = False
                    blocks.append({
                        'type': 'code',
                        'content': {
                            'code': "\n".join(code_buffer),
                            'language': code_lang
                        }
                    })
                    code_buffer = []
                continue
            
            if in_code_block:
                code_buffer.append(line)
                continue
                
            # Heading detection
            heading_match = re.match(r'^(#{1,6})\s+(.*)', line)
            if heading_match:
                flush_text()
                level = len(heading_match.group(1))
                text = heading_match.group(2)
                blocks.append({
                    'type': 'heading',
                    'content': {'level': level, 'text': text}
                })
                continue
            
            # Image detection (more robust search)
            image_search = re.search(r'!\[(.*?)\]\((.*?)\)', line)
            if image_search and not in_code_block:
                flush_text()
                alt_text = image_search.group(1)
                img_url = image_search.group(2)
                blocks.append({
                    'type': 'image',
                    'content': {'url': img_url, 'alt': alt_text}
                })
                # If there's remaining text after the image on the same line (rare in my extractor), 
                # we could handle it, but for now we expect one image per item.
                continue

            # List detection (simple)
            list_match = re.match(r'^[\*\-\+]\s+(.*)', line)
            if list_match:
                # For now, let's just keep them as text or implement a simple list block
                # To be consistent with existing 'list' type:
                # blocks.append({'type': 'list', 'content': {'items': [list_match.group(1)], 'ordered': False}})
                # However, merging them is better. Keeping it simple as text for now or basic list:
                flush_text()
                blocks.append({
                    'type': 'list',
                    'content': {'items': [list_match.group(1)], 'ordered': False}
                })
                continue

            # PDF Page detection (V8.8 Ultimate vision preservation)
            if line.strip().startswith("<div class='pdf-page'") or line.strip().startswith("<div class=\"pdf-page\""):
                flush_text()
                # 寻找闭合标签，将整个页面块作为 HTML 块存储
                blocks.append({
                    'type': 'html',
                    'content': {'text': self._sanitize(line.strip())}
                })
                continue

            # Default text
            if line.strip():
                current_text_buffer.append(self._sanitize(line))
            elif current_text_buffer:
                flush_text()
                
        flush_text()
        return blocks
    def _detect_code_language(self, code: str) -> str:
        """根据代码内容智能识别编程语言，优先识别文本提示"""
        if not code:
            return "text"
        
        # 1. 优先提取文本提示 (如 // Scala: 或 -- SQL:)
        # 只检查前 100 个字符
        head = code[:100].strip()
        hint_match = re.search(r'^(?://|#|--|/\*)\s*(\w+)[:：\s]', head, re.IGNORECASE)
        if hint_match:
            hint = hint_match.group(1).lower()
            # 语义映射
            meta_map = {
                'js': 'javascript',
                'ts': 'typescript',
                'py': 'python',
                'cpp': 'c++',
                'golang': 'go'
            }
            hint = meta_map.get(hint, hint)
            
            # 验证是否在支持列表中
            supported = ['python', 'java', 'javascript', 'typescript', 'shell', 'bash', 'json', 'sql', 'yaml', 'html', 'css', 'scala', 'go', 'rust', 'php', 'ruby', 'kotlin', 'swift']
            if hint in supported:
                return hint

        code_lower = code.lower()
        
        # 2. 常见语言特征正则
        patterns = {
            'python': [r'def\s+\w+\(.*\):', r'import\s+\w+', r'from\s+\w+\s+import', r'print\(.*\)'],
            'java': [r'public\s+class\s+\w+', r'private\s+\w+', r'void\s+\w+\(.*\)', r'System\.out\.println'],
            'javascript': [r'const\s+\w+\s*=', r'let\s+\w+\s*=', r'function\s+\w+\(.*\)', r'console\.log'],
            'typescript': [r'interface\s+\w+', r'type\s+\w+\s*=', r'readonly\s+\w+'],
            'shell': [r'npm\s+', r'pip\s+', r'conda\s+', r'sudo\s+', r'yum\s+', r'apt\s+', r'git\s+', r'ls\s+', r'mkdir\s+', r'cd\s+', r'export\s+'],
            'json': [r'^\{[\s\S]*\}$', r'^\[[\s\S]*\]$'],
            'sql': [r'select\s+.*\s+from', r'insert\s+into', r'update\s+\w+\s+set', r'delete\s+from'],
            'yaml': [r'^\w+:\s+.*', r'^-\s+\w+:\s+.*'],
            'html': [r'<!DOCTYPE\s+html>', r'<html>', r'<div.*>', r'<script.*>'],
            'css': [r'.*\{\s*\w+:\s*.*;\s*\}'],
            'scala': [r'def\s+\w+\(.*\)\s*[:=]', r'val\s+\w+\s*=', r'var\s+\w+\s*=', r'object\s+\w+', r'case\s+class\s+\w+']
        }
        
        for lang, regexes in patterns.items():
            for regex in regexes:
                if re.search(regex, code if lang in ['json', 'yaml', 'html'] else code_lower, re.MULTILINE):
                    return lang
        
        return "text"

    def _extract_and_clean_style(self, element) -> str:
        """从元素中提取并清理样式，只保留必要的展示属性"""
        style = element.get('style', '')
        if not style:
            return ""
        
        # 只保留影响布局和视觉的核心样式
        allowed_props = [
            'font-family', 'font-size', 'font-weight', 'color', 
            'background', 'background-color', 'background-image', 'background-size', 'background-repeat', 'background-position',
            'text-align', 'margin', 'padding', 'line-height', 'letter-spacing',
            'border', 'border-left', 'border-right', 'border-top', 'border-bottom',
            'border-style', 'border-width', 'border-color',
            'border-radius', 'display', 'flex', 'width', 'height', 'justify-content', 'align-items', 'flex-direction',
            'box-shadow', 'overflow', 'max-width', 'vertical-align', 'opacity',
            'text-indent', 'box-sizing', 'word-break', 'overflow-wrap', 'list-style-type', 'list-style-position'
        ]
        
        new_styles = []
        # 稳健分割：利用正则排除括号内的分号 (如 data:image/png;base64, ... 或 linear-gradient)
        pairs = re.split(r';(?![^()]*\))', style)
        for pair in pairs:
            if ':' in pair:
                parts = pair.split(':', 1)
                if len(parts) == 2:
                    prop, val = [p.strip().lower() for p in parts]
                    if prop in allowed_props:
                        # 针对 margin/padding 进行数值限制
                        if 'margin' in prop or 'padding' in prop:
                            val = re.sub(r'(\d+)px', lambda m: f"{min(int(m.group(1)), 80)}px", val)
                            val = re.sub(r'(\d*\.?\d+)(r?em)', lambda m: f"{min(float(m.group(1)), 4)}{m.group(2)}", val)
                            
                        new_styles.append(f"{prop}:{val}")
        
        return ";".join(new_styles)

    async def _download_external_resource(self, url: str, save_dir: str, filename_key: str) -> Dict[str, str]:
        """下载外部资源（图片等）"""
        try:
            client = await self._get_client()
            async with client.stream("GET", url, headers=self.headers) as response:
                if response.status_code == 200:
                    ext = urlparse(url).path.split('.')[-1]
                    if len(ext) > 4 or not ext: ext = 'png'
                    filename = f"{filename_key}.{ext}"
                    filepath = os.path.join(save_dir, filename)
                    
                    async with aiofiles.open(filepath, mode='wb') as f:
                        async for chunk in response.aiter_bytes():
                            await f.write(chunk)
                    
                    # 返回相对于上传根目录的路径，用于前端访问
                    rel_path = os.path.relpath(filepath, self.upload_dir)
                    return {'original_url': url, 'local_path': f"/uploads/{rel_path}"}
        except Exception as e:
            logger.error(f"❌ 下载资源失败 {url}: {str(e)}")
        return None

    def _is_pseudo_heading(self, node: Tag) -> bool:
        """识别微信文章中的伪标题"""
        if node.name not in ['section', 'div', 'p']: return False
        style_attr = node.get('style', '')
        # 常见特征：带网格背景、加粗、居中、大字号
        is_emphasized = 'font-weight:bold' in style_attr.replace(' ', '').lower() or 'font-weight:700' in style_attr.replace(' ', '').lower()
        is_centered = 'text-align:center' in style_attr.replace(' ', '').lower()
        is_large = 'font-size' in style_attr and any(px in style_attr for px in ['17px', '18px', '20px', '22px', '24px'])
        
        text_pure = node.get_text().strip()
        # 正则匹配序号：1., (1), 一、 等
        is_numbered = re.match(r'^(\d+[\.\:、\)])|^([一二三四五六七八九十]+[、\.])|^\(\d+\)', text_pure)
        
        # 排除包含复杂内容的节点
        has_complex = node.find(['img', 'pre', 'code', 'table'])
        
        # NOTE: 针对代码块上方的语言标识进行过滤，避免将其误判为标题
        lang_labels = ['scala', 'sql', 'python', 'java', 'javascript', 'js', 'html', 'css', 'shell', 'bash', 'yaml', 'json', 'typescript', 'ts', 'go', 'rust']
        if text_pure.lower() in lang_labels:
            return False

        return (is_emphasized and (is_centered or is_large)) and not has_complex and 0 < len(text_pure) < 200

    def _parse_heading(self, node: Tag) -> Dict[str, Any]:
        """解析标题块"""
        text_content = node.decode_contents().strip()
        extracted_style = self._extract_and_clean_style(node)
        level = 1
        if node.name.startswith('h'):
            level = int(node.name[1])
        else:
            # 根据特征推测层级
            text_pure = node.get_text().strip()
            if re.match(r'^(\d+\))|^(\(\d+\))', text_pure):
                level = 2
        return {'type': 'heading', 'content': {'level': level, 'text': text_content, 'style': extracted_style}}

    def _parse_table(self, node: Tag) -> Dict[str, Any]:
        """高保真解析表格"""
        rows = []
        table_style = self._extract_and_clean_style(node)
        for tr in node.find_all('tr'):
            cells = []
            tr_style = self._extract_and_clean_style(tr)
            for td in tr.find_all(['td', 'th']):
                cell_style = self._extract_and_clean_style(td)
                # 单元格内部保留 innerHTML 以维持高保真样式（加粗、链接、颜色等）
                cell_html = td.decode_contents().strip()
                cells.append({
                    'content': [{'type': 'text', 'content': {'text': cell_html}}],
                    'style': cell_style,
                    'is_header': td.name == 'th'
                })
            if cells:
                rows.append({'cells': cells, 'style': tr_style})
        return {'type': 'table', 'content': {'rows': rows, 'style': table_style}}

    def _parse_code(self, node: Tag) -> Dict[str, Any]:
        """解析代码块，优化换行处理并去除首行空行"""
        code_el = node.find('code') if node.name == 'pre' else node
        # 拷贝以处理内部标签
        code_clone = copy.copy(code_el)
        for br in code_clone.find_all('br'):
            br.replace_with('\n')
        for li in code_clone.find_all('li'):
            li.append('\n')
            
        # 1. 提取文本
        code_text = code_clone.get_text()
        
        # 2. 移除开头的各种空行（含 \xa0/NBSP，只移除换行相关的空白，保留代码缩进）
        # 使用正则：匹配开头的所有换行符及换行符前后的空格/NBSP
        code_text = re.sub(r'^[\s\xa0\r\n]+', '', code_text)
        code_text = code_text.rstrip()
        
        # 针对用户反馈：去掉代码行间的空行，使间距更紧凑
        # Figure 3 主要是配置文件，移除过多的空行
        code_text = re.sub(r'\n[\s\xa0]*\n', '\n', code_text)
        
        # 3. 语言检测与声明行过滤
        lang = 'text'
        for cls in code_el.get('class', []):
            if cls.startswith('language-'):
                lang = cls.replace('language-', '')
        
        # 微信特有：如果第一行只是语言名称，且后面还有内容，则剔除第一行
        lang_labels = ['shell', 'bash', 'python', 'java', 'javascript', 'js', 'html', 'css', 'sql', 'go', 'golang', 'c++', 'cpp', 'rust', 'yaml', 'json', 'typescript', 'ts', 'php', 'ruby', 'kotlin', 'swift', 'scala']
        lines = code_text.split('\n')
        if len(lines) > 1:
            first_line = lines[0].strip().lower()
            if first_line in lang_labels:
                # 移除语言行，并再次移除后续可能紧跟的空行/NBSP
                code_text = '\n'.join(lines[1:])
                code_text = re.sub(r'^[\s\xa0\r\n]+', '', code_text)
        
        if lang == 'text' or not lang:
            lang = self._detect_code_language(code_text)
            
        return {'type': 'code', 'content': {'code': code_text, 'language': lang}}

    def _parse_box(self, node: Tag) -> Dict[str, Any]:
        """解析带边框的盒子"""
        cleaned_style = self._extract_and_clean_style(node)
        # 核心：递归进入流式合并引擎
        return {'type': 'box', 'content': {'blocks': self._wechat_inner_parse(node), 'style': cleaned_style}}

    def _wechat_inner_parse(self, container: Tag) -> List[Dict[str, Any]]:
        """
        全平台微信流式合并解析引擎
        解决核心痛点：不同样式的文本混排导致的断行
        """
        blocks = []
        inline_buffer = []

        def flush_buffer():
            if inline_buffer:
                # 合并所有行内内容
                html_content = "".join(inline_buffer).strip()
                if html_content:
                    blocks.append({'type': 'text', 'content': {'text': html_content}})
                inline_buffer.clear()

        # 定义行内标签
        # 定义行内标签（现在包括列表容器，因为我们在流式合并中需要保持它们，除非它们包含重大的块）
        inline_tags = ['span', 'strong', 'b', 'em', 'i', 'u', 'font', 'a', 'br', 'sub', 'sup', 'label', 'ol', 'ul', 'li']

        for node in container.children:
            if isinstance(node, NavigableString):
                text = str(node)
                if text.strip() or '\n' in text:
                    inline_buffer.append(text)
                continue

            if not isinstance(node, Tag):
                continue
            
            if node.name in ['script', 'style', 'input', 'button', 'iframe', 'video', 'mp-common-videosnap', 'mp-common-profile', 'mp-common-videoplayer']:
                continue
            
            # 排除微信搜索/广告相关的 class 容器
            node_classes = node.get('class', [])
            if any(cls in node_classes for cls in ['video_iframe_cnt', 'js_video_con', 'ad_unit']):
                continue

            # 过滤广告占位文本 (如 "请在微信客户端打开")
            # 核心修复：不能对大型容器直接进行全文关键词过滤，否则会导致内容丢失
            text_total = node.get_text(strip=True)
            if len(text_total) < 200: # 只针对相对较小的节点（如广告位、占位符）
                if "请在微信客户端打开" in text_total or "该视频无法在此浏览器播放" in text_total:
                    continue

            # A. 核心块级元素识别
            
            # 1. 独立图片块
            if node.name == 'img' or (node.name == 'p' and node.find('img') and len(node.find_all(True)) == 1):
                img_tag = node if node.name == 'img' else node.find('img')
                if not node.get_text(strip=True):
                    flush_buffer()
                    blocks.append({'type': 'image', 'content': {
                        'url': img_tag.get('data-src') or img_tag.get('src') or '',
                        'style': self._extract_and_clean_style(img_tag)
                    }})
                    continue
                else:
                    inline_buffer.append(str(node))
                    continue

            # 2. 标题块
            if node.name.startswith('h') or self._is_pseudo_heading(node):
                # 针对用户反馈：过滤掉完全无内容的标题（如空 h1/h2），避免产生多余空白
                text_pure = node.get_text(strip=True).replace('\xa0', '').strip()
                if not text_pure:
                    continue
                flush_buffer()
                blocks.append(self._parse_heading(node))
                continue

            # 3. 表格块
            if node.name == 'table':
                flush_buffer()
                blocks.append(self._parse_table(node))
                continue

            # 4. 代码块
            if node.name == 'pre' or (node.name == 'section' and 'code-snippet' in node.get('class', [])):
                flush_buffer()
                
                # NOTE: 识别前置语言标识 (Look-behind)
                # 如果前一个块是短文本且是已知语言，则取之并移除该文本块
                detected_lang = None
                if blocks and blocks[-1]['type'] == 'text':
                    prev_text = BeautifulSoup(blocks[-1]['content']['text'], 'html.parser').get_text().strip().lower()
                    if prev_text in ['scala', 'sql', 'python', 'java', 'javascript', 'js', 'html', 'css', 'shell', 'bash', 'yaml', 'json', 'typescript', 'ts', 'go', 'rust']:
                        detected_lang = prev_text
                        blocks.pop() # 移除作为标题存在的语言标签
                
                code_block = self._parse_code(node)
                if detected_lang:
                    code_block['content']['language'] = detected_lang
                    
                blocks.append(code_block)
                continue

            # 5. 边框盒子块
            style_attr = node.get('style', '')
            if 'border' in style_attr and any(bt in style_attr for bt in ['solid', 'dashed', 'dotted', 'double']):
                # 核心决策：如果盒子内部解析后为空，则丢弃该盒子，避免幽灵边框/垂直条
                box_block = self._parse_box(node)
                if box_block['content']['blocks']:
                    flush_buffer()
                    blocks.append(box_block)
                continue

            # B. 行内与容器处理
            if node.name in inline_tags:
                inline_buffer.append(str(node))
                continue

            # 检查容器内是否包含块级标签
            if node.find(['table', 'pre', 'img', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']) or self._is_pseudo_heading(node):
                flush_buffer()
                blocks.extend(self._wechat_inner_parse(node))
            else:
                # 微信排版精髓：保留 section/p 内部所有高真样式
                style = self._extract_and_clean_style(node)
                inner_html = node.decode_contents().strip()
                
                # 针对内容丢失优化：
                # 如果是 section/div 且没有背景边框，或者包含 chunked 的子结构，优先递归解析
                # 微信公众号里的 layout 经常套娃，递归打平是保证高真的关键
                if node.name in ['section', 'div']:
                    is_mdnice_wrapper = node.get('data-tool') == 'mdnice编辑器'
                    # 如果没有背景边框，或者是一个大的 mdnice 包装器，我们必须解析其内部
                    if not any(k in style for k in ['background', 'border']) or is_mdnice_wrapper:
                       # 检查是否有实质内容
                       if node.get_text(strip=True):
                           flush_buffer()
                           blocks.extend(self._wechat_inner_parse(node))
                           continue

                # 针对用户反馈的"大段空白"进行优化：
                # 过滤掉无文本内容且无背景/边框的纯占位块 (如 <p><br></p>)
                text_pure = node.get_text(strip=True).replace('\xa0', '').strip()
                # 精细化视觉判定：背景图(用于图标)、边框、阴影等都属于有视觉效果
                has_visual = any(x in style for x in ['background', 'border', 'box-shadow'])
                
                # 特殊场景：如果没有文字但有明确的宽高和背景（如微信标题左侧的图标 span），必须保留
                is_decorative_icon = not text_pure and 'background' in style and ('width' in style or 'height' in style)

                if not text_pure and not has_visual and not is_decorative_icon:
                    continue

                # 特殊优化：如果这是个大的容器但最终没有产生任何子块，也应跳过，避免巨大的 padding/margin 空白
                if node.name in ['section', 'div', 'blockquote', 'p'] and not text_pure:
                    # 尝试预解析看是否有实质内容
                    temp_inner = self._wechat_inner_parse(node)
                    if not temp_inner:
                        continue

                if inner_html:
                    # 对于块级元素，保留原标签以维持段落结构；行内元素使用 span
                    tag_name = node.name if node.name in ['p', 'section', 'div', 'blockquote', 'li', 'ol', 'ul', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'] else 'span'
                    
                    if tag_name in ['p', 'ul', 'ol', 'li', 'h1', 'h2', 'h3'] and 'margin' not in style and 'padding' not in style:
                        # 针对微信优化：收紧间距，避免过大的空行 (Hudi/JDGenie 反馈)
                        # 如果是标题，甚至是 0 padding
                        if tag_name.startswith('h'):
                             style = f"margin:0;padding:0;{style}" # Reduced padding
                        else:
                             style = f"margin:0;padding:2px 0;{style}" if style else "margin:0;padding:2px 0" # Reduced padding
                    
                    # 特殊处理 ol 的 start 属性
                    start_attr = ""
                    if tag_name == 'ol' and node.get('start'):
                        start_attr = f' start="{node.get("start")}"'

                    if style:
                        # 核心修改：如果是 layout container (section/div/blockquote)，直接作为 box 处理或保留样式
                        if node.name in ['section', 'div', 'blockquote'] and ('background' in style or 'border' in style):
                            flush_buffer()
                            sub_blocks = self._wechat_inner_parse(node)
                            blocks.append({
                                'type': 'box',
                                'content': {
                                    'style': style,
                                    'blocks': sub_blocks
                                }
                            })
                        else:
                            inline_buffer.append(f'<{tag_name} style="{style}"{start_attr}>{inner_html}</{tag_name}>')
                            # 块级容器默认刷新缓冲区以实现换行
                            if tag_name != 'span':
                                flush_buffer()
                    else:
                        inline_buffer.append(f'<{tag_name}{start_attr}>{inner_html}</{tag_name}>')
                        if tag_name != 'span':
                            flush_buffer()

        flush_buffer()
        return blocks

    async def _parse_wechat(self, html: str, source_url: str, **kwargs) -> Dict[str, Any]:
        """高保真微信公众号文章解析"""
        logger.info(f"🔍 开始高保真解析微信文章: {source_url}")
        soup = BeautifulSoup(html, 'html.parser')
        
        # 1. 提取标题
        title_tag = soup.find(id='activity-name') or soup.find('h1') or soup.find('title')
        title = title_tag.get_text().strip() if title_tag else "未命名微信文章"
        
        container_style = "" # NOTE: Initialize safe default
        
        # 2. 设置存储目录
        safe_title = re.sub(r'[\\/:*?"<>|]', '', title).strip()[:50]
        self.current_rel_path = f"wechat/{safe_title}"
        self.current_abs_path = os.path.join(self.upload_dir, self.current_rel_path)
        os.makedirs(self.current_abs_path, exist_ok=True)
        
        content_blocks = []
        
        # 核心解析逻辑
        # 微信文章主体内容在 #js_content 容器中
        content_div = soup.find(id='js_content')
        if not content_div:
            # 尝试直接解析 body
            content_div = soup.find('body')
        
        if content_div:
            # 提取容器样式（用于高保真背景等）
            # 微信网格背景常在 #js_content 的直接子 section (data-tool="mdnice") 上
            container_style = self._extract_and_clean_style(content_div)
            if 'background' not in container_style:
                # 深度搜索背景网格 (仅搜索前层)
                first_section = content_div.find('section', recursive=False)
                if first_section:
                    s = self._extract_and_clean_style(first_section)
                    if 'background' in s:
                        container_style = s
            
            # 预处理：下载所有图片（并行）
            img_tags = content_div.find_all('img')
            results = []
            if img_tags:
                logger.info(f"🚀 并发下载 {len(img_tags)} 张图片...")
                tasks = []
                for img in img_tags:
                    src = img.get('data-src') or img.get('src')
                    if src and src.startswith('http'):
                        # 生成文件名 key
                        filename_key = hashlib.md5(src.encode()).hexdigest()
                        tasks.append(self._download_external_resource(src, self.current_abs_path, filename_key))
                
                # 等待所有下载完成
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
            # --- 建立映射表 ---
            url_map = {}
            for res in results:
                if isinstance(res, dict) and res:
                    url_map[res['original_url']] = res['local_path']
            
            # --- 替换 HTML 中的图片链接 ---
            for img in img_tags:
                src = img.get('data-src') or img.get('src')
                if src in url_map:
                    img['src'] = url_map[src]
                    img['data-src'] = url_map[src]

            # --- 核心解析：调用流式合并引擎 ---
            # 该引擎会智能合并行内元素，解决断行问题
            content_blocks = self._wechat_inner_parse(content_div)
            
        if not content_blocks:
            content_blocks = [{'type': 'text', 'content': {'text': '解析内容为空'}}]

        # 5. 生成摘要和封面
        summary = self._generate_summary(content_blocks)
        cover_image = next((b['content']['url'] for b in content_blocks if b['type'] == 'image'), None)
        
        return {
            'title': title,
            'summary': summary,
            'content': content_blocks,
            'cover_image': cover_image, 'container_style': container_style
        }

    async def _parse_yuque(self, html: str, source_url: str, **kwargs) -> Dict[str, Any]:
        """高保真语雀文档解析"""
        logger.info(f"🔍 开始高保真解析语雀文档: {source_url}")
        soup = BeautifulSoup(html, 'html.parser')
        
        # 1. 提取标题
        title_tag = soup.find(class_='doc-title') or soup.find(class_='wiki-title') or soup.find('h1') or soup.find('title')
        title = title_tag.get_text().strip() if title_tag else "未命名语雀文档"
        
        # 2. 设置存储目录
        safe_title = re.sub(r'[\\/:*?"<>|]', '', title).strip()[:50]
        self.current_rel_path = f"yuque/{safe_title}"
        self.current_abs_path = os.path.join(self.upload_dir, self.current_rel_path)
        os.makedirs(self.current_abs_path, exist_ok=True)
        
        # 3. 解析内容块 (针对 .ne-engine)
        content_blocks = []
        container_style = "" # NOTE: Initialize safe default to fix NameError regression
        container = soup.find(class_='ne-engine') or soup.find(class_='yuque-doc-content') or soup.find('article')
        if container:
            def process_yuque_node(node):
                if not hasattr(node, 'children') or node.name is None:
                    text = node.get_text().strip()
                    if text:
                        return {'type': 'text', 'content': {'text': text}}
                    return None

                if node.name == 'img':
                    img_url = node.get('src')
                    if img_url:
                        return {'type': 'image', 'content': {'url': img_url, 'style': self._extract_and_clean_style(node)}}
                
                if node.name in ['h1', 'h2', 'h3', 'h4']:
                    return {'type': 'heading', 'content': {'level': int(node.name[1]), 'text': node.get_text().strip()}}
                
                if node.name in ['pre', 'code'] or 'ne-code' in node.get('class', []):
                    # 语雀代码块处理
                    code_text = node.get_text()
                    lang = self._detect_code_language(code_text)
                    return {'type': 'code', 'content': {'code': code_text, 'language': lang}}

                if node.name in ['p', 'blockquote', 'li']:
                    if node.find(['img', 'pre', 'code', 'table']):
                        return "RECURSE"
                    text = node.get_text(strip=True)
                    if text:
                        style = self._extract_and_clean_style(node)
                        html_content = f'<span style="{style}">{text}</span>' if style else text
                        return {'type': 'text', 'content': {'text': html_content}}
                
                return "RECURSE"

            for child in container.children:
                stack = [child]
                while stack:
                    curr = stack.pop(0)
                    res = process_yuque_node(curr)
                    if res == "RECURSE" and hasattr(curr, 'children'):
                        stack = list(curr.children) + stack
                    elif res:
                        content_blocks.append(res)

        # 4. 并发优化：批量下载图片
        image_tasks = []
        image_blocks = [b for b in content_blocks if b['type'] == 'image']
        for b in image_blocks:
            image_tasks.append(self._download_external_resource(b['content']['url']))
        
        if image_tasks:
            logger.info(f"🚀 并发下载 {len(image_tasks)} 张图片...")
            local_urls = await asyncio.gather(*image_tasks)
            for b, local_url in zip(image_blocks, local_urls):
                if local_url:
                    b['content']['url'] = local_url

        summary = self._generate_summary(content_blocks)
        cover_image = next((b['content']['url'] for b in content_blocks if b['type'] == 'image'), None)
        
        return {
            'title': title,
            'summary': summary,
            'content': content_blocks,
            'cover_image': cover_image, 'container_style': container_style
        }

    async def _download_external_resource(self, url: str, save_dir: str = None, filename_key: str = None) -> Optional[str]:
        """下载外部资源到本地"""
        if not url or url.startswith('data:'):
            return url
            
        try:
            # 如果没有指定目录，使用当前目录
            if not save_dir:
                if hasattr(self, 'current_abs_path') and self.current_abs_path:
                    save_dir = self.current_abs_path
                else:
                    save_dir = self.upload_dir

            # 如果没有指定 key，生成一个
            if not filename_key:
                filename_key = hashlib.md5(url.encode()).hexdigest()
            
            # 简单猜测扩展名
            ext = '.jpg'
            if '.png' in url.lower(): ext = '.png'
            elif '.gif' in url.lower(): ext = '.gif'
            elif '.svg' in url.lower(): ext = '.svg'
            
            filename = f"{filename_key}{ext}"
            local_path = os.path.join(save_dir, filename)
            
            # 如果已存在，直接返回相对路径
            rel_path = f"/uploads/{os.path.relpath(local_path, self.upload_dir)}"
            if os.path.exists(local_path):
                return {'original_url': url, 'local_path': rel_path}

            async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                resp = await client.get(url, headers=self.headers)
                if resp.status_code == 200:
                    async with aiofiles.open(local_path, 'wb') as f:
                        await f.write(resp.content)
                    return {'original_url': url, 'local_path': rel_path}
                else:
                    logger.warning(f"⚠️ 下载失败 {url}: {resp.status_code}")
                    return None
        except Exception as e:
            logger.error(f"❌ 下载异常 {url}: {e}")
            return None

    async def _parse_feishu(
        self, 
        html: str, 
        source_url: str, 
        cookies: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        images_data: Optional[Dict] = None,
        client_vars_data: Optional[str] = None,
        title: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """飞书文档解析 - 优先使用 API 解析器，回退到 legacy 模式"""
        
        # 1. 优先尝试使用 API 解析器 (推荐：高保真且内容完整)
        if settings.FEISHU_APP_ID and settings.FEISHU_APP_SECRET:
            try:
                sdk = FeishuSDK()
                access_token = sdk.get_tenant_access_token(settings.FEISHU_APP_ID, settings.FEISHU_APP_SECRET)
                if access_token:
                    parser = FeishuParser(sdk, access_token, self.upload_dir)
                    logger.info(f"🚀 使用 API 解析器解析飞书文档: {source_url}")
                    result = await parser.parse_url(
                        source_url, 
                        images_data=images_data, 
                        client_vars_data=client_vars_data
                    )
                    # 如果解析到了内容，则返回结果
                    if result.get('content'):
                        # 同步样式，确保 legacy 模式的一些预期字段存在
                        if 'platform' not in result:
                            result['platform'] = 'feishu'
                        return result
                    
                    # 🚀 特殊检查：如果是 Wiki 节点且解析内容为空，且日志中出现了 spreadsheet_token invalid
                    # 这通常意味着它其实是一个多维表格 (Bitable) 伪装成了表格
                    logger.info("ℹ️ API 解析内容为空，继续尝试...")
            except Exception as e:
                logger.error(f"❌ API 解析飞书文档失败，尝试回退到 Legacy 模式: {e}", exc_info=True)

        # 2. 回退到旧版 Playwright/clientVars 解析
        return await self._parse_feishu_legacy(
            html, source_url, cookies, headers, images_data, client_vars_data, title, **kwargs
        )

    async def _parse_feishu_legacy(
        self, 
        html: str, 
        source_url: str, 
        cookies: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        images_data: Optional[Dict] = None,
        client_vars_data: Optional[str] = None,
        title: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """飞书文档解析 - 旧版 Legacy 模式"""
        logger.info(f"💾 使用 Legacy 模式解析飞书文档: {source_url}")
        
        # 重置顺序计数器，确保每个文档解析时顺序匹配从 0 开始
        self._sheet_counter = 0
        self._board_counter = 0
        self._global_complex_counter = 0
        
        # 1. 解析 clientVars 获取 block_map
        block_map = {}
        raw_data = {}
        try:
            if isinstance(client_vars_data, str):
                raw_data = json.loads(client_vars_data)
            elif isinstance(client_vars_data, dict):
                raw_data = client_vars_data
            
            cv = raw_data.get('clientVars', raw_data)
            data = cv.get('data', {}) if isinstance(cv.get('data'), dict) else {}
            block_map = data.get('block_map') or data.get('blocks') or {}
            logger.info(f"📦 解析到 {len(block_map)} 个内容块")
        except Exception as e:
            logger.error(f"解析 clientVars 失败: {e}")
        
        # 2. 标题与路径 (全面遵循用户规范)
        final_title = self._extract_title(title, raw_data)
        safe_title = re.sub(r'[\\/:*?"<>|]', '', final_title).strip()[:120]
        
        # 从 URL 提取平台标识 (默认 feishu)
        platform_part = kwargs.get('platform', 'feishu')
        if "feishu" in source_url or "larksuite" in source_url:
            platform_part = "feishu"
        
        self.current_rel_path = f"{platform_part}/{safe_title}"
        self.current_abs_path = os.path.join(self.upload_dir, self.current_rel_path)
        os.makedirs(self.current_abs_path, exist_ok=True)
        
        # 3. 处理资源与解析
        images_data = images_data or {}
        container_style = "" # NOTE: Initialize safe default
        tokens = set()
        self._scan_tokens(block_map, tokens, is_top_level=True)
        token_to_url = await self._process_resources(block_map, images_data, source_url, cookies)
        content_blocks = []
        block_sequence = self._get_block_sequence(raw_data, block_map)
        visited = set()
        for bid in block_sequence:
            await self._parse_block_recursive(bid, block_map, token_to_url, content_blocks, visited)
        
        # 合并列表
        processed_blocks = self._post_process_blocks(content_blocks)
        summary = self._generate_summary(processed_blocks, final_title)
        cover_image = next((b['content']['url'] for b in processed_blocks if b['type'] == 'image'), None)
        
        return {
            'title': final_title,
            'summary': summary,
            'content': processed_blocks,
            'cover_image': cover_image, 'container_style': container_style
        }

    def _post_process_blocks(self, blocks: List[Dict]) -> List[Dict]:
        """对解析后的块进行优化合并"""
        if not blocks: return []
        
        new_blocks = []
        for block in blocks:
            if not new_blocks:
                new_blocks.append(block)
                continue
            
            last = new_blocks[-1]
            # 合并连续的同类列表项
            if block['type'] == 'list' and last['type'] == 'list' and \
               block['content'].get('ordered') == last['content'].get('ordered'):
                last['content']['items'].extend(block['content']['items'])
                continue
            
            new_blocks.append(block)
            
        return new_blocks

    def _extract_title(self, page_title: Optional[str], raw_data: Dict) -> str:
        """从多个来源提取文档标题"""
        # 优先使用 meta 中的标题
        cv = raw_data.get('clientVars', raw_data)
        data = cv.get('data', {}) if isinstance(cv.get('data'), dict) else {}
        
        candidates = [
            page_title,
            data.get('meta', {}).get('title'),
            cv.get('wikiMeta', {}).get('title'),
            raw_data.get('meta', {}).get('title'),
            raw_data.get('workspaceName'),
        ]
        
        for t in candidates:
            if t and t not in ['Docs', '飞书云文档', '飞书', 'Lark', 'Wiki']:
                # 完善清理逻辑：不仅仅是后缀，还有各种零宽字符、装饰符
                t = t.replace('\u200b', '').replace('\ufeff', '').strip()
                t = re.sub(r'\s*-\s*飞书[云]?文档.*', '', t, flags=re.I)
                t = re.sub(r'\s*-\s*Lark.*', '', t, flags=re.I)
                t = re.sub(r'\s*-\s*Wiki.*', '', t, flags=re.I)
                t = re.sub(r'\s*\|\s*飞书.*', '', t, flags=re.I)
                t = t.strip()
                if t and t not in ['Docs', '飞书云文档', '飞书', 'Lark', 'Wiki']:
                    return t
        
        return "未命名飞书文档"

    def _get_block_sequence(self, raw_data: Dict, block_map: Dict) -> List[str]:
        """获取内容块的遍历顺序"""
        cv = raw_data.get('clientVars', raw_data)
        data = cv.get('data', {}) if isinstance(cv.get('data'), dict) else {}
        
        # 优先使用 block_sequence
        sequence = data.get('block_sequence') or cv.get('block_sequence') or raw_data.get('block_sequence')
        if sequence:
            return sequence
        
        # 尝试从 body.blocks 提取 (某些 Wiki 场景)
        body_blocks = data.get('body', {}).get('blocks', [])
        if body_blocks:
            return [b.get('block_id') for b in body_blocks if b.get('block_id')]

        # 否则返回 block_map 的所有 key
        return list(block_map.keys())

    async def _parse_block_recursive(
        self,
        bid: str,
        block_map: Dict,
        token_to_url: Dict[str, str],
        results: List[Dict],
        visited: set
    ):
        """
        递归解析飞书内容块
        每个块只处理一次（通过 visited 集合控制）
        """
        if not bid or bid in visited:
            return
        
        block = block_map.get(bid)
        if not block:
            return
        
        visited.add(bid)
        
        # 获取块数据
        b_data = block.get('data', {}) if isinstance(block.get('data'), dict) else {}
        b_type = b_data.get('type') or block.get('type', '')
        
        # 获取 children（飞书的 children 存储在 data.children 中）
        children = b_data.get('children') or block.get('children') or block.get('child_ids', [])
        
        # 根据类型处理
        results_len_before = len(results)
        
        if b_type in ['text', 'paragraph']:
            self._handle_text_block(block, results)
        
        elif b_type.startswith('heading'):
            self._handle_heading_block(block, b_type, results)
        
        elif b_type in ['bullet', 'ordered', 'checklist', 'todo']:
            self._handle_list_block(block, b_type, results)
        
        elif b_type == 'code':
            self._handle_code_block(block, results)
        
        elif b_type == 'image':
            self._handle_image_block(block, token_to_url, results)
        
        elif b_type == 'table':
            await self._handle_table_block(bid, block, block_map, token_to_url, results, visited)
            # 内部处理子节点
            return
        
        elif b_type == 'callout':
            await self._handle_callout_block(block, block_map, token_to_url, results, visited)
            # 内部处理子节点
            return
        
        elif b_type == 'quote':
            self._handle_quote_block(block, results)
            # quote 通常只包含文本，如果它有子节点（某些版本），这里会继续递归
        
        elif b_type == 'divider':
            results.append({'type': 'divider', 'content': {}})
        
        elif any(kw in b_type.lower() for kw in ['sheet', 'bitable', 'whiteboard', 'mindmap', 'diagram', 'grid', 'diagram-block', 'board', 'canvas', 'diagram-v2', 'mindmap-v2', 'table-v2', 'chart']):
            self._handle_complex_block(bid, block, token_to_url, results)
            
        elif b_type == 'table_cell':
            # table_cell 本身不产生输出，递归处理子节点
            pass
    
        # 递归处理子节点
        # 注意：复杂块（已处理为截图）不应再递归以免内容重复
        complex_keywords = ['sheet', 'bitable', 'whiteboard', 'mindmap', 'diagram', 'grid', 'diagram-block', 'board', 'canvas', 'diagram-v2', 'mindmap-v2', 'table-v2', 'chart']
        if b_type not in (['table', 'callout'] + complex_keywords) and not any(kw in b_type.lower() for kw in complex_keywords):
            for cbid in children:
                await self._parse_block_recursive(cbid, block_map, token_to_url, results, visited)

            # 调试用：为新产生的块打上 ID 标签
            if len(results) > results_len_before:
                for i in range(results_len_before, len(results)):
                    if isinstance(results[i], dict) and 'id' not in results[i]:
                        results[i]['id'] = bid
    
    def _handle_text_block(self, block: Dict, results: List[Dict]):
        """处理文本块"""
        text = self._extract_text(block)
        if text:
            b_data = block.get('data', {})
            style = {}
            if b_data.get('align'):
                style['text-align'] = b_data.get('align')
            
            results.append({
                'type': 'text', 
                'content': {
                    'text': text,
                    'style': style
                }
            })

    def _handle_heading_block(self, block: Dict, b_type: str, results: List[Dict]):
        """处理标题块 (高保真版：包含对齐等样式)"""
        text = self._extract_text(block)
        if text:
            b_data = block.get('data', {})
            style = {}
            if b_data.get('align'):
                style['text-align'] = b_data.get('align')
            
            # 提取标题级别
            level = 1
            match = re.search(r'heading(\d+)', b_type)
            if match:
                level = min(int(match.group(1)), 6)
                
            results.append({
                'type': 'heading', 
                'content': {
                    'level': level, 
                    'text': text,
                    'style': style
                }
            })

    def _handle_list_block(self, block: Dict, b_type: str, results: List[Dict]):
        """处理列表块"""
        text = self._extract_text(block)
        if text:
            results.append({
                'type': 'list',
                'content': {
                    'ordered': b_type == 'ordered',
                    'items': [{'text': text}]
                }
            })

    def _handle_code_block(self, block: Dict, results: List[Dict]):
        """处理代码块"""
        b_data = block.get('data', {})
        code = self._extract_text(block, plain=True)
        language = b_data.get('language', 'text')
        
        if code:
            # 改进语言识别
            language = language.lower() if language else 'text'
            # 飞书有时候会把 bash 识别为 sql，尝试简单校正
            if language == 'sql' and ('npm ' in code or 'curl ' in code or 'bash ' in code or '| bash' in code):
                language = 'bash'
            
            results.append({
                'type': 'code',
                'content': {
                    'code': code.strip(),
                    'language': language
                }
            })

    def _handle_image_block(self, block: Dict, token_to_url: Dict[str, str], results: List[Dict]):
        """处理图片块"""
        b_data = block.get('data', {})
        
        # 尝试多种路径获取 token
        token = (
            b_data.get('token') or
            b_data.get('file_token') or
            b_data.get('image', {}).get('token')
        )
        
        # 查找对应的本地 URL
        url = self._find_resource_url(token, token_to_url)
        
        if url:
            img_data = b_data.get('image', {})
            style = {}
            if b_data.get('align'):
                style['text-align'] = b_data.get('align')
            
            results.append({
                'type': 'image',
                'content': {
                    'url': url,
                    'alt': 'Image',
                    'width': img_data.get('width'),
                    'height': img_data.get('height'),
                    'align': b_data.get('align', 'left'),
                    'style': style
                }
            })
        else:
            logger.warning(f"⚠️ 图片未找到: token={token}")

    async def _handle_table_block(
        self,
        bid: str,
        block: Dict,
        block_map: Dict,
        token_to_url: Dict[str, str],
        results: List[Dict],
        visited: set
    ):
        """处理二维表格块"""
        b_data = block.get('data', {})
        t_data = b_data.get('table', {}) or b_data
        
        rows_id = t_data.get('rows_id', [])
        cols_id = t_data.get('columns_id', [])
        cells_map = t_data.get('cell_set') or t_data.get('cells', {})
        
        if not rows_id or not cols_id or not cells_map:
            logger.debug(f"表格数据不完整: bid={bid}")
            return
        
        table_rows = []
        
        for r_id in rows_id:
            current_row = []
            for c_id in cols_id:
                # 尝试多种 key 格式
                cell_key = f"{r_id}{c_id}"
                cell_info = cells_map.get(cell_key)
                if not cell_info:
                    # 某些版本直接使用拼接，某些可能有分隔符（虽然目前观测到是 rowXXXcolYYY 这种大组合）
                    # 注入逻辑已经匹配了原始 key，所以这里保持灵活
                    pass
                
                cell_info = cell_info or {}
                
                # 提取单元格内的块 ID
                cell_bids = []
                if cell_info.get('block_id'):
                    cell_bids.append(cell_info.get('block_id'))
                elif cell_info.get('block_ids'):
                    cell_bids.extend(cell_info.get('block_ids'))
                
                cell_content = []
                for cbid in cell_bids:
                    # 递归解析单元格内容
                    await self._parse_block_recursive(cbid, block_map, token_to_url, cell_content, visited)
                
                # 提取样式
                cell_style = {}
                c_style = cell_info.get('style', {})
                if c_style.get('background_color'):
                    cell_style['background-color'] = c_style.get('background_color')
                
                current_row.append({
                    'content': cell_content,
                    'style': cell_style,
                    'is_header': cell_info.get('is_header', False)
                })
            
            table_rows.append({'cells': current_row, 'style': {}})
        
        if table_rows:
            results.append({
                'type': 'table',
                'content': {
                    'rows': table_rows,
                    'style': {}
                }
            })
            logger.info(f"📊 解析表格: {len(table_rows)} 行 x {len(cols_id)} 列")

    async def _handle_callout_block(
        self,
        block: Dict,
        block_map: Dict,
        token_to_url: Dict[str, str],
        results: List[Dict],
        visited: set
    ):
        """处理提示/引用块 - 包含其子内容"""
        b_data = block.get('data', {})
        
        # 收集 callout 内部的子内容
        children_content = []
        children = b_data.get('children', [])
        for cbid in children:
            await self._parse_block_recursive(cbid, block_map, token_to_url, children_content, visited)
        
        # 获取背景色（支持多种格式）
        bg_color = (
            b_data.get('background_color_theme') or
            b_data.get('background_color') or
            'blue'
        )
        
        results.append({
            'type': 'callout',
            'content': {
                'children': children_content,
                'emoji': b_data.get('emoji_id') or b_data.get('emoji_value') or '💡',
                'background_color': bg_color
            }
        })

    def _handle_quote_block(self, block: Dict, results: List[Dict]):
        """处理引用块"""
        text = self._extract_text(block)
        if text:
            results.append({'type': 'quote', 'content': {'text': text}})

    def _handle_complex_block(self, bid: str, block: Dict, token_to_url: Dict[str, str], results: List[Dict]):
        """处理复杂组件（电子表格、白板、脑图等）- 增强版 V3.0
        
        改进：分离 sheet 和 board 类型匹配，支持新的 crawler 输出格式
        """
        # 飞书不同版本的 block 数据可能在 data, block_data 或 payload 下
        b_data = block.get('data') or block.get('block_data') or block.get('payload', {})
        b_type = str(b_data.get('type') or block.get('type') or 'unknown').lower()
        
        # 统一映射类型 (Wiki 数字类型兼容)
        type_map = {
            '15': 'sheet', '16': 'bitable', '17': 'mindmap', 
            '18': 'diagram', '24': 'whiteboard', '28': 'diagram'
        }
        b_type = type_map.get(b_type, b_type)

        # 确定显示类型和对应的文件前缀
        display_type = 'whiteboard'
        file_prefix = 'complex_board_'  # 默认使用 board 前缀
        
        if any(kw in b_type for kw in ['sheet', 'table', 'bitable']):
            display_type = 'sheet'
            file_prefix = 'complex_sheet_'
        elif any(kw in b_type for kw in ['mindmap', 'mind_map']):
            display_type = 'mindmap'
            file_prefix = 'complex_board_'  # mindmap 使用 board 前缀
        elif any(kw in b_type for kw in ['diagram', 'chart', 'processchart', 'uml']):
            display_type = 'diagram'
            file_prefix = 'complex_board_'
        
        # 初始化分类计数器（分别跟踪 sheet 和 board）
        if not hasattr(self, '_sheet_counter'):
            self._sheet_counter = 0
        if not hasattr(self, '_board_counter'):
            self._board_counter = 0
        
        # 根据类型递增相应计数器
        if display_type == 'sheet':
            component_index = self._sheet_counter
            self._sheet_counter += 1
        else:
            component_index = self._board_counter
            self._board_counter += 1
            
        url = None
        
        # 1. 直接通过 BID 精确匹配
        url = token_to_url.get(bid) or token_to_url.get(f"{bid}_vp")
        
        # 2. BID 前缀/后缀匹配（处理 block ID 变体）
        if not url and bid:
            bid_short = bid[:16] if len(bid) > 16 else bid
            for key, val in token_to_url.items():
                if isinstance(val, str) and bid_short in val:
                    url = val
                    logger.info(f"📍 BID前缀匹配成功: {bid_short} -> {val}")
                    break
        
        # 3. 深入数据结构寻找 token
        if not url:
            all_possible_tokens = []
            def collect_tokens(obj):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if isinstance(v, str) and (len(v) >= 15 or (v.startswith('V-') and len(v) > 10)):
                            all_possible_tokens.append(v)
                        collect_tokens(v)
                elif isinstance(obj, list):
                    for item in obj: collect_tokens(item)
            
            collect_tokens(block)
            
            for t in all_possible_tokens:
                url = self._find_resource_url(t, token_to_url)
                if url: break
        
        # 4. 基于类型的顺序匹配（优先策略 - 兼容 V14.0 序列号）
        if not url:
            # 收集所有匹配当前类型的图片
            type_matched_files = []
            for key, val in token_to_url.items():
                if isinstance(val, str) and file_prefix in val:
                    type_matched_files.append(val)
            
            # 按文件名排序（V14.0 使用了 001, 002 前缀，排序即为顺序）
            type_matched_files = sorted(set(type_matched_files))
            
            if component_index < len(type_matched_files):
                url = type_matched_files[component_index]
                logger.info(f"📍 类型顺序匹配成功: {display_type}#{component_index} -> {url}")
        
        # 5. 模糊匹配 (ID 包含关系)
        if not url:
            clean_bid = bid.replace('block-', '').replace('docx-', '').replace('B-', '').replace('B_', '').replace('G-', '')
            core_id = clean_bid[-12:] if len(clean_bid) > 12 else clean_bid
            
            for key in token_to_url:
                s_key = str(key)
                if (bid in s_key or s_key in bid or 
                    clean_bid in s_key or s_key.startswith(clean_bid) or
                    core_id in s_key or s_key.endswith(core_id)):
                    url = token_to_url[key]
                    logger.info(f"📍 模糊匹配成功: {core_id} -> {url}")
                    break
        
        # 6. 全局兜底：从所有 complex 文件中按全局索引匹配
        if not url:
            if not hasattr(self, '_global_complex_counter'):
                self._global_complex_counter = 0
            global_index = self._global_complex_counter
            self._global_complex_counter += 1
            
            all_complex_files = sorted(set(
                v for k, v in token_to_url.items() 
                if isinstance(v, str) and ('complex_sheet_' in v or 'complex_board_' in v)
            ))
            
            if global_index < len(all_complex_files):
                url = all_complex_files[global_index]
                logger.info(f"📍 全局顺序匹配成功: {bid} -> {url}")
            else:
                # 最后的最后：如果还有任何未使用的 complex 文件，尝试捡漏
                unused_complex = [v for k, v in token_to_url.items() 
                                 if isinstance(v, str) and ('complex_' in v) and v not in results]
                if unused_complex:
                    url = unused_complex[0]
                    logger.info(f"📍 兜底捡漏匹配成功: {bid} -> {url}")

        title = b_data.get('name') or b_data.get('title') or f"飞书{b_type.capitalize()}"
        
        if url:
            results.append({
                'id': bid,
                'type': display_type,
                'bid': bid,
                'title': title,
                'b_type': b_type,
                'content': {
                    'bid': bid,
                    'title': title,
                    'preview': url,
                    'b_type': b_type
                }
            })
            logger.info(f"✅ 复杂组件映射成功: type={display_type}, bid={bid[:20] if bid else 'N/A'}...")
        else:
            logger.warning(f"⚠️ 复杂组件无预览: type={b_type}, bid={bid}")
            results.append({
                'id': bid,
                'type': display_type,
                'bid': bid,
                'title': f"[暂无预览] {title}",
                'b_type': b_type,
                'is_missing': True,
                'content': {
                    'bid': bid,
                    'title': f"[暂无预览] {title}",
                    'b_type': b_type,
                    'is_missing': True
                }
            })

    def _extract_text(self, block: Dict, plain: bool = False) -> str:
        """
        从飞书块中提取文本内容
        支持多种数据格式
        """
        b_data = block.get('data', {})
        
        # 路径1: attributedString（最常见）
        text_obj = b_data.get('text', {})
        ast = (
            text_obj.get('initial_attributedString') or
            text_obj.get('base_attributedString') or
            text_obj.get('attributedString')
        )
        
        if not ast:
            # 尝试 content 路径
            content_obj = b_data.get('content', {})
            ast = content_obj.get('initial_attributedString')
        
        if ast:
            text = ast.get('text', '')
            if plain:
                return text.strip()
            
            # 应用富文本样式
            return self._apply_text_styles(text, ast.get('attributes', []))
        
        # 路径2: initialAttributedTexts（Wiki 格式）
        iat = text_obj.get('initialAttributedTexts', {})
        if iat and 'text' in iat:
            t_obj = iat['text']
            attribs_obj = iat.get('attribs', {})
            apool = text_obj.get('apool', {})
            
            full_text = ""
            if isinstance(t_obj, dict):
                keys = sorted(t_obj.keys(), key=lambda x: int(x) if x.isdigit() else 0)
                full_text = ''.join(str(t_obj[k]) for k in keys)
            else:
                full_text = str(iat['text'])

            if plain or not attribs_obj or not apool:
                return full_text.strip()
            
            # 解析 Wiki 样式的 attributes
            attributes = self._parse_wiki_attribs(attribs_obj, apool)
            return self._apply_text_styles(full_text, attributes)
        
        # 路径3: 简单文本字段
        if isinstance(text_obj, str):
            return text_obj.strip()
        
        return ""

    def _apply_text_styles(self, text: str, attributes: List[Dict]) -> str:
        """将飞书的 attributes 转换为 HTML 标签"""
        if not attributes or not text:
            return text
        
        # 收集所有标记点
        marks = []
        for attr in attributes:
            start = attr.get('location', 0)
            length = attr.get('length', 0)
            end = start + length
            style = attr.get('style', {})
            
            if style.get('bold'):
                marks.append((start, '<b>', 10))
                marks.append((end, '</b>', -10))
            if style.get('italic'):
                marks.append((start, '<i>', 9))
                marks.append((end, '</i>', -9))
            if style.get('underline'):
                marks.append((start, '<u>', 8))
                marks.append((end, '</u>', -8))
            if style.get('strike'):
                marks.append((start, '<s>', 7))
                marks.append((end, '</s>', -7))
            if style.get('link'):
                url = style['link'].get('url', '#')
                marks.append((start, f'<a href="{url}" target="_blank">', 6))
                marks.append((end, '</a>', -6))
            if style.get('code'):
                marks.append((start, '<code>', 5))
                marks.append((end, '</code>', -5))
            
            # 处理颜色和高亮
            inline_style = []
            if style.get('text_color'):
                inline_style.append(f"color: {style['text_color']}")
            if style.get('background_color'):
                inline_style.append(f"background-color: {style['background_color']}")
            if style.get('font_size'):
                # 兼容不同单位
                fs = str(style['font_size'])
                if fs.isdigit(): fs += 'px'
                inline_style.append(f"font-size: {fs}")
            if style.get('font_weight'):
                inline_style.append(f"font-weight: {style['font_weight']}")
            if style.get('align'):
                inline_style.append(f"text-align: {style['align']}")
            if style.get('line_height'):
                inline_style.append(f"line-height: {style['line_height']}")
            
            if inline_style:
                style_str = "; ".join(inline_style)
                marks.append((start, f'<span style="{style_str}">', 4))
                marks.append((end, '</span>', -4))
        
        # 按位置排序（同位置时，结束标签优先）
        marks.sort(key=lambda x: (x[0], x[2]))
        
        # 构建结果
        result = ""
        last_idx = 0
        for pos, tag, _ in marks:
            # 转换换行符为 <br/> 以保证飞书文档内的换行一致 (图1/图3 需求)
            segment = text[last_idx:pos].replace('\n', '<br/>')
            result += segment
            result += tag
            last_idx = pos
        result += text[last_idx:].replace('\n', '<br/>')
        
        return result

    def _parse_wiki_attribs(self, attribs_obj: Dict, apool: Dict) -> List[Dict]:
        """解析 Wiki 格式的属性字符串 (e.g., *0*1+7)"""
        results = []
        num_to_attrib = apool.get('numToAttrib', {})
        
        current_location = 0
        # 飞书 Wiki 的 attribs 通常是以索引为 key 的字典，例如 {"0": "*0*1+7*0+5"}
        # 我们按顺序合并它们
        sorted_keys = sorted(attribs_obj.keys(), key=lambda x: int(x) if x.isdigit() else 0)
        full_attrib_str = ''.join(attribs_obj[k] for k in sorted_keys)
        
        # 简单的正则解析: (*N)* (+L)
        # 格式可能是 *0*1+5*2+3...
        # *(\d+) 表示属性索引，+(\w+) 表示长度（通常是 36 进制或 10 进制，这里简单处理）
        import re
        parts = re.findall(r'(\*\d+|\+\w+)', full_attrib_str)
        
        active_styles = {}
        for part in parts:
            if part.startswith('*'):
                idx = part[1:]
                attr_pair = num_to_attrib.get(idx, [])
                if len(attr_pair) >= 2:
                    key, val = attr_pair[0], attr_pair[1]
                    # 映射到标准 style 键名
                    if key == 'bold' and val == 'true': active_styles['bold'] = True
                    elif key == 'italic' and val == 'true': active_styles['italic'] = True
                    elif key == 'underline' and val == 'true': active_styles['underline'] = True
                    elif key == 'strike' and val == 'true': active_styles['strike'] = True
                    elif key == 'inlineCode' and val == 'true': active_styles['code'] = True
                    elif key == 'textHighlight': active_styles['background_color'] = val
                    elif key == 'textColor': active_styles['text_color'] = val
                    elif key == 'fontSize': active_styles['font_size'] = val
                    elif key == 'fontWeight': active_styles['font_weight'] = val
                    elif key == 'link': active_styles['link'] = {'url': val}
            elif part.startswith('+'):
                # 长度解析（飞书使用 base36）
                try:
                    length_str = part[1:]
                    length = int(length_str, 36)
                except:
                    length = 0
                
                if length > 0 and active_styles:
                    results.append({
                        'location': current_location,
                        'length': length,
                        'style': active_styles.copy()
                    })
                
                current_location += length
                # 长度段结束后，属性通常会重置或变更，但在 Wiki 格式中，*N 是累加的直到遇到下一个长度段前的变更
                # 这里我们假设每个 + 段是一个独立的样式应用
                active_styles = {} 
        
        return results

    def _find_resource_url(self, token: Optional[str], token_to_url: Dict[str, str]) -> Optional[str]:
        """在资源映射中查找 URL，增加鲁棒性"""
        if not token:
            return None
        
        # 1. 精确匹配
        if token in token_to_url:
            return token_to_url[token]
        
        # 2. 归一化匹配：处理 block- 前缀差异
        norm_token = token.replace('block-', '')
        if norm_token in token_to_url:
            return token_to_url[norm_token]
        
        # 3. 模糊匹配：key 包含 token 或 token 包含 key
        for key, url in token_to_url.items():
            if norm_token in str(key) or str(key) in norm_token:
                return url
        
        # 4. 解码尝试
        from urllib.parse import unquote
        decoded_token = unquote(token)
        if decoded_token in token_to_url:
            return token_to_url[decoded_token]
            
        return None

    async def _process_resources(
        self,
        block_map: Dict,
        images_data: Dict,
        source_url: str,
        cookies: Optional[Dict]
    ) -> Dict[str, str]:
        """
        处理所有资源
        1. 扫描 block_map 中的所有 token
        2. 从 images_data 中恢复资源
        3. 尝试下载缺失的资源
        """
        # 收集所有 token (设置 is_top_level=True 以捕获 block_map keys)
        tokens = set()
        self._scan_tokens(block_map, tokens, is_top_level=True)
        
        # 增加缓存，防止重复处理
        processed_tokens = set()
        token_to_url = {}
        
        # 0. 预处理：记录所有 bid 列表以便快速查重
        all_bids = set()
        for k, v in block_map.items():
            if isinstance(v, dict) and (v.get('id') or v.get('block_id')):
                all_bids.add(v.get('id') or v.get('block_id'))

        # 1. 优先处理并保存 images_data (这是 crawler 截图捕获的成品)
        if images_data:
            for key, res_val in images_data.items():
                if key in processed_tokens: continue
                t, url = await self._save_crawled_resource(key, res_val)
                if url:
                    token_to_url[key] = url
                    processed_tokens.add(key)
        
        # 2. 处理剩余 tokens
        tasks = []
        # 快速合并所有待处理 token
        all_pending_tokens = tokens.union(set(images_data.keys()) if images_data else set())
        
        for token in all_pending_tokens:
            if token in processed_tokens or token in token_to_url:
                continue
            
            # 强化匹配：搜索 images_data 中的模糊对应关系
            found_uri = None
            if images_data:
                if token in images_data:
                    found_uri = images_data[token]
                else:
                    # 模糊匹配：比如 token=123, images_data={block-123: ...}
                    for k, v in images_data.items():
                        if token in k or k in token:
                            found_uri = v
                            break
            
            if found_uri:
                tasks.append(self._save_crawled_resource(token, found_uri))
            else:
                # 尝试下载
                tasks.append(self._download_resource(token, source_url, cookies))
        
        if tasks:
            # 并行处理，提高速度
            results = await asyncio.gather(*tasks)
            for t, url in results:
                if url:
                    token_to_url[t] = url
        
        return token_to_url

    def _scan_tokens(self, obj: Any, tokens: set, is_top_level: bool = False):
        """递归扫描对象中的所有 token 和 复杂块 ID"""
        if isinstance(obj, dict):
            # 如果是顶级 block_map，直接将所有 key 列为潜在 token
            if is_top_level:
                for bid in obj.keys():
                    if isinstance(bid, str) and len(bid) > 10:
                        tokens.add(bid)

            # 获取 ID 和 Type 以识别复杂块
            b_id = obj.get('id') or obj.get('record_id')
            b_data = obj.get('data', {}) if isinstance(obj.get('data'), dict) else {}
            type_val = b_data.get('type') or obj.get('type', '')
            
            # 映射数字类型
            type_map = {15: 'sheet', 16: 'bitable', 17: 'mindmap', 18: 'diagram', 24: 'whiteboard', 28: 'diagram'}
            b_type = str(type_map.get(type_val, type_val)).lower()
            
            # 如果是复杂块，将其 ID 加入 tokens 集合
            complex_keywords = ['sheet', 'bitable', 'whiteboard', 'mindmap', 'diagram', 'grid', 'board', 'canvas', 'spreadsheet']
            if any(k in b_type for k in complex_keywords):
                if b_id: tokens.add(b_id)
            elif b_id and any(kw in str(obj).lower() for kw in complex_keywords):
                if b_id: tokens.add(b_id)

            for k, v in obj.items():
                if k in ['token', 'file_token', 'obj_token', 'record_id'] and isinstance(v, str) and len(v) > 10:
                    tokens.add(v)
                self._scan_tokens(v, tokens, is_top_level=False)
        elif isinstance(obj, list):
            for item in obj:
                self._scan_tokens(item, tokens, is_top_level=False)

    async def _save_crawled_resource(self, token: str, resource_data: str) -> tuple:
        """
        保存抓取到的资源。
        resource_data 可以是 Base64 Data URI，也可以是本地磁盘路径。
        """
        try:
            # 1. 处理磁盘路径 (来自 crawler 的 temp_crawl_dir)
            if os.path.exists(resource_data) and not resource_data.startswith('data:'):
                orig_filename = os.path.basename(resource_data)
                ext = resource_data.split('.')[-1] or 'png'
                
                # 如果是复杂组件（带有前缀），保留原始文件名以支持顺序匹配
                if 'complex_sheet_' in orig_filename or 'complex_board_' in orig_filename:
                    filename = orig_filename
                else:
                    file_hash = hashlib.md5(token.encode()).hexdigest()
                    filename = f"{file_hash}.{ext}"
                
                filepath = os.path.join(self.current_abs_path, filename)
                
                # 移动或复制文件
                import shutil
                try:
                    shutil.copy2(resource_data, filepath)
                    logger.debug(f"✅ 复制图片文件: {filename}")
                except Exception as e:
                    logger.warning(f"复制文件失败: {e}")
                    return (token, None)
                    
                return (token, f"/uploads/{self.current_rel_path}/{filename}")

            # 2. 处理 Base64
            if 'base64,' not in resource_data:
                return (token, None)
            
            _, b64_data = resource_data.split('base64,', 1)
            content = base64.b64decode(b64_data)
            
            # 确定文件扩展名
            ext = 'png'
            if resource_data.startswith('data:image/'):
                ext = resource_data.split('/')[1].split(';')[0]
                if ext not in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
                    ext = 'png'
            
            # 生成文件名
            file_hash = hashlib.md5(token.encode()).hexdigest()
            filename = f"{file_hash}.{ext}"
            filepath = os.path.join(self.current_abs_path, filename)
            
            async with aiofiles.open(filepath, 'wb') as f:
                await f.write(content)
            
            return (token, f"/uploads/{self.current_rel_path}/{filename}")
            
        except Exception as e:
            logger.debug(f"保存抓取资源失败: {token}, {e}")
            return (token, None)

    async def _download_resource(self, token: str, source_url: str, cookies: Optional[Dict]) -> tuple:
        """从飞书服务器下载资源"""
        if len(token) < 15:  # 太短的不是有效 token
            return (token, None)
        
        parsed = urlparse(source_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        
        # 飞书的资源下载端点
        endpoints = [
            f"{base}/space/api/box/stream/download/all/{token}/",
            f"{base}/space/api/box/stream/download/v2/cover/{token}/",
            f"{base}/drive/api/box/stream/download/all/{token}/",
        ]
        
        async with httpx.AsyncClient(verify=False, timeout=15.0, cookies=cookies) as client:
            client.headers['Referer'] = source_url
            client.headers['User-Agent'] = self.headers['User-Agent']
            
            for url in endpoints:
                try:
                    resp = await client.get(url, follow_redirects=True)
                    if resp.status_code == 200:
                        ctype = resp.headers.get('content-type', '')
                        if 'text/html' in ctype or 'application/json' in ctype:
                            continue
                        
                        # 保存文件
                        ext = ctype.split('/')[-1].split(';')[0] or 'png'
                        file_hash = hashlib.md5(token.encode()).hexdigest()
                        filename = f"{file_hash}.{ext}"
                        filepath = os.path.join(self.current_abs_path, filename)
                        
                        async with aiofiles.open(filepath, 'wb') as f:
                            await f.write(resp.content)
                        
                        return (token, f"/uploads/{self.current_rel_path}/{filename}")
                        
                except Exception as e:
                    logger.debug(f"下载失败: {url}, {e}")
                    continue
        
        return (token, None)

    def _generate_summary(self, content_blocks: List[Dict], article_title: str = "") -> str:
        """从内容块中通过语义合成核心摘要 (非单纯截取版)"""
        if not content_blocks:
            return ""

        # 1. 提取要素：标题、一级/二级标题、结论段落
        title = article_title
        headings = []
        conclusion_text = ""
        all_texts = []

        for i, block in enumerate(content_blocks):
            # 获取纯文本
            text = re.sub(r'<[^>]+>', '', block['content'].get('text', '')).strip()
            if not text: continue
            
            if block['type'] == 'heading':
                if not title: title = text
                if block['content'].get('level', 0) <= 2:
                    headings.append(text)
            
            if block['type'] == 'text':
                all_texts.append(text)
                # 寻找结论词
                if any(kw in text.lower() for kw in ['总结', '结论', '核心', '综上所述', '综上', '总之', '最后', 'conclusion', 'summary']):
                    conclusion_text = text

        # 2. 精简要素
        # 提取关键词：从标题中提取前 3-4 个核心词（简单按长度或常见字符）
        key_keywords = []
        for h in headings:
            # 过滤掉太短或包含总结字样的标题
            if 2 < len(h) < 20 and not any(kw in h for kw in ['总结', '结论']):
                key_keywords.append(h)
        key_keywords = list(dict.fromkeys(key_keywords))[:3] # 去重并取前3

        # 如果没有找到明确的结论段落，取文章最后一段
        if not conclusion_text and all_texts:
            conclusion_text = all_texts[-1]

        # 3. 模版合成
        if title and key_keywords:
            keywords_str = "、".join(key_keywords)
            # 抽取结论的前两句
            sentences = re.split(r'[。！？.!?]', conclusion_text)
            final_point = sentences[0] if sentences else conclusion_text
            
            summary = f"本文深度剖析了《{title}》的核心脉络，重点围绕“{keywords_str}”等核心环节展开深度探讨，最终指出“{final_point}”，为读者提供了极具价值的技术洞察。"
        elif all_texts:
            # 退化逻辑：如果缺乏结构，则使用改进的首尾逻辑
            head = all_texts[0][:60]
            tail = all_texts[-1][:60]
            summary = f"文章针对相关领域进行了系统阐述，从“{head}...”切入，并最终归纳得出“...{tail}”的核心结论，旨在帮助读者构建完整的知识框架。"
        else:
            summary = title or "该文章内容丰富，涵盖了多个层面的专业见解与深度分析。"

        return summary[:250].strip()

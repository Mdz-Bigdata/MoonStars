import os
import sys
import json
import logging
import asyncio
import random
import tempfile
import re
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional, Dict, Tuple, Callable
from urllib.parse import unquote

import lark_oapi as lark
from lark_oapi.api.docx.v1 import ListDocumentBlockRequest, ListDocumentBlockResponse, GetDocumentRequest, GetDocumentResponse
from lark_oapi.api.drive.v1 import DownloadMediaRequest, DownloadMediaResponse
from lark_oapi.api.wiki.v2 import GetNodeSpaceRequest, GetNodeSpaceResponse, Node
from lark_oapi.api.bitable.v1 import ListAppTableRequest, ListAppTableResponse, SearchAppTableRecordRequest, SearchAppTableRecordRequestBody, SearchAppTableRecordResponse
from lark_oapi.api.sheets.v3 import QuerySpreadsheetSheetRequest, QuerySpreadsheetSheetResponse
from lark_oapi.api.board.v1 import DownloadAsImageWhiteboardRequest, DownloadAsImageWhiteboardResponse
from lark_oapi.core.token import TokenManager

from app.core.config import settings

logger = logging.getLogger(__name__)

# ==============================================================================
# Constants & Models
# ==============================================================================

class BlockType:
    PAGE = 1
    TEXT = 2
    HEADING1 = 3
    HEADING2 = 4
    HEADING3 = 5
    HEADING4 = 6
    HEADING5 = 7
    HEADING6 = 8
    HEADING7 = 9
    HEADING8 = 10
    HEADING9 = 11
    BULLET = 12
    ORDERED = 13
    CODE = 14
    QUOTE = 15
    TODO = 16
    BITABLE = 17
    CALLOUT = 18
    DIVIDER = 19
    FILE = 20
    GRID = 21
    GRID_COLUMN = 22
    IMAGE = 27 # Discovered in Wiki Docs, was 23
    LEGACY_IMAGE = 23
    MINDNOTE = 26
    SHEET = 28 # Was 27
    TABLE = 31 # Was 28
    TABLE_CELL = 32 # Was 29
    VIEWGROUP = 30
    QUOTE_CONTAINER = 31
    WIKI_CATALOG = 32
    BOARD = 43 # Discovered in Wiki Docs, was 33
    LEGACY_BOARD = 33
    DIAGRAM = 34
    UNDEFINED = 999

FEISHU_COLOR_MAP = {
    1: "#1F2329",
    2: "#2B2F36",
    3: "#646A73",
    4: "#8F959E",
    5: "#3370FF",
    6: "#F54A45",
    7: "#FF8F1F",
    8: "#FFC60A",
    9: "#00B578",
    10: "#722ED1",
}

# ==============================================================================
# Feishu SDK Wrapper
# ==============================================================================

class FeishuSDK:
    def __init__(self, temp_dir: Optional[Path] = None):
        self.client = (
            lark.Client.builder()
            .app_id(settings.FEISHU_APP_ID)
            .app_secret(settings.FEISHU_APP_SECRET)
            .enable_set_token(True)
            .timeout(60)
            .log_level(lark.LogLevel.ERROR)
            .build()
        )
        self.temp_dir = temp_dir or Path(tempfile.gettempdir()) / "feishu_docx"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    async def get_document_info(self, document_id: str, access_token: str) -> dict:
        def _get():
            request = GetDocumentRequest.builder().document_id(document_id).build()
            option = lark.RequestOption.builder().tenant_access_token(access_token).build()
            
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response: GetDocumentResponse = self.client.docx.v1.document.get(request, option)
                    if response.success():
                        doc = response.data.document
                        return {
                            "document_id": doc.document_id,
                            "revision_id": doc.revision_id,
                            "title": doc.title or document_id,
                        }
                    logger.warning(f"docx.v1.document.get attempt {attempt+1} failed: {response.msg}")
                except Exception as e:
                    logger.warning(f"docx.v1.document.get attempt {attempt+1} exception: {e}")
                
                if attempt < max_retries - 1:
                    time.sleep(1)
            
            return {"document_id": document_id, "title": document_id}
            
        return await asyncio.to_thread(_get)

    def _clean_token(self, token: str) -> str:
        """
        🛡️ 确保 Token 纯净。处理 Wiki 映射、URL 直接传入等复杂情况。
        """
        if not token:
            return ""
        
        # 如果传入的是完整 URL，尝试提取
        if "feishu.cn" in token or "larksuite.com" in token:
            for p in [r"docx/([a-zA-Z0-9_\-]+)", r"sheets/([a-zA-Z0-9_\-]+)", r"base/([a-zA-Z0-9_\-]+)", r"wiki/([a-zA-Z0-9_\-]+)"]:
                match = re.search(p, token)
                if match:
                    token = match.group(1)
                    break
        
        # 处理 Wiki 映射后缀 spreadsheetToken_sheetId
        if "_" in token:
            parts = token.split("_")
            if len(parts) == 2 and (len(parts[0]) > 20 or parts[0].startswith("sht")):
                logger.info(f"🧼 自动清理 Token: {token} -> {parts[0]}")
                return parts[0]
            else:
                logger.debug(f"ℹ️ Token 包含下划线但未触发清理逻辑: {token}")
                
        return token

    async def get_document_block_list(self, document_id: str, access_token: str) -> List[dict]:
        def _get_all():
            all_blocks = []
            page_token = None
            
            while True:
                request_builder = ListDocumentBlockRequest.builder().document_id(document_id).page_size(100)
                if page_token:
                    request_builder.page_token(page_token)
                
                request = request_builder.build()
                option = lark.RequestOption.builder().tenant_access_token(access_token).build()
                
                # Application-level retry for SSL/Network stability
                max_retries = 3
                response = None
                for attempt in range(max_retries):
                    try:
                        response = self.client.docx.v1.document_block.list(request, option)
                        if response.success():
                            break
                        logger.warning(f"docx.v1.document_block.list attempt {attempt+1} failed: {response.msg}")
                    except Exception as e:
                        logger.warning(f"docx.v1.document_block.list attempt {attempt+1} exception: {e}")
                    
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt) # Exponential backoff
                
                if not response or not response.success():
                    msg = response.msg if response else "Unknown error (SSL/Timeout)"
                    logger.error(f"docx.v1.document_block.list failed after {max_retries} attempts: {msg}")
                    raise RuntimeError(f"Failed to fetch document blocks: {msg}")
                
                data = json.loads(response.raw.content)
                items = data.get("data", {}).get("items", [])
                all_blocks.extend(items)
                
                page_token = data.get("data", {}).get("page_token")
                has_more = data.get("data", {}).get("has_more", False)
                
                if not has_more or not page_token:
                    break
                    
            return all_blocks
            
        return await asyncio.to_thread(_get_all)

    async def download_image(self, file_token: str, access_token: str, target_dir: Path) -> Optional[str]:
        def _do_download():
            request = DownloadMediaRequest.builder().file_token(file_token).build()
            option = lark.RequestOption.builder().tenant_access_token(access_token).build()
            
            max_retries = 10
            for attempt in range(max_retries):
                try:
                    response: DownloadMediaResponse = self.client.drive.v1.media.download(request, option)
                    if response.success():
                        extension = ".png"
                        file_path = target_dir / f"{file_token}{extension}"
                        file_path.write_bytes(response.file.read())
                        return str(file_path)
                    
                    # 💡 记录详细错误码以精准排查
                    code = getattr(response, "code", "Unknown")
                    msg = response.msg or "Empty message"
                    logger.warning(f"drive.v1.media.download attempt {attempt+1} failed for {file_token}: Code={code}, Msg={msg}")
                    
                    if code == 429 or "frequency limit" in msg.lower():
                        # 如果触发限流，使用更长的随机等待
                        wait_time = (5 * (2 ** attempt)) + (random.random() * 5)
                    else:
                        wait_time = (2 * (2 ** attempt)) + (random.random() * 2)
                        
                except Exception as e:
                    logger.warning(f"drive.v1.media.download attempt {attempt+1} exception for {file_token}: {e}")
                    wait_time = (3 * (2 ** attempt)) + (random.random() * 3)
                
                if attempt < max_retries - 1:
                    time.sleep(min(wait_time, 60))
            return None
            
        return await asyncio.to_thread(_do_download)

    async def get_whiteboard_as_image(self, whiteboard_id: str, access_token: str, target_dir: Path) -> Optional[str]:
        def _do_board():
            request = DownloadAsImageWhiteboardRequest.builder().whiteboard_id(whiteboard_id).build()
            option = lark.RequestOption.builder().tenant_access_token(access_token).build()
            
            max_retries = 10
            for attempt in range(max_retries):
                try:
                    response: DownloadAsImageWhiteboardResponse = self.client.board.v1.whiteboard.download_as_image(request, option)
                    if response.success():
                        file_path = target_dir / f"{whiteboard_id}.png"
                        file_path.write_bytes(response.file.read())
                        return str(file_path)
                    
                    code = getattr(response, "code", "Unknown")
                    msg = response.msg or "Empty message"
                    logger.warning(f"board.v1.whiteboard.download_as_image attempt {attempt+1} failed: Code={code}, Msg={msg}")
                    
                    if code == 429 or "frequency limit" in msg.lower():
                        wait_time = (5 * (2 ** attempt)) + (random.random() * 5)
                    else:
                        wait_time = (2 * (2 ** attempt)) + (random.random() * 2)

                except Exception as e:
                    logger.warning(f"board.v1.whiteboard.download_as_image attempt {attempt+1} exception: {e}")
                    wait_time = (3 * (2 ** attempt)) + (random.random() * 3)
                
                if attempt < max_retries - 1:
                    time.sleep(min(wait_time, 60))

            logger.error(f"board.v1.whiteboard.download_as_image failed after {max_retries} attempts")
            return None
            
        return await asyncio.to_thread(_do_board)

    def get_wiki_node_metadata(self, node_token: str, access_token: str) -> Optional[Node]:
        request = (
            GetNodeSpaceRequest.builder()
            .token(node_token)
            .obj_type("wiki")
            .build()
        )
        option = lark.RequestOption.builder().tenant_access_token(access_token).build()
        response: GetNodeSpaceResponse = self.client.wiki.v2.space.get_node(request, option)
        if not response.success():
            logger.error(f"wiki.v2.space.get_node failed: {response.msg}")
            return None
        return response.data.node

    def get_sheet_list(self, spreadsheet_token: str, access_token: str) -> Tuple[List[Any], str]:
        """返回 (sheets_list, working_token)"""
        variants = [spreadsheet_token]
        cleaned = self._clean_token(spreadsheet_token)
        if cleaned != spreadsheet_token:
            variants.append(cleaned)
            
        for v in variants:
            if not v or len(v) < 5: continue
            # 🚀 首先尝试 V3 接口
            try:
                request = QuerySpreadsheetSheetRequest.builder().spreadsheet_token(v).build()
                option = lark.RequestOption.builder().tenant_access_token(access_token).build()
                response: QuerySpreadsheetSheetResponse = self.client.sheets.v3.spreadsheet_sheet.query(request, option)
                if response.success():
                    logger.info(f"✅ sheets.v3 query success for {v}, found {len(response.data.sheets)} sheets")
                    return response.data.sheets, v
                
                # 🚀 备选：尝试 V2 接口 (部分旧表格或 Wiki 嵌入表格可能仅支持 V2)
                request_v2 = (
                    lark.BaseRequest.builder()
                    .http_method(lark.HttpMethod.GET)
                    .uri(f"/open-apis/sheets/v2/spreadsheets/{v}/metainfo")
                    .token_types({lark.AccessTokenType.TENANT})
                    .build()
                )
                response_v2 = self.client.request(request_v2, option)
                if response_v2.success():
                    data = json.loads(response_v2.raw.content).get("data", {})
                    sheets_v2 = data.get("sheets", [])
                    # 转换 V2 结构到类似 V3 的对象 (简单模拟)
                    class MockSheet:
                        def __init__(self, d):
                            self.sheet_id = d.get("sheetId")
                            self.title = d.get("title")
                            self.index = d.get("index")
                    
                    logger.info(f"✅ sheets.v2 metainfo success for {v}, found {len(sheets_v2)} sheets")
                    return [MockSheet(s) for s in sheets_v2], v

                if "not exist" in response.msg.lower() or "131002" in response.msg:
                    continue
            except Exception as e:
                logger.warning(f"⚠️ get_sheet_list attempt failed for {v}: {e}")
                continue
            
        logger.error(f"❌ sheets api query failed for {spreadsheet_token}")
        return [], spreadsheet_token

    def get_spreadsheet_metainfo(self, spreadsheet_token: str, access_token: str) -> Dict[str, Any]:
        """获取表格元数据，包含合并单元格信息"""
        variants = [spreadsheet_token]
        cleaned = self._clean_token(spreadsheet_token)
        if cleaned != spreadsheet_token:
            variants.append(cleaned)
            
        for v in variants:
            request = (
                lark.BaseRequest.builder()
                .http_method(lark.HttpMethod.GET)
                .uri(f"/open-apis/sheets/v2/spreadsheets/{v}/metainfo")
                .token_types({lark.AccessTokenType.TENANT})
                .build()
            )
            option = lark.RequestOption.builder().tenant_access_token(access_token).build()
            response = self.client.request(request, option)
            if response.success():
                return json.loads(response.raw.content).get("data", {})
            
            if "not exist" in response.msg.lower() or "131002" in response.msg:
                continue
                
        logger.error(f"❌ sheets.v2.metainfo failed for {spreadsheet_token}")
        return {}
    def get_sheet_values(self, spreadsheet_token: str, sheet_id: str, access_token: str) -> List[List[Any]]:
        # 🛡️ 针对 V2 接口也做 Token 容错
        variants = [spreadsheet_token]
        cleaned = self._clean_token(spreadsheet_token)
        if cleaned != spreadsheet_token:
            variants.append(cleaned)
            
        for v in variants:
            request = (
                lark.BaseRequest.builder()
                .http_method(lark.HttpMethod.GET)
                .uri(f"/open-apis/sheets/v2/spreadsheets/{v}/values/{sheet_id}")
                .token_types({lark.AccessTokenType.TENANT})
                .build()
            )
            option = lark.RequestOption.builder().tenant_access_token(access_token).build()
            response = self.client.request(request, option)
            if response.success():
                data = json.loads(response.raw.content)
                return data.get("data", {}).get("valueRange", {}).get("values", [])
            
            if "not exist" in response.msg.lower() or "131002" in response.msg:
                continue
                
        logger.error(f"❌ sheets.v2.values failed for {spreadsheet_token}")
        return []

    def get_spreadsheet_styles(self, spreadsheet_token: str, sheet_id: str, row_count: int, col_count: int, access_token: str) -> Dict[str, Any]:
        """批量获取单元格样式 (使用 V2 接口，优化传参方式)"""
        # 飞书列索引转字母 A, B, ..., Z, AA, AB, ...
        def col_to_letter(n):
            string = ""
            while n > 0:
                n, remainder = divmod(n - 1, 26)
                string = chr(65 + remainder) + string
            return string
            
        last_col = col_to_letter(col_count)
        
        # 🛡️ 兼容性处理：如果 sheet_id 已经带了引号，先去掉再统一加
        clean_sheet_id = sheet_id.strip("'").strip('"')
        range_str = f"'{clean_sheet_id}'!A1:{last_col}{row_count}"
        
        request = (
            lark.BaseRequest.builder()
            .http_method(lark.HttpMethod.GET)
            .uri(f"/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/styles_batch_get")
            .queries({"ranges": range_str}) # 🚀 使用 SDK 提供的 queries 方法，自动处理 URL 编码和路由
            .token_types({lark.AccessTokenType.TENANT})
            .build()
        )
        option = lark.RequestOption.builder().tenant_access_token(access_token).build()
        
        try:
            response = self.client.request(request, option)
            if response.success():
                return json.loads(response.raw.content).get("data", {})
            
            # 🚀 记录失败详情
            status_code = getattr(response, "status_code", "Unknown")
            error_body = "No body"
            if response.raw and response.raw.content:
                try: error_body = response.raw.content.decode()[:500]
                except: pass
            
            # 💡 某些 Wiki 嵌套表格可能无法通过此接口获取样式，记录为 info 级别避免刷屏
            if status_code == 404:
                logger.warning(f"⚠️ sheets.v2.styles_batch_get returned 404 (possibly restricted Wiki content). Token: {spreadsheet_token}, Range: {range_str}")
            else:
                logger.error(f"❌ sheets.v2.styles_batch_get failed for {spreadsheet_token}. Status: {status_code}, Range: {range_str}, Msg: {response.msg}, Body: {error_body}")
        except Exception as log_err:
            logger.error(f"❌ sheets.v2.styles_batch_get crashed: {log_err}")
            
        return {}




    def get_bitable_tables(self, app_token: str, access_token: str) -> List[Any]:
        variants = [app_token]
        cleaned = self._clean_token(app_token)
        if cleaned != app_token:
            variants.append(cleaned)
            
        for v in variants:
            request = ListAppTableRequest.builder().app_token(v).build()
            option = lark.RequestOption.builder().tenant_access_token(access_token).build()
            response: ListAppTableResponse = self.client.bitable.v1.app_table.list(request, option)
            if response.success():
                return response.data.items
            if "not exist" in response.msg.lower() or "131002" in response.msg:
                continue
                
        logger.error(f"❌ bitable.v1.app_table.list failed for {app_token}")
        return []

    def get_bitable_records(self, app_token: str, table_id: str, access_token: str) -> List[Dict[str, Any]]:
        variants = [app_token]
        cleaned = self._clean_token(app_token)
        if cleaned != app_token:
            variants.append(cleaned)
            
        for v in variants:
            if not v or len(v) < 5: continue
            all_items = []
            page_token = None
            success = True
            
            while True:
                # 💡 使用 search 接口配合 page_token 实现分页抓取，确保数据完整性
                rb = SearchAppTableRecordRequestBody.builder().page_size(100)
                if page_token:
                    rb.page_token(page_token)
                    
                request = (
                    SearchAppTableRecordRequest.builder()
                    .app_token(v)
                    .table_id(table_id)
                    .request_body(rb.build())
                    .build()
                )
                option = lark.RequestOption.builder().tenant_access_token(access_token).build()
                response: SearchAppTableRecordResponse = self.client.bitable.v1.app_table_record.search(request, option)
                
                if not response.success():
                    if "not exist" in response.msg.lower() or "131002" in response.msg:
                        success = False
                        break
                    logger.error(f"bitable.v1.app_table_record.search failed: {response.msg}")
                    break
                    
                if response.data.items:
                    all_items.extend(response.data.items)
                
                if not response.data.has_more:
                    break
                page_token = response.data.page_token
            
            if success:
                logger.info(f"📊 Bitable ({v}/{table_id}) 捕获完成，共 {len(all_items)} 条记录")
                return all_items
            
        logger.error(f"❌ bitable.v1.app_table_record.search failed for {app_token}")
        return []

    def get_tenant_access_token(self, app_id: str, app_secret: str) -> str:
        # Use TokenManager to handle token retrieval and caching automatically
        return TokenManager.get_self_tenant_token(self.client._config)

# ==============================================================================
# Document Parser
# ==============================================================================

class FeishuParser:
    def __init__(self, sdk: FeishuSDK, access_token: str, upload_dir: str):
        self.sdk = sdk
        self.access_token = access_token
        self.upload_dir = upload_dir
        self.blocks_map = {}
        self.blocks_map_normalized = {}
        self.root_block = None
        self.current_abs_path = None
        self.current_rel_path = None
        self.images_data = {}
        self.downloaded_images = {}
        self.processed_images = set()
        self.client_style_text = {}
        self.client_block_styles = {}
        self.last_ordered_count = 0

    async def parse_url(
        self,
        url: str,
        images_data: Optional[Dict] = None,
        client_vars_data: Optional[str] = None
    ) -> Dict[str, Any]:
        # 🚀 设置递归限制，防止超长/深嵌套文档解析崩溃
        sys.setrecursionlimit(3000)
        self.images_data = images_data or {}
        self.downloaded_images = {}
        self.processed_images = set()
        self._load_client_vars_styles(client_vars_data)
        info = self._identify_url_type(url)
        if not info:
            raise ValueError(f"Unsupported Feishu URL format: {url}")
        
        doc_type, token = info
        
        # Handle Wiki
        if doc_type == "wiki":
            node = self.sdk.get_wiki_node_metadata(token, self.access_token)
            if not node:
                raise ValueError(f"Wiki node not found: {token}")
            doc_type = node.obj_type
            token = node.obj_token
            title = node.title
            
            # 💡 飞书 Wiki 映射的 Sheet/Bitable Token 可能是 spreadsheetToken_sheetId 格式
            if "_" in token:
                parts = token.split("_")
                if len(parts) == 2 and len(parts[0]) > 20:
                    logger.info(f"📍 Wiki 节点 Token 自动转换: {token} -> {parts[0]}")
                    token = parts[0]
        else:
            title = await self._get_title(doc_type, token)

        self.current_title = title
        self.title_removed = False
        safe_title = re.sub(r'[\\/:*?"<>|]', '', title or "Untitled").strip()[:100]
        self.current_rel_path = f"feishu/{safe_title}"
        self.current_abs_path = Path(self.upload_dir) / self.current_rel_path
        self.current_abs_path.mkdir(parents=True, exist_ok=True)

        content_blocks = []
        try:
            if doc_type in ("docx", "doc"):
                await self._parse_docx(token, content_blocks)
            elif doc_type == "sheet":
                # 🛡️ 容错点：部分 Wiki 映射的 Sheet 实际上可能是 Bitable
                await self._parse_sheet(token, content_blocks)
                if not content_blocks or len(content_blocks) < 2: # 只有标题没有内容也算失败
                    logger.warning(f"⚠️ Sheet 解析内容不足，尝试作为 Bitable 解析: {token}")
                    await self._parse_bitable(token, content_blocks)
            elif doc_type == "bitable" or doc_type == "base":
                await self._parse_bitable(token, content_blocks)
            else:
                logger.error(f"Unsupported document type: {doc_type}")
        except Exception as e:
            logger.error(f"❌ API 解析执行异常: {e}", exc_info=True)

        # Post-process: merge consecutive list items
        content_blocks = self._merge_consecutive_lists(content_blocks)

        # Generate synthetic summary after content is parsed
        synthetic_summary = self._generate_synthetic_summary(content_blocks, title)

        return {
            'title': title,
            'summary': synthetic_summary,
            'content': content_blocks,
            'cover_image': next((b['content']['url'] for b in content_blocks if b['type'] == 'image'), None)
        }

    def _merge_consecutive_lists(self, blocks: List[Dict]) -> List[Dict]:
        """Merge adjacent list items of the same type and nesting level."""
        if not blocks:
            return []
            
        merged = []
        for block in blocks:
            if block['type'] == 'list':
                if merged and merged[-1]['type'] == 'list' and \
                   merged[-1]['content']['ordered'] == block['content']['ordered']:
                    # Consecutive list items of same type - merge
                    merged[-1]['content']['items'].extend(block['content']['items'])
                    continue
            merged.append(block)
        return merged

    def _generate_synthetic_summary(self, content_blocks: List[Dict], title: str) -> str:
        """Synthesize a core summary from headings and conclusions."""
        headings = []
        all_text = []
        conclusion = ""
        
        for b in content_blocks:
            if b['type'] == 'heading':
                text = re.sub(r'<[^>]+>', '', b['content']['text']).strip()
                if text: headings.append(text)
            elif b['type'] == 'text':
                text = re.sub(r'<[^>]+>', '', b['content']['text']).strip()
                if text:
                    all_text.append(text)
                    if any(kw in text for kw in ['总结', '结论', '总之', '综上']):
                        conclusion = text

        key_themes = "、".join(headings[:3]) if headings else title
        final_point = conclusion[:150] if conclusion else (all_text[-1][:150] if all_text else "暂无总结")
        
        return f"本文深度剖析了《{title}》的核心脉络，重点围绕“{key_themes}”等核心环节展开深度探讨，最终指出“{final_point}”，为读者提供了极具价值的技术洞察。"

    def _identify_url_type(self, url: str) -> Optional[Tuple[str, str]]:
        patterns = {
            "docx": r"docx/([a-zA-Z0-9_\-]+)",
            "sheet": r"sheets/([a-zA-Z0-9_\-]+)",
            "bitable": r"base/([a-zA-Z0-9_\-]+)",
            "wiki": r"wiki/([a-zA-Z0-9_\-]+)",
        }
        for doc_type, p in patterns.items():
            match = re.search(p, url)
            if match:
                return doc_type, match.group(1)
        return None

    async def _get_title(self, doc_type: str, token: str) -> str:
        try:
            if doc_type == "docx":
                info = await self.sdk.get_document_info(token, self.access_token)
                return info.get("title", token)
            # For other types, we could fetch metadata but title is often enough
            return token
        except:
            return token

    async def _parse_docx(self, document_id: str, results: List[Dict]):
        self.blocks_map.clear()
        self.blocks_map_normalized.clear()
        raw_blocks = await self.sdk.get_document_block_list(document_id, self.access_token)
        for rb in raw_blocks:
            bid = rb.get("block_id")
            if bid:
                self._register_block(bid, rb)
        
        self.root_block = next((b for b in self.blocks_map.values() if b.get("block_type") == BlockType.PAGE), None)
        if not self.root_block and raw_blocks:
            self.root_block = self.blocks_map[raw_blocks[0]["block_id"]]

        # 🚀 并行预取图片和复杂组件资源
        await self._prefetch_resources(raw_blocks)

        if self.root_block:
            await self._recursive_render_docx(self.root_block, results)

    async def _prefetch_resources(self, blocks: List[Dict]):
        """🚀 并行资源预取：提前扫描并下载所有可能需要的图片和附件（限流保护 + 错峰启动）"""
        tasks = []
        # 🔧 关键修复：使用 list 保持 token 顺序，避免与 download_results 错配
        tokens_ordered = []  # 有序列表，用于 zip
        tokens_seen_set = set()  # 集合，用于快速去重查询
        # 🛡️ 限制并发下载量。调整为 12 以提高速度。
        max_concurrent = 12
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def sem_download(coro, delay):
            # 💡 增加错峰启动延迟到 300ms，减少频率限制警告
            if delay > 0:
                await asyncio.sleep(delay)
            async with semaphore:
                return await coro

        task_idx = 0
        for block in blocks:
            bt = block.get("block_type")
            inferred_key = self._infer_payload_key(block)
            payload_key = inferred_key or self._get_payload_key(bt)
            b_data = block.get(payload_key, {}) if payload_key and isinstance(block.get(payload_key), dict) else {}
            
            token = b_data.get("token") or b_data.get("obj_token")
            if not token:
                continue
                
            if token in tokens_seen_set or token in self.downloaded_images:
                continue
            
            # 🔧 同时添加到有序列表和去重集合
            tokens_ordered.append(token)
            tokens_seen_set.add(token)
            
            # 💡 增加错峰启动间隔到 300ms，减少频率限制警告
            delay = (task_idx * 0.3) + (random.random() * 0.1)

            
            # 识别资源类型并加入下载队列 (使用 Semaphore 包装)
            if bt in (BlockType.IMAGE, BlockType.LEGACY_IMAGE) or payload_key == "image":
                tasks.append(sem_download(self.sdk.download_image(token, self.access_token, self.current_abs_path), delay))
                task_idx += 1
            elif bt in (BlockType.BOARD, BlockType.LEGACY_BOARD, BlockType.MINDNOTE) or payload_key in ("board", "mindnote"):
                tasks.append(sem_download(self.sdk.get_whiteboard_as_image(token, self.access_token, self.current_abs_path), delay))
                task_idx += 1
                
        if tasks:
            logger.info(f"🚀 启动并行资源预取 (并发限制: {max_concurrent}, 开启 300ms 错峰启动)，共 {len(tasks)} 个任务...")
            download_results = await asyncio.gather(*tasks, return_exceptions=True)
            # 🔧 使用有序的 tokens_ordered 进行 zip，确保顺序正确
            for token, res in zip(tokens_ordered, download_results):
                if isinstance(res, str) and res:
                    self.downloaded_images[token] = res
            logger.info(f"✅ 资源预取完成，成功: {len([r for r in download_results if isinstance(r, str) and r])}")


    async def _parse_sheet(self, token: str, results: List[Dict]):
        content_added = False
        original_token = token
        token = self.sdk._clean_token(token) # 🛡️ 预清洗 Token
        
        # 🚀 强制截图优先：如果用户要求截图展示，或者 API 解析不可靠，首先查找截图
        screenshot_path = self._lookup_image_data(original_token, None)
        if screenshot_path:
            logger.info(f"📸 发现电子表格截图，采用截图展示模式: {original_token}")
            results.append({
                'type': 'sheet',
                'content': {
                    'preview': f"/uploads/{self.current_rel_path}/{os.path.basename(screenshot_path)}",
                    'title': '电子表格 (视觉捕捉)',
                    'is_missing': False
                }
            })
            return  # 🎯 找到截图直接返回，不再尝试 API 解析

        # 提取指定的 SheetID (如果是 Wiki 嵌入格式 spreadsheetToken_sheetId)
        target_sheet_id = None
        if "_" in original_token:
            parts = original_token.split("_")
            if len(parts) == 2:
                target_sheet_id = parts[1]

        try:
            # 1. 获取工作簿信息（Sheet 列表）
            sheets, working_token = self.sdk.get_sheet_list(token, self.access_token)
            logger.info(f"📊 Sheet 解析开始: token={working_token}, target={target_sheet_id}, 共有 {len(sheets)} 个工作表")
            
            # 2. 获取元数据（包含合并单元格信息 merges）
            metainfo = self.sdk.get_spreadsheet_metainfo(working_token, self.access_token)
            sheets_meta = {s.get("sheetId"): s for s in metainfo.get("sheets", [])}
            
            for s in sheets:
                # 🚀 如果指定了 target_sheet_id，只解析该 Sheet
                if target_sheet_id and s.sheet_id != target_sheet_id:
                    continue
                    
                results.append({'type': 'heading', 'content': {'level': 2, 'text': s.title}})
                
                # 3. 获取单元格数值
                values = self.sdk.get_sheet_values(working_token, s.sheet_id, self.access_token)
                
                # 4. 获取该 Sheet 的合并单元格列表
                merges = sheets_meta.get(s.sheet_id, {}).get("merges", [])
                
                # 5. 获取样式
                styles = {}
                if values:
                    row_count = len(values)
                    col_count = len(values[0]) if row_count > 0 else 0
                    if row_count > 0 and col_count > 0:
                        styles_data = self.sdk.get_spreadsheet_styles(working_token, s.sheet_id, row_count, col_count, self.access_token)
                        styles = styles_data.get("valueRanges", [{}])[0].get("styles", [])
                
                if values:
                    table_block = self._convert_to_table_block(values, merges, styles)
                    # 🚀 增加视觉同步：如果 Crawler 已经抓取了更完美的截图，将其作为预览图附带
                    # 使用原始 token (包含 _SheetID) 进行查找，因为 Crawler 是按块 ID 或 URL 查找的
                    screenshot_path = self._lookup_image_data(original_token, None)
                    if screenshot_path:
                        table_block['content']['preview'] = f"/uploads/{self.current_rel_path}/{os.path.basename(screenshot_path)}"
                    
                    results.append(table_block)
                    content_added = True
        except Exception as e:
            logger.warning(f"⚠️ 解析 Sheet ({token}) 异常: {e}")
            
        # 🛡️ 极致兜底：如果 Sheet 解析未能产生任何内容，或者报错，尝试作为 Bitable 解析
        if not content_added:
            logger.warning(f"🔄 Sheet ({token}) 内容为空或解析失败，尝试 Bitable 兜底")
            try:
                # 记录当前结果集长度，用于判断 bitable 是否增加了内容
                count_before = len(results)
                await self._parse_bitable(token, results)
                if len(results) > count_before:
                    content_added = True
            except Exception as e2:
                logger.error(f"❌ Bitable ({token}) 兜底解析也失败: {e2}")

        # 🚀 最终完成度兜底：如果 API 和 Bitable 都无法获取内容，强制查找截图预览 (确保 100% 可视)
        if not content_added:
            logger.warning(f"🖼️ API/Bitable 均未获内容，尝试截图兜底: {original_token}")
            screenshot_path = self._lookup_image_data(original_token, None)
            if screenshot_path:
                results.append({
                    'type': 'sheet',
                    'content': {
                        'preview': f"/uploads/{self.current_rel_path}/{os.path.basename(screenshot_path)}",
                        'title': '电子表格 (视觉捕捉版)',
                        'is_missing': False
                    }
                })
                content_added = True
            else:
                logger.error(f"❌ 电子表格已完全丢失: {original_token} (无截图，无 API 数据)")

    async def _parse_bitable(self, token: str, results: List[Dict]):
        token = self.sdk._clean_token(token) # 🛡️ 预清洗 Token
        tables = self.sdk.get_bitable_tables(token, self.access_token)
        for t in tables:
            results.append({'type': 'heading', 'content': {'level': 2, 'text': t.name}})
            records = self.sdk.get_bitable_records(token, t.table_id, self.access_token)
            if records:
                # Basic conversion: use field names as header
                # records is a list of AppTableRecord objects
                if not records: continue
                fields_keys = list(records[0].fields.keys())
                matrix = [fields_keys]
                for r in records:
                    row = [str(r.fields.get(k, "")) for k in fields_keys]
                    matrix.append(row)
                results.append(self._convert_to_table_block(matrix))
                
                # 🚀 Bitable 也尝试匹配截图预览
                screenshot_path = self._lookup_image_data(token, None)
                if screenshot_path and results and results[-1]['type'] == 'table':
                    results[-1]['content']['preview'] = f"/uploads/{self.current_rel_path}/{os.path.basename(screenshot_path)}"

    def _convert_to_table_block(self, matrix: List[List[Any]], merges: Optional[List[Dict]] = None, styles: Optional[List[List[Dict]]] = None) -> Dict[str, Any]:
        """
        将二维矩阵转换为高保真表格块，支持合并单元格和背景颜色。
        merges: [{'startRowIndex': 0, 'startColumnIndex': 0, 'rowCount': 2, 'columnCount': 2}, ...]
        styles: [[{'backColor': '#ffffff'}, ...], ...]
        """
        table_rows = []
        merges = merges or []
        styles = styles or []
        
        # 建立合并中心映射：(row, col) -> (rowspan, colspan)
        merge_map = {}
        # 建立被屏蔽单元格集合：(row, col)
        hidden_cells = set()
        
        for m in merges:
            r = m.get("startRowIndex", 0)
            c = m.get("startColumnIndex", 0)
            rs = m.get("rowCount", 1)
            cs = m.get("columnCount", 1)
            if rs > 1 or cs > 1:
                merge_map[(r, c)] = (rs, cs)
                for dr in range(rs):
                    for dc in range(cs):
                        if dr == 0 and dc == 0: continue
                        hidden_cells.add((r + dr, c + dc))

        for r_idx, row in enumerate(matrix):
            cells = []
            for c_idx, cell_val in enumerate(row):
                # 如果是被合并覆盖的单元格，则跳过
                if (r_idx, c_idx) in hidden_cells:
                    continue
                
                v = "" if cell_val is None else str(cell_val)
                cell_style = {}
                
                # 提取样式
                if r_idx < len(styles) and c_idx < len(styles[r_idx]):
                    s = styles[r_idx][c_idx] or {}
                    
                    # 背景颜色
                    bg_color = s.get("backColor")
                    if bg_color and bg_color.lower() != "#ffffff":
                        cell_style['background-color'] = bg_color
                    
                    # 字体颜色
                    fore_color = s.get("foreColor")
                    if fore_color and fore_color.lower() != "#000000":
                        cell_style['color'] = fore_color
                        
                    # 水平对齐
                    h_align = s.get("hAlign")
                    if h_align is not None:
                        h_map = {0: "left", 1: "center", 2: "right"}
                        cell_style['text-align'] = h_map.get(int(h_align), "left")
                    
                    # 垂直对齐
                    v_align = s.get("vAlign")
                    if v_align is not None:
                        v_map = {0: "top", 1: "middle", 2: "bottom"}
                        cell_style['vertical-align'] = v_map.get(int(v_align), "middle")
                    
                    # 加粗
                    if s.get("fontWeight") == 1: # 飞书 Sheets V2 中 1 通常代表 Bold
                        cell_style['font-weight'] = 'bold'
                    
                    # 斜体
                    if s.get("fontItalic"):
                        cell_style['font-style'] = 'italic'

                # 处理合并属性
                if (r_idx, c_idx) in merge_map:
                    rs, cs = merge_map[(r_idx, c_idx)]
                    if rs > 1: cell_style['rowspan'] = rs
                    if cs > 1: cell_style['colspan'] = cs

                cells.append({
                    'content': [{'type': 'text', 'content': {'text': v}}],
                    'style': cell_style,
                    'is_header': r_idx == 0
                })
            
            if cells:
                table_rows.append({'cells': cells, 'style': {}})
        
        return {
            'type': 'table',
            'content': {
                'rows': table_rows,
                'style': {}
            }
        }

    def _normalize_block_id(self, block_id: str) -> str:
        if not block_id:
            return ""
        for prefix in ("block-", "docx-", "B-", "B_", "G-"):
            block_id = block_id.replace(prefix, "")
        return block_id

    def _register_block(self, block_id: str, block: Dict) -> None:
        self.blocks_map[block_id] = block
        normalized = self._normalize_block_id(block_id)
        if normalized and normalized not in self.blocks_map_normalized:
            self.blocks_map_normalized[normalized] = block

    def _get_block_by_id(self, block_id: Optional[str]) -> Optional[Dict]:
        if not block_id:
            return None
        if block_id in self.blocks_map:
            return self.blocks_map[block_id]
        normalized = self._normalize_block_id(block_id)
        return self.blocks_map_normalized.get(normalized)

    def _infer_payload_key(self, block: Dict) -> str:
        candidate_keys = [
            "text",
            "heading1", "heading2", "heading3", "heading4", "heading5", "heading6", "heading7", "heading8", "heading9",
            "bullet", "ordered", "code", "quote", "todo", "equation",
            "image", "table", "file", "link_preview", "iframe",
            "callout", "board", "diagram", "sheet", "bitable"
        ]
        for key in candidate_keys:
            if key in block and block.get(key) is not None:
                return key
        return ""

    def _apply_text_element_style(self, content: str, style: Optional[Dict[str, Any]]) -> str:
        if not content or not style:
            return content

        mapped_styles = self._map_styles(style)
        css_styles = [f"{k}: {v}" for k, v in mapped_styles.items()]
        
        # Semantic mapping
        if style.get("bold") or style.get("font_weight") == 2:
            content = f"<strong>{content}</strong>"
        if style.get("italic") or style.get("font_style") == "italic":
            content = f"<em>{content}</em>"
        if style.get("strikethrough") or style.get("strike"):
            content = f"<del>{content}</del>"
        if style.get("underline"):
            content = f"<u>{content}</u>"
        if style.get("inline_code") or style.get("code"):
            content = f"<code>{content}</code>"

        # Links
        link = style.get("link") or {}
        link_url = link.get("url")
        if link_url:
            content = f'<a href="{unquote(link_url)}" target="_blank" rel="noopener noreferrer">{content}</a>'

        if css_styles:
            style_attr = "; ".join(css_styles)
            content = f'<span style="{style_attr}">{content}</span>'

        return content

    def _map_styles(self, style: Dict[str, Any]) -> Dict[str, str]:
        res = {}
        if not style: return res
        
        # Colors
        text_color = self._resolve_color_value(style.get("text_color") or style.get("textColor"))
        if text_color: res["color"] = text_color
        
        bg_color = self._resolve_color_value(style.get("background_color") or style.get("backgroundColor") or style.get("textHighlight") or style.get("text_highlight"))
        if bg_color: res["background-color"] = bg_color
        
        # Align
        align = style.get("align") or style.get("textAlign") or style.get("text_align")
        if align is not None: res["text-align"] = self._map_align(align)
        
        # Typography
        fs = style.get("font_size") or style.get("fontSize")
        if fs:
            fs_str = str(fs)
            if fs_str.isdigit(): fs_str += "px"
            res["font-size"] = fs_str
            
        fw = style.get("font_weight") or style.get("fontWeight")
        if fw:
            if fw == 2 or str(fw).lower() == "bold": res["font-weight"] = "bold"
            elif fw == 1: res["font-weight"] = "normal"
            else: res["font-weight"] = str(fw)
            
        ff = style.get("font_family") or style.get("fontFamily")
        if ff: res["font-family"] = ff
        
        fst = style.get("font_style") or style.get("fontStyle")
        if fst:
            if fst == "italic" or fst is True: res["font-style"] = "italic"
            else: res["font-style"] = str(fst)

        # Indentation
        indent = style.get("indent_level") or style.get("indent")
        if indent:
            try:
                res["margin-left"] = f"{int(indent) * 2}em"
            except: pass

        # Line Height
        lh = style.get("line_height") or style.get("lineHeight")
        if lh:
            res["line-height"] = str(lh)
            
        return res

    def _resolve_color_value(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, dict):
            r = value.get("r")
            g = value.get("g")
            b = value.get("b")
            if r is not None and g is not None and b is not None:
                a = value.get("a", 1)
                try:
                    return f"rgba({int(r)}, {int(g)}, {int(b)}, {float(a)})"
                except Exception:
                    return None
        try:
            if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
                idx = int(value)
                mapped = FEISHU_COLOR_MAP.get(idx)
                if mapped:
                    return f"var(--feishu-color-{idx}, {mapped})"
                return f"var(--feishu-color-{idx})"
        except Exception:
            pass
        return str(value)

    def _format_reminder(self, reminder: Dict[str, Any]) -> str:
        ts = reminder.get("expire_time") or reminder.get("notify_time")
        if not ts:
            return "[reminder]"
        try:
            ts_val = int(ts)
            if ts_val > 1_000_000_000_000:
                ts_val = ts_val / 1000
            dt = datetime.fromtimestamp(ts_val, tz=timezone.utc).astimezone()
            return f"[reminder {dt.strftime('%Y-%m-%d %H:%M')}]"
        except Exception:
            return "[reminder]"

    def _render_inline_block(self, block_id: Optional[str], inline_block_visited: set) -> str:
        if not block_id or block_id in inline_block_visited:
            return ""
        inline_block_visited.add(block_id)
        block = self._get_block_by_id(block_id)
        if not block:
            return ""

        payload_key = self._get_payload_key(block.get("block_type")) or self._infer_payload_key(block)
        if not payload_key:
            return ""

        payload = block.get(payload_key, {})
        if payload_key.startswith("heading"):
            return self._render_text_payload(payload, inline_block_visited)
        if payload_key in ("text", "bullet", "ordered", "quote", "todo", "code", "equation"):
            return self._render_text_payload(payload, inline_block_visited)
        return ""

    def _render_text_elements(self, elements: List[Dict[str, Any]], inline_block_visited: Optional[set] = None, replace_newline: bool = True) -> str:
        if inline_block_visited is None:
            inline_block_visited = set()

        text_parts = []
        for el in elements:
            if "text_run" in el:
                run = el["text_run"]
                content = run.get("content", "")
                content = self._apply_text_element_style(content, run.get("text_element_style"))
                text_parts.append(content)
            elif "mention_user" in el:
                mention = el["mention_user"]
                content = mention.get("user_id") or ""
                content = f"@{content}" if content else "@user"
                content = self._apply_text_element_style(content, mention.get("text_element_style"))
                text_parts.append(content)
            elif "mention_doc" in el:
                mention = el["mention_doc"]
                title = mention.get("title") or mention.get("token") or "doc"
                url = mention.get("url")
                content = f'<a href="{unquote(url)}" target="_blank" rel="noopener noreferrer">{title}</a>' if url else title
                content = self._apply_text_element_style(content, mention.get("text_element_style"))
                text_parts.append(content)
            elif "reminder" in el:
                reminder = el["reminder"]
                content = self._format_reminder(reminder)
                content = self._apply_text_element_style(content, reminder.get("text_element_style"))
                text_parts.append(content)
            elif "file" in el:
                inline_file = el["file"]
                file_token = inline_file.get("file_token") or ""
                source_block_id = inline_file.get("source_block_id")
                name = None
                if source_block_id:
                    source_block = self._get_block_by_id(source_block_id)
                    if source_block:
                        name = (source_block.get("file") or {}).get("name")
                if not name:
                    name = file_token or source_block_id or "file"
                content = f"[file:{name}]"
                content = self._apply_text_element_style(content, inline_file.get("text_element_style"))
                text_parts.append(content)
            elif "inline_block" in el:
                inline_block = el["inline_block"]
                block_id = inline_block.get("block_id")
                fallback_label = f"[block:{block_id}]" if block_id else "[block]"
                content = self._render_inline_block(block_id, inline_block_visited) or fallback_label
                content = self._apply_text_element_style(content, inline_block.get("text_element_style"))
                text_parts.append(content)
            elif "equation" in el:
                equation = el["equation"]
                eq_content = equation.get("content", "")
                content = f"${eq_content}$" if eq_content else ""
                content = self._apply_text_element_style(content, equation.get("text_element_style"))
                if content:
                    text_parts.append(content)
            elif "link_preview" in el:
                link_preview = el["link_preview"]
                title = link_preview.get("title") or link_preview.get("url") or "link"
                url = link_preview.get("url")
                content = f'<a href="{unquote(url)}" target="_blank" rel="noopener noreferrer">{title}</a>' if url else title
                content = self._apply_text_element_style(content, link_preview.get("text_element_style"))
                text_parts.append(content)
            elif "undefined" in el:
                continue
            else:
                fallback = ""
                for value in el.values():
                    if isinstance(value, dict):
                        for key in ("content", "text", "title", "url"):
                            val = value.get(key)
                            if isinstance(val, str) and val:
                                fallback = val
                                break
                    if fallback:
                        break
                if fallback:
                    text_parts.append(fallback)

        final_text = "".join(text_parts)
        if replace_newline:
            final_text = final_text.replace("\n", "<br/>")
        return final_text

    def _load_client_vars_styles(self, client_vars_data: Optional[str]) -> None:
        self.client_style_text = {}
        self.client_block_styles = {}

        if not client_vars_data:
            return

        try:
            raw = json.loads(client_vars_data) if isinstance(client_vars_data, str) else client_vars_data
        except Exception as e:
            logger.debug(f"client_vars_data parse failed: {e}")
            return

        block_map = self._find_client_block_map(raw)
        if not block_map:
            return

        for bid, block in block_map.items():
            if not isinstance(block, dict):
                continue

            block_id = block.get("block_id") or block.get("id") or bid
            if not block_id:
                continue

            normalized = self._normalize_block_id(block_id)
            text = self._extract_text_from_client_block(block)
            if text:
                self.client_style_text[normalized] = text

            style = self._extract_block_style_from_client_block(block)
            if style:
                self.client_block_styles[normalized] = style

    def _find_client_block_map(self, raw: Any) -> Dict[str, Any]:
        if not isinstance(raw, dict):
            return {}

        candidates = []
        data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
        candidates.append(data.get("body", {}).get("blocks") if isinstance(data.get("body"), dict) else None)
        candidates.append(data.get("blocks"))
        candidates.append(raw.get("blocks"))

        cv = raw.get("clientVars") if isinstance(raw.get("clientVars"), dict) else None
        if cv:
            cv_data = cv.get("data") if isinstance(cv.get("data"), dict) else {}
            candidates.append(cv_data.get("body", {}).get("blocks") if isinstance(cv_data.get("body"), dict) else None)
            candidates.append(cv_data.get("blocks"))
            candidates.append(cv.get("blocks"))

        for candidate in candidates:
            if isinstance(candidate, dict) and candidate:
                return candidate

        return self._deep_find_blocks(raw)

    def _deep_find_blocks(self, obj: Any) -> Dict[str, Any]:
        if isinstance(obj, dict):
            blocks = obj.get("blocks")
            if isinstance(blocks, dict) and blocks:
                if all(isinstance(v, dict) for v in blocks.values()):
                    return blocks
            for value in obj.values():
                result = self._deep_find_blocks(value)
                if result:
                    return result
        elif isinstance(obj, list):
            for item in obj:
                result = self._deep_find_blocks(item)
                if result:
                    return result
        return {}

    def _extract_text_from_client_block(self, block: Dict) -> str:
        b_data = block.get("data", {}) if isinstance(block.get("data"), dict) else {}
        text_obj = b_data.get("text", {}) if isinstance(b_data.get("text"), dict) else {}

        ast = (
            text_obj.get("initial_attributedString")
            or text_obj.get("base_attributedString")
            or text_obj.get("attributedString")
        )
        if not ast:
            content_obj = b_data.get("content", {}) if isinstance(b_data.get("content"), dict) else {}
            ast = content_obj.get("initial_attributedString")

        if ast:
            text = ast.get("text", "")
            return self._apply_text_styles(text, ast.get("attributes", []))

        iat = text_obj.get("initialAttributedTexts", {})
        if iat and "text" in iat:
            t_obj = iat.get("text")
            attribs_obj = iat.get("attribs", {})
            apool = text_obj.get("apool", {})

            if isinstance(t_obj, dict):
                keys = sorted(t_obj.keys(), key=lambda x: int(x) if str(x).isdigit() else 0)
                full_text = "".join(str(t_obj[k]) for k in keys)
            else:
                full_text = str(t_obj)

            if not attribs_obj or not apool:
                return full_text # Don't strip to preserve newlines

            attributes = self._parse_wiki_attribs(attribs_obj, apool)
            return self._apply_text_styles(full_text, attributes)

        if isinstance(text_obj, str):
            return text_obj # Don't strip to preserve newlines

        return ""

    def _apply_text_styles(self, text: str, attributes: List[Dict]) -> str:
        if not text:
            return text
        
        # 即使没有样式属性，也需要进行换行符转换
        if not attributes:
            return text.replace("\n", "<br/>")

        marks = []
        for attr in attributes:
            start = attr.get("location", 0)
            length = attr.get("length", 0)
            end = start + length
            style = attr.get("style", {})

            if style.get("bold"):
                marks.append((start, "<strong>", 10))
                marks.append((end, "</strong>", -10))
            if style.get("italic"):
                marks.append((start, "<em>", 9))
                marks.append((end, "</em>", -9))
            if style.get("underline"):
                marks.append((start, "<u>", 8))
                marks.append((end, "</u>", -8))
            if style.get("strike"):
                marks.append((start, "<del>", 7))
                marks.append((end, "</del>", -7))
            if style.get("link"):
                url = style["link"].get("url", "#")
                marks.append((start, f'<a href="{unquote(url)}" target="_blank" rel="noopener noreferrer">', 6))
                marks.append((end, "</a>", -6))
            if style.get("code"):
                marks.append((start, "<code>", 5))
                marks.append((end, "</code>", -5))

            inline_style = []
            if style.get("text_color"):
                text_color = self._resolve_color_value(style.get("text_color"))
                if text_color:
                    inline_style.append(f"color: {text_color}")
            if style.get("background_color"):
                bg_color = self._resolve_color_value(style.get("background_color"))
                if bg_color:
                    inline_style.append(f"background-color: {bg_color}")
            if style.get("font_size"):
                fs = str(style["font_size"])
                if fs.isdigit():
                    fs += "px"
                inline_style.append(f"font-size: {fs}")
            if style.get("font_weight"):
                inline_style.append(f"font-weight: {style['font_weight']}")
            if style.get("font_family"):
                inline_style.append(f"font-family: {style['font_family']}")
            if style.get("font_style"):
                inline_style.append(f"font-style: {style['font_style']}")
            if style.get("align"):
                inline_style.append(f"text-align: {style['align']}")
            if style.get("line_height"):
                inline_style.append(f"line-height: {style['line_height']}")

            if inline_style:
                style_str = "; ".join(inline_style)
                marks.append((start, f'<span style="{style_str}">', 4))
                marks.append((end, "</span>", -4))

        marks.sort(key=lambda x: (x[0], x[2]))

        result = ""
        last_idx = 0
        for pos, tag, _ in marks:
            segment = text[last_idx:pos].replace("\n", "<br/>")
            result += segment
            result += tag
            last_idx = pos
        result += text[last_idx:].replace("\n", "<br/>")

        return result

    def _parse_wiki_attribs(self, attribs_obj: Dict, apool: Dict) -> List[Dict]:
        results = []
        num_to_attrib = apool.get("numToAttrib", {})

        current_location = 0
        sorted_keys = sorted(attribs_obj.keys(), key=lambda x: int(x) if str(x).isdigit() else 0)
        full_attrib_str = "".join(attribs_obj[k] for k in sorted_keys)

        parts = re.findall(r"(\*\d+|\+\w+)", full_attrib_str)
        active_styles = {}
        for part in parts:
            if part.startswith("*"):
                idx = part[1:]
                attr_pair = num_to_attrib.get(idx, [])
                if len(attr_pair) >= 2:
                    key, val = attr_pair[0], attr_pair[1]
                    if key == "bold" and val == "true":
                        active_styles["bold"] = True
                    elif key == "italic" and val == "true":
                        active_styles["italic"] = True
                    elif key == "underline" and val == "true":
                        active_styles["underline"] = True
                    elif key == "strike" and val == "true":
                        active_styles["strike"] = True
                    elif key == "inlineCode" and val == "true":
                        active_styles["code"] = True
                    elif key == "textHighlight":
                        active_styles["background_color"] = val
                    elif key == "textColor":
                        active_styles["text_color"] = val
                    elif key == "fontSize":
                        active_styles["font_size"] = val
                    elif key == "fontWeight":
                        active_styles["font_weight"] = val
                    elif key == "fontFamily":
                        active_styles["font_family"] = val
                    elif key == "fontStyle":
                        active_styles["font_style"] = val
                    elif key == "link":
                        active_styles["link"] = {"url": val}
            elif part.startswith("+"):
                try:
                    length_str = part[1:]
                    length = int(length_str, 36)
                except Exception:
                    length = 0

                if length > 0 and active_styles:
                    results.append({
                        "location": current_location,
                        "length": length,
                        "style": active_styles.copy()
                    })

                current_location += length
                active_styles = {}

        return results

    def _extract_block_style_from_client_block(self, block: Dict) -> Dict[str, Any]:
        b_data = block.get("data", {}) if isinstance(block.get("data"), dict) else {}
        return self._map_styles(b_data)

    def _get_client_style_text(self, block_id: Optional[str]) -> str:
        if not block_id:
            return ""
        normalized = self._normalize_block_id(block_id)
        return self.client_style_text.get(normalized, "")

    def _get_client_block_style(self, block_id: Optional[str]) -> Dict[str, Any]:
        if not block_id:
            return {}
        normalized = self._normalize_block_id(block_id)
        return self.client_block_styles.get(normalized, {})

    def _lookup_image_data(self, token: Optional[str], block_id: Optional[str]) -> Optional[str]:
        candidates = []
        for value in (token, block_id):
            if value:
                candidates.append(value)
                normalized = self._normalize_block_id(value)
                if normalized and normalized not in candidates:
                    candidates.append(normalized)

        for key in candidates:
            path = self.images_data.get(key)
            if isinstance(path, str) and path and not path.startswith("data:") and os.path.exists(path):
                return self._ensure_local_image(path, token or block_id)

        for key in candidates:
            if not key:
                continue
            for k, v in self.images_data.items():
                if not isinstance(k, str):
                    continue
                if key in k or k in key:
                    if isinstance(v, str) and v and not v.startswith("data:") and os.path.exists(v):
                        return self._ensure_local_image(v, token or block_id)

        if block_id:
            prefix = self._normalize_block_id(block_id)[:16]
            if prefix:
                for v in self.images_data.values():
                    if isinstance(v, str) and v and not v.startswith("data:") and os.path.exists(v):
                        if f"complex_{prefix}" in v:
                            return self._ensure_local_image(v, token or block_id)

        return None

    def _ensure_local_image(self, path: str, key: Optional[str]) -> str:
        if not self.current_abs_path:
            return path

        try:
            base_dir = str(self.current_abs_path)
            if os.path.commonpath([path, base_dir]) == base_dir:
                return self._trim_image_whitespace(path)
        except Exception:
            pass

        filename = os.path.basename(path)
        if key and filename.startswith("complex_") is False:
            ext = os.path.splitext(filename)[1] or ".png"
            filename = f"{hashlib.md5(str(key).encode()).hexdigest()}{ext}"

        target_path = os.path.join(self.current_abs_path, filename)
        if not os.path.exists(target_path):
            try:
                import shutil
                shutil.copy2(path, target_path)
            except Exception:
                return path
        return self._trim_image_whitespace(target_path)

    def _trim_image_whitespace(self, path: str) -> str:
        """裁剪图片周围的空白区域，特别针对飞书画板的大面积白边进行优化"""
        if not path or path in self.processed_images:
            return path

        self.processed_images.add(path)

        try:
            from PIL import Image, ImageChops
            with Image.open(path) as img:
                img.load()
                original_size = img.size
                modified = False

                # 1. 处理透明通道
                if img.mode in ("RGBA", "LA"):
                    alpha = img.split()[-1]
                    alpha_mask = alpha.point(lambda p: 255 if p > 0 else 0)
                    bbox = alpha_mask.getbbox()
                    if bbox:
                        bbox = self._expand_bbox(bbox, img.size, padding=6)
                        img = img.crop(bbox)
                        modified = True

                # 2. 转为 RGB 进行白色检测
                rgb = img.convert("RGB")
                
                # 🔧 优化：针对飞书画板，假设背景是纯白/近白
                # 先尝试纯白色背景裁剪
                white_bg = (255, 255, 255)
                diff = ImageChops.difference(rgb, Image.new("RGB", rgb.size, white_bg))
                diff = diff.convert("L")
                # 🔧 提高阈值从 12 到 20，更激进地检测内容边界
                mask = diff.point(lambda p: 255 if p > 20 else 0)
                bbox = mask.getbbox()
                
                if not bbox:
                    # 如果纯白检测失败，使用采样背景色
                    bg_color = self._sample_background(rgb)
                    diff = ImageChops.difference(rgb, Image.new("RGB", rgb.size, bg_color))
                    diff = diff.convert("L")
                    mask = diff.point(lambda p: 255 if p > 15 else 0)
                    bbox = mask.getbbox()
                
                if bbox:
                    bbox = self._expand_bbox(bbox, rgb.size, padding=8)
                    if bbox != (0, 0, rgb.size[0], rgb.size[1]):
                        cropped = img.crop(bbox)
                        if cropped.size[0] > 0 and cropped.size[1] > 0:
                            img = cropped
                            modified = True

                # 3. 🔧 新增：限制图片最大高度，防止过长的空白尾部
                # 如果图片高度超过宽度的 2 倍，且裁剪后仍很高，尝试进一步裁剪底部
                if img.size[1] > img.size[0] * 2:
                    # 从底部向上扫描，寻找最后一行有内容的位置
                    rgb_final = img.convert("RGB")
                    height = rgb_final.size[1]
                    width = rgb_final.size[0]
                    last_content_row = height
                    
                    for y in range(height - 1, max(0, height - int(height * 0.6)), -1):
                        row_has_content = False
                        for x in range(0, width, max(1, width // 20)):  # 每行抽样检查
                            pixel = rgb_final.getpixel((x, y))
                            # 检查是否为非白色像素
                            if not all(c > 245 for c in pixel):
                                row_has_content = True
                                break
                        if row_has_content:
                            last_content_row = y + 30  # 留一点底部边距
                            break
                    
                    if last_content_row < height - 50:  # 至少裁掉 50px 才值得
                        img = img.crop((0, 0, width, min(height, last_content_row)))
                        modified = True
                        logger.debug(f"🔧 进一步裁剪底部空白: {height} -> {last_content_row}")

                if modified:
                    img.save(path)
                    logger.debug(f"✂️ 图片裁剪完成: {original_size} -> {img.size}")
        except Exception as e:
            logger.debug(f"trim image failed: {path}, {e}")

        return path


    def _sample_background(self, img) -> Tuple[int, int, int]:
        width, height = img.size
        points = [
            (0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1),
            (width // 2, 0), (width // 2, height - 1), (0, height // 2), (width - 1, height // 2),
        ]
        colors = []
        for x, y in points:
            try:
                colors.append(img.getpixel((x, y)))
            except Exception:
                continue
        if not colors:
            return (255, 255, 255)
        avg = tuple(int(sum(c[i] for c in colors) / len(colors)) for i in range(3))
        return avg

    def _expand_bbox(self, bbox: Tuple[int, int, int, int], size: Tuple[int, int], padding: int = 0) -> Tuple[int, int, int, int]:
        left, top, right, bottom = bbox
        width, height = size
        if padding:
            left = max(0, left - padding)
            top = max(0, top - padding)
            right = min(width, right + padding)
            bottom = min(height, bottom + padding)
        return (left, top, right, bottom)

    async def _render_table_from_payload(self, table_data: Dict) -> Optional[Dict]:
        if not isinstance(table_data, dict):
            return None

        cells = table_data.get("cells") or []
        prop = table_data.get("property", {}) if isinstance(table_data.get("property"), dict) else {}
        row_size = prop.get("row_size")
        col_size = prop.get("column_size")

        try:
            row_size = int(row_size)
            col_size = int(col_size)
        except (TypeError, ValueError):
            return None

        if not cells or row_size <= 0 or col_size <= 0:
            return None

        rows = []
        for r_idx in range(row_size):
            row_cells = []
            for c_idx in range(col_size):
                cell_idx = (r_idx * col_size) + c_idx
                cell_id = cells[cell_idx] if cell_idx < len(cells) else None
                cell_results = []
                if cell_id:
                    cell_block = self._get_block_by_id(cell_id)
                    if cell_block:
                        await self._recursive_render_docx(cell_block, cell_results)
                is_header = (prop.get("header_row") and r_idx == 0) or (prop.get("header_column") and c_idx == 0)
                row_cells.append({'content': cell_results, 'style': {}, 'is_header': bool(is_header)})
            rows.append({'cells': row_cells, 'style': {}})

        return {'type': 'table', 'content': {'rows': rows, 'style': {}}}

    async def _render_table_from_children(self, block: Dict) -> Optional[Dict]:
        rows = []
        row_cids = block.get("children", [])
        for rcid in row_cids:
            row_block = self._get_block_by_id(rcid)
            if not row_block:
                continue
            cells = []
            cell_cids = row_block.get("children", [])
            for ccid in cell_cids:
                cell_block = self._get_block_by_id(ccid)
                if not cell_block:
                    continue
                cell_results = []
                cell_sub_cids = cell_block.get("children", [])
                for scid in cell_sub_cids:
                    sub_block = self._get_block_by_id(scid)
                    if sub_block:
                        await self._recursive_render_docx(sub_block, cell_results)
                cells.append({'content': cell_results, 'style': {}, 'is_header': False})
            rows.append({'cells': cells, 'style': {}})

        if not rows:
            return None
        return {'type': 'table', 'content': {'rows': rows, 'style': {}}}

    async def _recursive_render_docx(self, block: Dict, results: List[Dict], payload_key_override: str = None):
        bt = block.get("block_type")
        # Use payload-first approach: if the block has a certain payload key, use it
        inferred_key = self._infer_payload_key(block)
        payload_key = payload_key_override or inferred_key or self._get_payload_key(bt)
        b_data = block.get(payload_key, {}) if payload_key and isinstance(block.get(payload_key), dict) else {}
        
        # 兼容旧版或无 payload_key 情况
        if not b_data and payload_key == "sheet":
             b_data = block.get("sheet", {})


        block_id = block.get("block_id") or block.get("id")
        styled_text = self._get_client_style_text(block_id)
        block_style = self._get_client_block_style(block_id)
        children = block.get("children", [])
        
        # 1. Handle self
        payload_style = b_data.get("style", {}) if isinstance(b_data, dict) else {}
        if not block_style:
            block_style = {}
        
        # Deduplicate title if it appears at the very beginning of the content
        if not self.title_removed and self.current_title and not results:
            plain_text = self._extract_plain_text(b_data)
            if plain_text and plain_text.strip() == self.current_title.strip():
                self.title_removed = True
                # Still process children if any, but skip this title block itself
                for cid in children:
                    child_block = self._get_block_by_id(cid)
                    if child_block:
                        await self._recursive_render_docx(child_block, results)
                return
        
        # Merge alignment from payload if not in block_style
        if "align" in payload_style and "text-align" not in block_style:
            block_style["text-align"] = self._map_align(payload_style["align"])
        elif "text_align" in payload_style and "text-align" not in block_style:
            block_style["text-align"] = self._map_align(payload_style["text_align"])

        if bt == BlockType.TEXT or payload_key == "text":
            text = styled_text or self._render_text_payload(b_data, replace_newline=True)
            if text:
                content = {'text': text}
                if block_style:
                    content['style'] = block_style
                results.append({'type': 'text', 'content': content})
        
        elif (BlockType.HEADING1 <= bt <= BlockType.HEADING9) or (payload_key and payload_key.startswith("heading")):
            if payload_key and payload_key.startswith("heading"):
                try:
                    level = int(payload_key.replace("heading", ""))
                except ValueError:
                    level = 2
            else:
                # Feishu HEADING1 is 3, HEADING9 is 11
                # Standard mapping: h1=1, h2=2...
                level = bt - 2
            
            # Map level to range 1-6 for HTML safety
            level = max(1, min(6, level))
            
            text = styled_text or self._render_text_payload(b_data, replace_newline=True)
            if text:
                content = {'level': level, 'text': text}
                if block_style:
                    content['style'] = block_style
                results.append({'type': 'heading', 'content': content})
                # Heading breaks list continuity
                self.last_ordered_count = 0
            
        elif bt == BlockType.BULLET or payload_key == "bullet":
            text = styled_text or self._render_text_payload(b_data, replace_newline=True)
            if text:
                item = {'text': text}
                # Check if we can append to an existing unordered list (that's not a todo list)
                if results and results[-1].get('type') == 'list' and not results[-1]['content'].get('ordered') and not results[-1]['content'].get('items', [{}])[0].get('todo'):
                    results[-1]['content']['items'].append(item)
                else:
                    content = {'ordered': False, 'items': [item]}
                    if block_style:
                        content['style'] = block_style
                    results.append({'type': 'list', 'content': content})
            
        elif bt == BlockType.ORDERED or payload_key == "ordered":
            text = styled_text or self._render_text_payload(b_data, replace_newline=True)
            # 即使 text 为空，也允许作为列表项存在（用户可能只放了图片作为子节点）
            item = {'text': text or ""}
            # Group ordered lists
            if results and results[-1].get('type') == 'list' and results[-1]['content'].get('ordered'):
                results[-1]['content']['items'].append(item)
                self.last_ordered_count += 1
            else:
                # Start a new list, possibly continuing numbering
                start_val = self.last_ordered_count + 1
                content = {'ordered': True, 'items': [item], 'start': start_val}
                if block_style:
                    content['style'] = block_style
                results.append({'type': 'list', 'content': content})
                self.last_ordered_count += 1

        elif bt == BlockType.TODO or payload_key == "todo":
            text = styled_text or self._render_text_payload(b_data, replace_newline=True)
            if text:
                item = {'text': text, 'todo': True, 'done': b_data.get("done", False)}
                # Group todo lists separately from bullets
                if (results and results[-1].get('type') == 'list' and 
                    not results[-1]['content'].get('ordered') and 
                    results[-1]['content'].get('items') and 
                    results[-1]['content']['items'][0].get('todo')):
                    results[-1]['content']['items'].append(item)
                else:
                    content = {'ordered': False, 'items': [item]}
                    if block_style:
                        content['style'] = block_style
                    results.append({'type': 'list', 'content': content})

        elif bt == BlockType.QUOTE or payload_key == "quote":
            text = styled_text or self._render_text_payload(b_data, replace_newline=True)
            if text:
                results.append({'type': 'quote', 'content': {'text': text}})
            
        elif bt == BlockType.CODE or payload_key == "code":
            text = self._extract_plain_text(b_data)
            lang = b_data.get("language", 0)
            results.append({'type': 'code', 'content': {'code': text, 'language': self._map_lang(lang)}})

        elif payload_key == "equation":
            text = self._render_text_payload(b_data, replace_newline=True)
            if text:
                results.append({'type': 'text', 'content': {'text': text}})
            
        elif bt in (BlockType.IMAGE, BlockType.LEGACY_IMAGE) or payload_key == "image":
            token = b_data.get("token")
            if token:
                # 优先从 images_data 中获取 (可能已经由 Crawler 抓取)
                local_path = self._lookup_image_data(token, block_id)
                if not local_path:
                    local_path = self.downloaded_images.get(token)
                if not local_path or not os.path.exists(local_path):
                    local_path = await self.sdk.download_image(token, self.access_token, self.current_abs_path)
                    if local_path:
                        local_path = self._trim_image_whitespace(local_path)
                        self.downloaded_images[token] = local_path
                        self.images_data[token] = local_path
                
                if local_path:
                    rel_url = f"/uploads/{self.current_rel_path}/{os.path.basename(local_path)}"
                    results.append({
                        'type': 'image',
                        'content': {
                            'url': rel_url,
                            'alt': 'Image',
                            'align': 'center',
                            'style': {'text-align': 'center'}
                        }
                    })

        elif bt in (BlockType.BOARD, BlockType.LEGACY_BOARD) or payload_key == "board":
            token = b_data.get("token") or b_data.get("obj_token")
            # 优先使用 API 导出纯净图片
            local_path = None
            if token:
                # First try API download to get clean image
                local_path = self.downloaded_images.get(token)
                if not local_path or not os.path.exists(local_path):
                    local_path = await self.sdk.get_whiteboard_as_image(token, self.access_token, self.current_abs_path)
                    if local_path:
                        local_path = self._trim_image_whitespace(local_path)
                        self.downloaded_images[token] = local_path
                        self.images_data[token] = local_path

            # Fallback to Crawler screenshot if API fails
            if not local_path or not os.path.exists(local_path):
                 local_path = self._lookup_image_data(token, block_id) if token or block_id else None
            
            if local_path:
                rel_url = f"/uploads/{self.current_rel_path}/{os.path.basename(local_path)}"
                results.append({
                    'type': 'whiteboard', 
                    'content': {
                        'preview': rel_url, 
                        'url': rel_url,
                        'alt': 'Board',
                        'title': '智能画板',
                        'token': token,
                        'align': 'center',
                        'style': {'text-align': 'center'}
                    }
                })
            return

        elif bt == BlockType.DIAGRAM or payload_key == "diagram":
            token = b_data.get("token") or b_data.get("obj_token")
            # 优先使用 Crawler 捕捉的精准截图
            local_path = self._lookup_image_data(token, block_id) if token or block_id else None
            if not local_path and token:
                local_path = self.downloaded_images.get(token)
            
            if local_path and os.path.exists(local_path):
                rel_url = f"/uploads/{self.current_rel_path}/{os.path.basename(local_path)}"
                results.append({
                    'type': 'diagram', 
                    'content': {
                        'preview': rel_url, 
                        'url': rel_url,
                        'alt': 'Diagram',
                        'title': '流程图解',
                        'token': token,
                        'align': 'center',
                        'style': {'text-align': 'center'}
                    }
                })
            return

        elif bt == BlockType.GRID:
            # Grids contain columns
            col_cids = block.get("children", [])
            for ccid in col_cids:
                col_block = self._get_block_by_id(ccid)
                if col_block:
                    await self._recursive_render_docx(col_block, results)
            return

        elif bt == BlockType.TABLE or payload_key == "table":
            table_block = await self._render_table_from_payload(b_data)
            if not table_block:
                table_block = await self._render_table_from_children(block)
            if table_block:
                results.append(table_block)
            return

        elif bt == BlockType.VIEWGROUP and not payload_key_override:
            # VIEWGROUP (Type 30) 充当复杂组件（如嵌入 Sheet、Bitable、Whiteboard）的容器
            # 🚀 自动探测内部实际负载类型并代理处理
            inferred_key = self._infer_payload_key(block)
            if inferred_key and inferred_key in ["sheet", "bitable", "board", "diagram"]:
                logger.info(f"📦 检测到 VIEWGROUP ({block_id}) 含有 {inferred_key} 负载, 内部转办...")
                # 🛡️ 修复无限递归：通过 payload_key_override 告知下一层不要再进入 VIEWGROUP 逻辑
                await self._recursive_render_docx(block, results, payload_key_override=inferred_key)
                return
            
            # 如果没有识别出负载，递归处理子节点
            for cid in children:
                child_block = self._get_block_by_id(cid)
                if child_block:
                    await self._recursive_render_docx(child_block, results)
            return




        elif bt == BlockType.SHEET or payload_key == "sheet":
            token = b_data.get("token") or b_data.get("obj_token")
            # 🚀 策略：由于 Sheet API 复杂，优先检查是否有 Crawler 捕捉的高保真截图
            screenshot_path = self._lookup_image_data(token, block_id) if token or block_id else None
            
            # 如果有截图，且是针对该块的（或者包含 token），优先展示截图以确保 100% 还原布局
            if screenshot_path and os.path.exists(screenshot_path):
                rel_url = f"/uploads/{self.current_rel_path}/{os.path.basename(screenshot_path)}"
                logger.info(f"📸 为 Sheet ({token}) 采用截图展示模式")
                results.append({
                    'type': 'sheet',
                    'content': {
                        'preview': rel_url,
                        'title': '电子表格 (视觉捕捉)',
                        'is_missing': False
                    }
                })
                return

            # 如果没有截图，尝试 API 解析获取表格数据
            content_length_before = len(results)
            if token:
                await self._parse_sheet(token, results)
            
            if len(results) == content_length_before: # API 解析未能添加任何内容
                logger.error(f"❌ Sheet ({token}) API 解析失败且无截图可用")
                results.append({
                    'type': 'sheet',
                    'content': {
                        'title': '电子表格 (无法加载)',
                        'is_missing': True
                    }
                })
            return


        elif bt == BlockType.BITABLE or payload_key == "bitable":
            token = b_data.get("token") or b_data.get("obj_token")
            # 优先尝试 Crawler 抓取的截图
            local_path = self._lookup_image_data(token, block_id) if token or block_id else None
            if local_path and os.path.exists(local_path):
                rel_url = f"/uploads/{self.current_rel_path}/{os.path.basename(local_path)}"
                results.append({
                    'type': 'image',
                    'content': {
                        'url': rel_url,
                        'alt': 'Bitable Preview',
                        'title': '多维表格',
                        'align': 'center',
                        'style': {'text-align': 'center'}
                    }
                })
            elif token:
                await self._parse_bitable(token, results)
            return

        elif bt == BlockType.FILE or payload_key == "file":
            name = b_data.get("name") or b_data.get("token")
            if name:
                results.append({'type': 'text', 'content': {'text': f"[file:{name}]"}})

        elif payload_key == "link_preview":
            url = b_data.get("url")
            if url:
                results.append({'type': 'text', 'content': {'text': f'<a href="{unquote(url)}" target="_blank" rel="noopener noreferrer">{url}</a>'}})

        elif payload_key == "iframe":
            component = b_data.get("component", {}) if isinstance(b_data, dict) else {}
            url = component.get("url") or b_data.get("url")
            if url:
                results.append({'type': 'text', 'content': {'text': f'<a href="{unquote(url)}" target="_blank" rel="noopener noreferrer">iframe</a>'}})

        elif bt == BlockType.DIVIDER:
            results.append({'type': 'divider', 'content': {}})

        elif bt == BlockType.CALLOUT or payload_key == "callout":
            # Callouts can have background colors and emoji
            text = styled_text or self._render_text_payload(b_data, replace_newline=True)
            emoji_id = b_data.get("emoji_id", "")
            bg_color = b_data.get("background_color") or b_data.get("style", {}).get("background_color", "")

            callout_results = []
            if text:
                callout_results.append({'type': 'text', 'content': {'text': text}})

            # Process nested blocks in callout
            children = block.get("children", [])
            for cid in children:
                child_block = self._get_block_by_id(cid)
                if child_block:
                    await self._recursive_render_docx(child_block, callout_results)

            results.append({
                'type': 'callout',
                'content': {
                    'blocks': callout_results,
                    'emoji': emoji_id,
                    'style': {'background_color': bg_color}
                }
            })
            return

        elif isinstance(b_data, dict) and b_data.get("elements"):
            text = styled_text or self._render_text_payload(b_data, replace_newline=True)
            if text:
                content = {'text': text}
                if block_style:
                    content['style'] = block_style
                results.append({'type': 'text', 'content': content})

        # 2. Handle children recursively
        # For list items, children should be nested inside the item's content
        if bt in (BlockType.BULLET, BlockType.ORDERED, BlockType.TODO):
            if results and results[-1].get('type') == 'list':
                last_list = results[-1]
                if last_list['content']['items']:
                    last_item = last_list['content']['items'][-1]
                    if 'children' not in last_item:
                        last_item['children'] = []
                    
                    for cid in children:
                        child_block = self._get_block_by_id(cid)
                        if child_block:
                            await self._recursive_render_docx(child_block, last_item['children'])
            return

        # For regular blocks, children are appended as siblings or nested in specific containers
        if bt == BlockType.CALLOUT or payload_key == "callout":
            # Already handled in the callout branch above
            return

        for cid in children:
            child_block = self._get_block_by_id(cid)
            if child_block:
                await self._recursive_render_docx(child_block, results)

    def _extract_plain_text(self, b_data: Dict) -> str:
        if not b_data: return ""
        elements = b_data.get("elements") or []
        texts = []
        for el in elements:
            if "text_run" in el:
                texts.append(el["text_run"].get("content", ""))
            elif "mention_user" in el:
                texts.append(el["mention_user"].get("user_id", ""))
            elif "mention_doc" in el:
                texts.append(el["mention_doc"].get("title", ""))
            elif "equation" in el:
                texts.append(el["equation"].get("content", ""))
        return "".join(texts)

    def _get_payload_key(self, bt: int) -> str:
        keys = {
            BlockType.PAGE: "page",
            BlockType.TEXT: "text",
            BlockType.HEADING1: "heading1",
            BlockType.HEADING2: "heading2",
            BlockType.HEADING3: "heading3",
            BlockType.HEADING4: "heading4",
            BlockType.HEADING5: "heading5",
            BlockType.HEADING6: "heading6",
            BlockType.HEADING7: "heading7",
            BlockType.HEADING8: "heading8",
            BlockType.HEADING9: "heading9",
            BlockType.BULLET: "bullet",
            BlockType.ORDERED: "ordered",
            BlockType.CODE: "code",
            BlockType.IMAGE: "image",
            BlockType.LEGACY_IMAGE: "image",
            BlockType.TABLE: "table",
            BlockType.QUOTE: "quote",
            BlockType.TODO: "todo",
            BlockType.CALLOUT: "callout",
            BlockType.FILE: "file",
            BlockType.SHEET: "sheet",
            BlockType.BITABLE: "bitable",
            BlockType.BOARD: "board",
            BlockType.LEGACY_BOARD: "board",
            BlockType.DIAGRAM: "diagram",
        }
        return keys.get(bt, "")

    def _render_text_payload(self, payload: Dict, inline_block_visited: Optional[set] = None, replace_newline: bool = True) -> str:
        if not payload:
            return ""
        elements = payload.get("elements")
        if not elements:
            return ""
        return self._render_text_elements(elements, inline_block_visited, replace_newline=replace_newline)

    def _map_lang(self, lang_id: int) -> str:
        mapping = {1: "text", 2: "python", 3: "javascript", 4: "java", 5: "sql", 6: "go", 7: "cpp", 8: "php", 9: "ruby", 10: "rust"}
        return mapping.get(lang_id, "text")

    def _map_align(self, align: Any) -> str:
        if isinstance(align, str) and align in ('left', 'center', 'right'):
            return align
        mapping = {1: "left", 2: "center", 3: "right"}
        try:
            return mapping.get(int(align), "left")
        except:
            return "left"

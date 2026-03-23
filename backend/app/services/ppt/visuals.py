"""
视觉资源服务
集成 ComfyUI (Stable Diffusion)、Mermaid 图表、Unsplash/Pexels 图库、banana-slides AI
"""
import httpx
import base64
import json
import asyncio
import uuid
import logging
from typing import Optional, List, Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)


class VisualService:
    """统一的视觉资源服务"""

    def __init__(self):
        self.comfy_url = settings.COMFYUI_URL
        self.mermaid_api = "https://mermaid.ink/img/"
        self.unsplash_api = "https://api.unsplash.com"

    # ==================== ComfyUI / Stable Diffusion ====================

    async def generate_image(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 576,
        model_name: Optional[str] = None,
        steps: Optional[int] = None,
        cfg: Optional[float] = None,
    ) -> Optional[bytes]:
        """
        使用 ComfyUI 生成图片。

        Args:
            prompt: 正向提示词
            negative_prompt: 负向提示词
            width: 图片宽度（默认 16:9 比例）
            height: 图片高度
            model_name: SD 模型名称（覆盖默认配置）
            steps: 采样步数（覆盖默认配置）
            cfg: CFG Scale（覆盖默认配置）

        Returns:
            生成的图片字节数据，失败返回 None
        """
        if not settings.ENABLE_SD:
            return None

        try:
            # 使用 ImageGeneratorService 构建增强工作流
            from .image_generator import ImageGeneratorService
            img_gen = ImageGeneratorService()
            workflow = img_gen.build_workflow(
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                model_name=model_name,
                steps=steps,
                cfg=cfg,
            )

            async with httpx.AsyncClient(timeout=120.0) as client:
                client_id = str(uuid.uuid4())
                response = await client.post(
                    f"{self.comfy_url}/prompt",
                    json={"prompt": workflow, "client_id": client_id},
                )

                if response.status_code != 200:
                    logger.warning(f"ComfyUI 提交失败: {response.text}")
                    return None

                result = response.json()
                prompt_id = result.get("prompt_id")

                if not prompt_id:
                    return None

                image_data = await self._wait_for_comfy_result(client, prompt_id)
                return image_data

        except Exception as e:
            logger.warning(f"ComfyUI 图片生成失败: {e}")
            return None

    async def _wait_for_comfy_result(
        self, client: httpx.AsyncClient, prompt_id: str, max_wait: int = 120
    ) -> Optional[bytes]:
        """轮询等待 ComfyUI 完成并获取图片"""
        for _ in range(max_wait):
            await asyncio.sleep(1)

            try:
                response = await client.get(f"{self.comfy_url}/history/{prompt_id}")
                if response.status_code != 200:
                    continue

                history = response.json()
                if prompt_id not in history:
                    continue

                outputs = history[prompt_id].get("outputs", {})
                for node_id, node_output in outputs.items():
                    if "images" in node_output:
                        for img in node_output["images"]:
                            img_response = await client.get(
                                f"{self.comfy_url}/view",
                                params={
                                    "filename": img["filename"],
                                    "subfolder": img.get("subfolder", ""),
                                    "type": img.get("type", "output"),
                                },
                            )
                            if img_response.status_code == 200:
                                return img_response.content
            except Exception:
                continue

        return None

    # ==================== Mermaid 图表 ====================

    def get_mermaid_image_url(self, mermaid_code: str) -> str:
        """将 Mermaid 代码转换为 PNG 图片 URL"""
        encoded = base64.b64encode(mermaid_code.encode("utf-8")).decode("utf-8")
        return f"{self.mermaid_api}{encoded}"

    async def fetch_mermaid_image(
        self, mermaid_code: str, theme: str = "default"
    ) -> Optional[bytes]:
        """
        获取 Mermaid 图表图片（远程 API）。

        Args:
            mermaid_code: Mermaid 语法代码
            theme: 主题（default, dark, forest, neutral）

        Returns:
            图片字节数据
        """
        # 添加主题配置
        themed_code = f"%%{{init: {{'theme': '{theme}'}}}}%%\n{mermaid_code}"
        url = self.get_mermaid_image_url(themed_code)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    return response.content
        except Exception as e:
            logger.warning(f"Mermaid 图片获取失败: {e}")

        # 重试：不带主题
        try:
            url = self.get_mermaid_image_url(mermaid_code)
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    return response.content
        except Exception:
            pass

        return None

    async def fetch_mermaid_image_smart(
        self, mermaid_code: str, theme: str = "default"
    ) -> Optional[bytes]:
        """
        智能获取 Mermaid 图表图片。
        优先使用本地 mermaid-cli，失败回退到远程 mermaid.ink API。

        Args:
            mermaid_code: Mermaid 语法代码
            theme: 主题
        """
        from .image_generator import ImageGeneratorService
        img_gen = ImageGeneratorService()
        return await img_gen.get_mermaid_image(mermaid_code, theme=theme, visual_service=self)

    # ==================== Unsplash 图库 ====================

    async def search_unsplash(self, query: str, count: int = 1) -> List[str]:
        """
        搜索 Unsplash 图片。

        Args:
            query: 搜索关键词
            count: 返回图片数量

        Returns:
            图片 URL 列表
        """
        access_key = getattr(settings, "UNSPLASH_ACCESS_KEY", "")
        if not access_key:
            return []

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{self.unsplash_api}/search/photos",
                    params={
                        "query": query,
                        "per_page": count,
                        "orientation": "landscape",
                    },
                    headers={"Authorization": f"Client-ID {access_key}"},
                )

                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])
                    return [r["urls"]["regular"] for r in results]
        except Exception as e:
            logger.warning(f"Unsplash 搜索失败: {e}")

        return []

    async def fetch_unsplash_image(self, query: str) -> Optional[bytes]:
        """根据关键词获取一张 Unsplash 图片"""
        urls = await self.search_unsplash(query, count=1)
        if not urls:
            return None

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(urls[0])
                if response.status_code == 200:
                    return response.content
        except Exception:
            pass

        return None

    # ==================== Pexels 图库 ====================

    async def search_pexels(self, query: str, count: int = 1) -> List[str]:
        """搜索 Pexels 图片（Unsplash 的备选）。"""
        api_key = getattr(settings, "PEXELS_API_KEY", "")
        if not api_key:
            return []

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    "https://api.pexels.com/v1/search",
                    params={
                        "query": query,
                        "per_page": count,
                        "orientation": "landscape",
                    },
                    headers={"Authorization": api_key},
                )

                if response.status_code == 200:
                    data = response.json()
                    photos = data.get("photos", [])
                    return [p["src"]["large"] for p in photos]
        except Exception as e:
            logger.warning(f"Pexels 搜索失败: {e}")

        return []

    # ==================== 智能图片获取 ====================

    async def get_slide_image(
        self,
        title: str,
        visual_prompt: str = None,
        prefer_ai: bool = True,
        sd_config: Optional[Dict] = None,
    ) -> Optional[bytes]:
        """
        智能获取幻灯片配图。

        优先级：
        1. ComfyUI 生成（如果启用）
        2. Unsplash 搜索
        3. Pexels 搜索

        Args:
            title: 幻灯片标题
            visual_prompt: AI 生成提示词（可选）
            prefer_ai: 是否优先使用 AI 生成
            sd_config: SD 参数覆盖

        Returns:
            图片字节数据
        """
        prompt = visual_prompt or title

        # 1. 尝试 AI 生成
        if prefer_ai and settings.ENABLE_SD:
            model_name = sd_config.get("model") if sd_config else None
            steps = sd_config.get("steps") if sd_config else None
            cfg = sd_config.get("cfg") if sd_config else None
            image = await self.generate_image(
                prompt, model_name=model_name, steps=steps, cfg=cfg
            )
            if image:
                return image

        # 2. 尝试 Unsplash
        keywords = title.split()[:3]
        search_query = " ".join(keywords) if keywords else title

        image = await self.fetch_unsplash_image(search_query)
        if image:
            return image

        # 3. 尝试 Pexels
        urls = await self.search_pexels(search_query, count=1)
        if urls:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(urls[0])
                    if response.status_code == 200:
                        return response.content
            except Exception:
                pass

        return None

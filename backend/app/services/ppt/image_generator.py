"""
统一 AI 图片生成服务
整合 ComfyUI/Stable Diffusion、Mermaid 图表渲染、图库搜索等多种图片来源，
按优先级链路自动选择最佳引擎生成幻灯片配图。
"""
import logging
import subprocess
import tempfile
import base64
import json
from typing import Optional, Dict, Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class ImageGeneratorService:
    """
    统一图片生成服务

    优先级链路：
    1. ComfyUI / Stable Diffusion（本地 GPU 生成）
    2. banana-slides AI（Gemini 图片生成）
    3. Unsplash 图库搜索
    4. Pexels 图库搜索
    5. 返回 None（优雅降级）
    """

    def __init__(self):
        self.comfy_url = settings.COMFYUI_URL
        self.sd_enabled = settings.ENABLE_SD
        self.sd_model = getattr(settings, "SD_MODEL_NAME", "sd_xl_base_1.0.safetensors")
        self.sd_steps = getattr(settings, "SD_STEPS", 20)
        self.sd_cfg = getattr(settings, "SD_CFG", 7.0)

    # ==================== ComfyUI 增强工作流 ====================

    def build_workflow(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 576,
        model_name: Optional[str] = None,
        steps: Optional[int] = None,
        cfg: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        构建 ComfyUI 工作流，支持 SDXL / SD1.5 / FLUX 等多种模型。

        Args:
            prompt: 正向提示词
            negative_prompt: 负向提示词
            width: 图片宽度
            height: 图片高度
            model_name: 模型文件名（覆盖默认）
            steps: 采样步数（覆盖默认）
            cfg: CFG Scale（覆盖默认）
        """
        ckpt = model_name or self.sd_model
        step_count = steps or self.sd_steps
        cfg_scale = cfg or self.sd_cfg

        # NOTE: 根据模型名自动调整采样器
        sampler = "euler"
        scheduler = "normal"
        if "flux" in ckpt.lower():
            sampler = "euler"
            scheduler = "simple"
            cfg_scale = 1.0  # FLUX 模型 CFG 固定为 1.0

        return {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": -1,
                    "steps": step_count,
                    "cfg": cfg_scale,
                    "sampler_name": sampler,
                    "scheduler": scheduler,
                    "denoise": 1.0,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0],
                },
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": ckpt},
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "width": width,
                    "height": height,
                    "batch_size": 1,
                },
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": f"professional presentation slide, {prompt}, high quality, detailed, clean design",
                    "clip": ["4", 1],
                },
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": negative_prompt or "blurry, low quality, text, watermark, logo, ugly",
                    "clip": ["4", 1],
                },
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["3", 0],
                    "vae": ["4", 2],
                },
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": "ppt_slide",
                    "images": ["8", 0],
                },
            },
        }

    # ==================== Mermaid 本地渲染 ====================

    async def render_mermaid_local(self, mermaid_code: str, theme: str = "default") -> Optional[bytes]:
        """
        使用本地 mermaid-cli (mmdc) 渲染 Mermaid 图表为 PNG。
        需要先安装：npm install -g @mermaid-js/mermaid-cli

        Args:
            mermaid_code: Mermaid 语法代码
            theme: 主题（default, dark, forest, neutral）

        Returns:
            PNG 图片字节数据，失败返回 None
        """
        cli_path = getattr(settings, "MERMAID_CLI_PATH", "")
        mmdc = cli_path or "mmdc"

        try:
            with tempfile.NamedTemporaryFile(suffix=".mmd", mode="w", delete=False) as mmd_file:
                mmd_file.write(mermaid_code)
                mmd_path = mmd_file.name

            out_path = mmd_path.replace(".mmd", ".png")

            result = subprocess.run(
                [mmdc, "-i", mmd_path, "-o", out_path, "-t", theme, "-b", "transparent", "-s", "2"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                with open(out_path, "rb") as f:
                    return f.read()
            else:
                logger.warning(f"mermaid-cli 渲染失败: {result.stderr}")
                return None
        except FileNotFoundError:
            logger.debug("mermaid-cli (mmdc) 未安装，跳过本地渲染")
            return None
        except subprocess.TimeoutExpired:
            logger.warning("mermaid-cli 渲染超时")
            return None
        except Exception as e:
            logger.warning(f"Mermaid 本地渲染异常: {e}")
            return None

    # ==================== 智能图片获取 ====================

    async def get_best_image(
        self,
        title: str,
        visual_prompt: Optional[str] = None,
        visual_service=None,
        banana_service=None,
        prefer_ai: bool = True,
        sd_config: Optional[Dict] = None,
    ) -> Optional[bytes]:
        """
        智能获取幻灯片配图，按优先级链路自动选择最佳引擎。

        优先级：
        1. ComfyUI/SD（如果启用且可用）
        2. banana-slides AI（如果可用）
        3. Unsplash
        4. Pexels
        5. None

        Args:
            title: 幻灯片标题
            visual_prompt: AI 生成提示词
            visual_service: VisualService 实例
            banana_service: BananaSlidesService 实例
            prefer_ai: 是否优先使用 AI
            sd_config: SD 参数覆盖（model, steps, cfg, width, height）
        """
        prompt = visual_prompt or title

        # 1. ComfyUI / Stable Diffusion
        if prefer_ai and self.sd_enabled and visual_service:
            try:
                width = sd_config.get("width", 1024) if sd_config else 1024
                height = sd_config.get("height", 576) if sd_config else 576
                image = await visual_service.generate_image(prompt, width=width, height=height)
                if image:
                    logger.info(f"ComfyUI 生成图片成功: {title[:30]}")
                    return image
            except Exception as e:
                logger.warning(f"ComfyUI 生成失败: {e}")

        # 2. banana-slides AI 图片生成
        if prefer_ai and banana_service:
            try:
                image = await banana_service.generate_slide_image(prompt)
                if image:
                    logger.info(f"banana-slides 生成图片成功: {title[:30]}")
                    return image
            except Exception as e:
                logger.warning(f"banana-slides 生成失败: {e}")

        # 3. Unsplash
        if visual_service:
            keywords = title.split()[:3]
            search_query = " ".join(keywords) if keywords else title
            image = await visual_service.fetch_unsplash_image(search_query)
            if image:
                return image

            # 4. Pexels
            urls = await visual_service.search_pexels(search_query, count=1)
            if urls:
                import httpx
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        response = await client.get(urls[0])
                        if response.status_code == 200:
                            return response.content
                except Exception:
                    pass

        return None

    # ==================== Mermaid 智能渲染 ====================

    async def get_mermaid_image(
        self,
        mermaid_code: str,
        theme: str = "default",
        visual_service=None,
    ) -> Optional[bytes]:
        """
        智能获取 Mermaid 图表图片。
        优先使用本地 mermaid-cli，失败时回退到远程 mermaid.ink API。

        Args:
            mermaid_code: Mermaid 语法代码
            theme: 图表主题
            visual_service: VisualService 实例（用于远程回退）
        """
        # 1. 尝试本地渲染
        image = await self.render_mermaid_local(mermaid_code, theme=theme)
        if image:
            return image

        # 2. 回退到远程 API（通过 VisualService）
        if visual_service:
            return await visual_service.fetch_mermaid_image(mermaid_code, theme=theme)

        return None

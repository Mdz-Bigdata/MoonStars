from app.services.video_assistant.gpt.base import GPT
from app.services.video_assistant.gpt.prompt_builder import generate_base_prompt
from app.services.video_assistant.models.gpt_model import GPTSource
from app.services.video_assistant.gpt.prompt import BASE_PROMPT, AI_SUM, SCREENSHOT, LINK
from app.services.video_assistant.gpt.utils import fix_markdown
from app.services.video_assistant.models.transcriber_model import TranscriptSegment
from app.services.video_assistant.utils.logger import get_logger
from datetime import timedelta
from typing import List

logger = get_logger(__name__)





class UniversalGPT(GPT):
    def __init__(self, client, model: str, temperature: float = 0.7, base_url: str = ""):
        self.client = client
        self.model = model
        self.temperature = temperature
        self.base_url = base_url or ""
        self.screenshot = False
        self.link = False

    def _format_time(self, seconds: float) -> str:
        return str(timedelta(seconds=int(seconds)))[2:]

    def _build_segment_text(self, segments: List[TranscriptSegment]) -> str:
        return "\n".join(
            f"{self._format_time(seg.start)} - {seg.text.strip()}"
            for seg in segments
        )

    def ensure_segments_type(self, segments) -> List[TranscriptSegment]:
        return [TranscriptSegment(**seg) if isinstance(seg, dict) else seg for seg in segments]

    def create_messages(self, segments: List[TranscriptSegment], **kwargs):

        content_text = generate_base_prompt(
            title=kwargs.get('title'),
            segment_text=self._build_segment_text(segments),
            tags=kwargs.get('tags'),
            _format=kwargs.get('_format'),
            style=kwargs.get('style'),
            extras=kwargs.get('extras'),
        )

        # ⛳ 组装 content 数组，支持 text + image_url 混合
        video_img_urls = kwargs.get('video_img_urls', [])

        # 检查是否为视觉模型（简单启发式判断）
        model_lower = self.model.lower()
        url_lower = self.base_url.lower()
        
        # 常见支持视觉的模型关键字
        vision_keywords = ["gpt-4o", "gpt-4-vision", "claude-3", "gemini", "vl", "qwen-vl", "phi-3-vision", "vision", "image"]
        is_vision_model = any(kw in model_lower for kw in vision_keywords)
        
        # 针对特定供应商做强规则排除
        if "deepseek" in model_lower or "deepseek" in url_lower:
            is_vision_model = False
            
        if "openai" in url_lower and "gpt-3.5" in model_lower:
            is_vision_model = False

        # OpenAI 官方格式通常只在有图片时才强制要求 input.messages.0.content 为 list，
        # 如果是普通文本模型，或者没有提供图片，强制转回 string 类型以避免通义千问等模型报错 (Input should be a valid list/string)
        if is_vision_model and video_img_urls:
            # 视觉模型：使用 content list 格式
            content = [{"type": "text", "text": content_text}]
            # 限制发送给 AI 的图片数量，防止 413 错误
            max_images = 3
            limited_urls = video_img_urls[:max_images]
            
            for url in limited_urls:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": url,
                        "detail": "auto"
                    }
                })
            messages = [{"role": "user", "content": content}]
        else:
            # 非视觉模型或无图片：严格使用纯文本字符串，增加对 Qwen, DeepSeek 等模型的兼容性
            if video_img_urls and not is_vision_model:
                logger.info(f"模型 {self.model} 或 Provider {self.base_url} 不支持视觉能力，已跳过图片发送")
            
            messages = [{"role": "user", "content": content_text}]

        return messages

    def list_models(self):
        return self.client.models.list()

    def summarize(self, source: GPTSource) -> str:
        self.screenshot = source.screenshot
        self.link = source.link
        source.segment = self.ensure_segments_type(source.segment)

        messages = self.create_messages(
            source.segment,
            title=source.title,
            tags=source.tags,
            video_img_urls=source.video_img_urls,
            _format=source._format,
            style=source.style,
            extras=source.extras
        )
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()

"""
PPT 数据模型
扩展模型以支持多引擎（标准/AI视觉/混合）PPT 生成
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class GenerationMode(str, Enum):
    """PPT 生成模式枚举"""
    STANDARD = "standard"       # 标准模式：python-pptx 结构化生成
    AI_VISUAL = "ai_visual"     # AI 视觉模式：banana-slides 全图式生成
    HYBRID = "hybrid"           # 混合模式：AI 背景 + 结构化文字叠加


class LayoutType(str, Enum):
    """幻灯片布局类型"""
    TEXT_ONLY = "text_only"           # 纯文字
    TEXT_IMAGE = "text_image"         # 左文右图
    IMAGE_TEXT = "image_text"         # 左图右文
    FULL_IMAGE = "full_image"         # 全图 + 文字叠加
    TWO_COLUMN = "two_column"         # 双栏布局
    DIAGRAM = "diagram"              # 图表为主
    DATA_CHART = "data_chart"        # 数据图表


class HeadingInfo(BaseModel):
    level: int
    text: str


class ImageInfo(BaseModel):
    src: str
    alt: str


class VisualFragment(BaseModel):
    """可视化碎片：网页截图中的表格、画板、图表等区域截图"""
    id: str  # e.g., 'table_1', 'board_1'
    type: str  # 'table', 'whiteboard', 'screenshot', 'chart'
    data_base64: str  # Base64 编码的截图
    caption: Optional[str] = None


class ScrapedContent(BaseModel):
    """爬取的网页内容"""
    url: str
    title: str
    content: str
    images: List[ImageInfo] = []
    tables: List[str] = []
    visual_fragments: List[VisualFragment] = []
    headings: List[HeadingInfo] = []
    excerpt: Optional[str] = None


class Section(BaseModel):
    """PPT 章节/幻灯片"""
    title: str
    points: List[str]
    table: Optional[str] = None
    visual_fragment_id: Optional[str] = None  # 关联的视觉碎片 ID
    mermaid: Optional[str] = None
    visual_type: Optional[str] = None  # 'mindmap' | 'flowchart' | 'architecture' | 'image'
    visual_prompt: Optional[str] = None
    # NOTE: 新增字段，由 AI 视觉模式和混合模式使用
    layout_type: Optional[str] = None  # LayoutType 值
    background_image_b64: Optional[str] = None  # 背景图 base64
    speaker_notes: Optional[str] = None  # 演讲者备注


class PPTOutline(BaseModel):
    """PPT 大纲"""
    title: str
    subtitle: Optional[str] = None
    sections: List[Section]
    # NOTE: 改为可选，避免 LLM 输出缺少时验证失败
    conclusion: Optional[List[str]] = []


class PPTConfig(BaseModel):
    """PPT 生成配置"""
    engine: GenerationMode = GenerationMode.STANDARD
    theme: str = "light"
    max_slides: int = 20
    language: str = "zh-CN"
    include_images: bool = True
    # Stable Diffusion 参数
    sd_enabled: bool = False
    sd_model: str = "sd_xl_base_1.0.safetensors"
    sd_steps: int = 20
    sd_cfg: float = 7.0
    sd_width: int = 1024
    sd_height: int = 576
    # banana-slides 参数
    banana_ai_provider: str = "gemini"
    banana_resolution: str = "2k"
    # Mermaid 主题
    mermaid_theme: str = "default"  # default | dark | forest | neutral
    # 大纲生成模型
    outline_model: Optional[str] = None  # 覆盖默认模型

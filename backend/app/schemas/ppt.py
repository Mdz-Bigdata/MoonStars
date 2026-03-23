"""
PPT 请求/响应 Schema
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict


class SDConfig(BaseModel):
    """Stable Diffusion 参数配置"""
    enabled: bool = False
    model: str = "sd_xl_base_1.0.safetensors"
    steps: int = 20
    cfg: float = 7.0
    width: int = 1024
    height: int = 576


class GenerateRequest(BaseModel):
    """PPT 生成请求 - 支持 URL 和提示词两种输入方式"""
    urls: Optional[List[str]] = None
    # NOTE: 新增一句话/提示词生成 PPT
    prompt: Optional[str] = None
    mode: str = "summarize"
    theme: str = "light"
    # NOTE: 新增生成引擎选择
    engine: str = "standard"  # standard | ai_visual | hybrid
    options: Optional[dict] = {}
    sd_config: Optional[SDConfig] = None


class JobStatus(BaseModel):
    """PPT 任务状态"""
    id: str
    status: str
    progress: int
    message: str
    downloadUrl: Optional[str] = Field(None, alias="download_url")

    class Config:
        populate_by_name = True


class EngineInfo(BaseModel):
    """PPT 引擎信息"""
    id: str
    name: str
    description: str
    available: bool
    requires: Optional[List[str]] = None

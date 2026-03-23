"""
应用配置管理
使用 pydantic-settings 从环境变量中读取配置
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, Field
from typing import List, Union, Dict
import secrets
import os
from pathlib import Path


class Settings(BaseSettings):
    """应用配置类"""
    
    # 应用基础配置
    APP_NAME: str = "大数据启示录"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    # 如果环境变量未设置，则自动生成一个随机密钥（注意：重启服务会导致密钥变化，生产环境建议固定）
    SECRET_KEY: str = "bili_default_secret_key_for_development_change_in_production"
    
    # 数据库配置
    DATABASE_URL: str
    
    # CORS 配置
    ALLOWED_ORIGINS: Union[List[str], str] = ["http://localhost:5173"]
    
    # 阿里云短信配置
    ALIBABA_CLOUD_ACCESS_KEY_ID: str = ""
    ALIBABA_CLOUD_ACCESS_KEY_SECRET: str = ""
    ALIBABA_CLOUD_SMS_SIGN_NAME: str = ""
    ALIBABA_CLOUD_SMS_TEMPLATE_CODE: str = ""
    
    @field_validator('ALLOWED_ORIGINS', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        """解析 CORS origins - 支持逗号分隔的字符串或列表"""
        if isinstance(v, str):
            # 将逗号分隔的字符串转换为列表
            return [origin.strip() for origin in v.split(',') if origin.strip()]
        return v
    
    # 文件上传配置
    # Use absolute path relative to the project root (backend/) to avoid CWD issues
    UPLOAD_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads")
    MAX_UPLOAD_SIZE: int = 10485760  # 10MB
    
    # 微信支付配置
    WECHAT_APP_ID: str = ""
    WECHAT_MCH_ID: str = ""
    WECHAT_API_KEY: str = ""
    WECHAT_CERT_PATH: str = ""
    WECHAT_KEY_PATH: str = ""
    
    # 支付宝配置
    ALIPAY_APP_ID: str = ""
    ALIPAY_PRIVATE_KEY_PATH: str = ""
    ALIPAY_PUBLIC_KEY_PATH: str = ""
    ALIPAY_SANDBOX: bool = True
    
    # 飞书 API 配置
    FEISHU_APP_ID: str = ""
    FEISHU_APP_SECRET: str = ""
    
    # JWT 认证配置
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 天

    # AI 配置
    # DeepSeek 官方 API（推荐，免费且稳定）
    AI_BASE_URL: str = "https://api.deepseek.com"
    AI_DEFAULT_MODEL: str = "deepseek-chat"
    
    # 针对不同模型的独立 API Key
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = ""
    CLAUDE_API_KEY: str = ""
    CLAUDE_BASE_URL: str = ""  # 可选的 Claude API 自定义地址
    GPT_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    QWEN_API_KEY: str = ""
    QWEN_BASE_URL: str = ""
    GROQ_API_KEY: str = ""
    GROQ_BASE_URL: str = ""
    
    # 允许一个总开关 Key，如果没有针对性的 Key 则使用这个
    AI_API_KEY: str = ""
    
    # 支持的 AI 模型列表（支持 DeepSeek 官方 API 和 OpenRouter 两种格式）
    AI_MODELS: Dict[str, str] = {
        # DeepSeek 官方 API 格式（无前缀）
        "deepseek": "deepseek-chat",
        "deepseek-chat": "deepseek-chat",
        "deepseek-reasoner": "deepseek-reasoner",
        "deepseek-v3": "deepseek-chat",  # V3 使用 deepseek-chat
        
        # OpenRouter 格式（带前缀，用于 OpenRouter 代理）
        "openrouter-deepseek": "deepseek/deepseek-chat",
        "openrouter-deepseek-chat": "deepseek/deepseek-chat",
        "openrouter-deepseek-reasoner": "deepseek/deepseek-reasoner",
        
        # Claude 系列（OpenRouter 格式）
        "claude": "anthropic/claude-3.5-sonnet",
        "claude-opus-4.5": "claude-opus-4-5-20251101",
        "claude-opus-4-5-20251101": "claude-opus-4-5-20251101",
        "claude-sonnet-4.5": "anthropic/claude-sonnet-4-5",
        "claude-haiku-4.5": "anthropic/claude-haiku-4-5",
        
        # OpenAI 系列（OpenRouter 格式）
        "gpt": "openai/gpt-4o",
        "gpt-5.2": "openai/gpt-5.2",
        "gpt-4o": "openai/gpt-4o",
        
        # Google Gemini 系列（OpenRouter 格式）
        "gemini": "google/gemini-pro-1.5",
        "gemini-3-pro": "google/gemini-3-pro",
        "gemini-2.5-flash": "google/gemini-2.5-flash"
    }
    
    # ComfyUI / Stable Diffusion 增强配置
    COMFYUI_URL: str = "http://127.0.0.1:8188"
    ENABLE_SD: bool = False
    SD_MODEL_NAME: str = "sd_xl_base_1.0.safetensors"  # SD 模型文件名
    SD_STEPS: int = 20  # 采样步数
    SD_CFG: float = 7.0  # CFG Scale
    
    # banana-slides 集成配置
    BANANA_SLIDES_ENABLED: bool = False  # 是否启用 banana-slides AI PPT
    BANANA_SLIDES_AI_PROVIDER: str = "gemini"  # AI 提供商：gemini / openai / vertex
    GOOGLE_API_KEY: str = ""  # Gemini API Key（banana-slides 使用）
    GOOGLE_API_BASE: str = "https://generativelanguage.googleapis.com"  # Gemini API 地址
    
    # Mermaid 配置
    MERMAID_CLI_PATH: str = ""  # 本地 mermaid-cli (mmdc) 路径，留空则使用远程 API
    
    # 图库 API 配置（免费套餐足够个人使用）
    UNSPLASH_ACCESS_KEY: str = ""  # https://unsplash.com/developers
    PEXELS_API_KEY: str = ""  # https://www.pexels.com/api/
    
    # Pydantic v2 配置
    model_config = SettingsConfigDict(
        # 使用绝对路径确保能正确找到 .env 文件
        env_file=str(Path(__file__).parent.parent.parent / ".env"),
        case_sensitive=True,
        extra='ignore'  # 忽略 .env 中未定义的字段
    )


# 全局配置实例
settings = Settings()

import logging
from typing import List, Dict, Optional, Any
from openai import AsyncOpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

class AIService:
    """AI 服务类，负责全文总结和对话"""
    
    def __init__(self):
        self.base_url = settings.AI_BASE_URL
        # 缓存客户端以提高效率
        self._clients = {}

    def _get_client(self, model_key: Optional[str] = None, custom_api_key: Optional[str] = None, custom_base_url: Optional[str] = None):
        """根据模型 key 获取对应的 OpenAI 客户端，支持动态覆盖"""
        # 1. 优先使用前端传入的覆盖配置
        api_key = custom_api_key
        base_url = custom_base_url

        if not api_key:
            # 2. 如果没有覆盖，使用环境配置中的具体模型 Key
            key_map = {
                "deepseek": settings.DEEPSEEK_API_KEY,
                "deepseek-chat": settings.DEEPSEEK_API_KEY,
                "deepseek-reasoner": settings.DEEPSEEK_API_KEY,
                "deepseek-v3.2": settings.DEEPSEEK_API_KEY,
                "claude": settings.CLAUDE_API_KEY,
                "claude-opus-4.5": settings.CLAUDE_API_KEY,
                "claude-opus-4-5-20251101": settings.CLAUDE_API_KEY,
                "claude-sonnet-4.5": settings.CLAUDE_API_KEY,
                "claude-haiku-4.5": settings.CLAUDE_API_KEY,
                "gpt": settings.GPT_API_KEY,
                "gpt-5.2": settings.GPT_API_KEY,
                "gpt-4o": settings.GPT_API_KEY,
                "gemini": settings.GEMINI_API_KEY,
                "gemini-3-pro": settings.GEMINI_API_KEY,
                "gemini-2.5-flash": settings.GEMINI_API_KEY,
                "qwen": settings.QWEN_API_KEY,
                "qwen-max": settings.QWEN_API_KEY,
                "qwen-plus": settings.QWEN_API_KEY,
                "qwen-turbo": settings.QWEN_API_KEY,
                "groq": settings.GROQ_API_KEY,
                "llama-3.3-70b-versatile": settings.GROQ_API_KEY,
                "mixtral-8x7b-32768": settings.GROQ_API_KEY
            }
            api_key = key_map.get(model_key) or settings.AI_API_KEY
        
        if not api_key:
            return None
        
        # 3. 根据模型类型选择 Base URL（如果未显式指定）
        if not base_url:
            if model_key and "claude" in model_key.lower():
                base_url = settings.CLAUDE_BASE_URL or self.base_url
            elif model_key and "qwen" in model_key.lower():
                base_url = settings.QWEN_BASE_URL or "https://dashscope.aliyuncs.com/compatible-mode/v1"
            elif model_key and ("llama" in model_key.lower() or "mixtral" in model_key.lower() or "groq" in model_key.lower()):
                base_url = settings.GROQ_BASE_URL or "https://api.groq.com/openai/v1"
            elif model_key and "deepseek" in model_key.lower():
                base_url = settings.DEEPSEEK_BASE_URL or "https://api.deepseek.com"
            else:
                base_url = self.base_url
            
        # 使用缓存以提高效率，缓存 ID 包含模型 key、API Key 和 Base URL
        cache_id = f"{model_key}_{api_key}_{base_url}"
        if cache_id not in self._clients:
            self._clients[cache_id] = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url
            )
        return self._clients[cache_id]

    async def summarize_article(
        self, 
        title: str, 
        content: str, 
        model_key: Optional[str] = None, 
        api_key: Optional[str] = None, 
        base_url: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """对文章内容进行全文总结"""
        client = self._get_client(model_key, api_key, base_url)
        if not client:
            return "AI 服务未配置 API Key"
            
        # 根据传入的 key 获取实际模型，默认使用配置的默认模型
        target_model = settings.AI_MODELS.get(model_key, settings.AI_DEFAULT_MODEL) if model_key else settings.AI_DEFAULT_MODEL
        
        prompt = f"""
        你是一个专业的文章摘要专家。请对以下文章进行深度总结，要求：
        1. 总结应包含核心观点、关键论据和最终结论。
        2. 字数控制在 200-300 字之间。
        3. 语言专业、精炼，吸引读者。
        
        文章标题：{title}
        文章内容：
        {content[:15000]} # 限制长度防止超限
        """
        
        try:
            response = await client.chat.completions.create(
                model=target_model,
                messages=[
                    {"role": "system", "content": "你是一个专业的文案策划和内容专家。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens or 2000,
                temperature=temperature or 0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"AI 总结生成失败: {e}")
            return f"生成总结时出错: {str(e)}"

    async def chat_with_article(
        self, 
        title: str, 
        content: str, 
        history: List[Dict[str, str]], 
        message: str, 
        model_key: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """基于文章内容进行对话"""
        client = self._get_client(model_key, api_key, base_url)
        if not client:
            return "AI 服务未配置 API Key"
            
        target_model = settings.AI_MODELS.get(model_key, settings.AI_DEFAULT_MODEL) if model_key else settings.AI_DEFAULT_MODEL
        
        # 构建消息列表
        messages = [
            {
                "role": "system", 
                "content": f"""你是一个基于当前文章内容的 AI 助手。
                这篇文章的标题是：《{title}》。
                内容如下：
                {content[:15000]}
                
                请基于以上内容回答用户的问题。如果问题不在文章范围内，请礼貌地指出。"""
            }
        ]
        
        # 添加历史记录
        for h in history[-10:]: # 只保留最近 10 条
            messages.append({"role": h["role"], "content": h["content"]})
            
        # 添加当前消息
        messages.append({"role": "user", "content": message})
        
        try:
            response = await client.chat.completions.create(
                model=target_model,
                messages=messages,
                max_tokens=max_tokens or 1000,
                temperature=temperature or 0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"AI 对话失败: {e}")
            return f"对话响应出错: {str(e)}"

    async def reconstruct_document_structure(
        self,
        content_blocks_text: str,
        model_key: Optional[str] = "deepseek",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ) -> str:
        """
        使用 DeepSeek 进行文档语义重构：
        1. 修复由于 PDF 提取导致的断词和非自然换行。
        2. 识别并标记潜在的列表、表格结构。
        3. 保持原始排版逻辑，仅优化文字可读性。
        """
        client = self._get_client(model_key, api_key, base_url)
        if not client:
            return content_blocks_text
            
        target_model = settings.AI_MODELS.get(model_key, "deepseek-chat")
        
        prompt = f"""
        你是一个专业的文档处理专家。下面是从 PDF 中提取出的原始文本内容。由于提取算法限制，可能存在以下问题：
        - 单词被不正常断开（如 'im- plement' 应为 'implement'）。
        - 段落内存在非自然的硬换行。
        - 中文字符间杂乱的空格。
        - 乱码干扰项（如 (cid:123) 或 \ufffd）。

        任务：
        1. 修复上述文本问题，恢复自然的语言流动。
        2. 严禁改变原意，保持所有专业术语不变。
        3. 将修复后的内容返回，保持原有的段落结构，但去除多余的硬换行。
        4. 如果发现内容是乱码或完全不可读，请保留原样。

        待修复文本：
        {content_blocks_text[:8000]}
        """
        
        try:
            response = await client.chat.completions.create(
                model=target_model,
                messages=[
                    {"role": "system", "content": "你是一个极高性能的文档清洗与修复助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1 # 低温度以保持准确性
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"文档语义重构失败: {e}")
            return content_blocks_text

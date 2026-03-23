

from app.services.video_assistant.db.model_dao import insert_model, get_all_models, get_model_by_provider_and_name, delete_model
from app.services.video_assistant.db.provider_dao import get_enabled_providers
from app.services.video_assistant.enums.exception import ProviderErrorEnum
from app.services.video_assistant.exceptions.provider import ProviderError
from app.services.video_assistant.gpt.gpt_factory import GPTFactory
from app.services.video_assistant.gpt.provider.OpenAI_compatible_provider import OpenAICompatibleProvider
from app.services.video_assistant.models.model_config import ModelConfig
from app.services.video_assistant.provider import ProviderService
from app.services.video_assistant.utils.logger import get_logger

logger=get_logger(__name__)
class ModelService:

    @staticmethod
    def _build_model_config(provider: dict) -> ModelConfig:
        return ModelConfig(
            api_key=provider["api_key"],
            base_url=provider["base_url"],
            provider=provider["name"],
            model_name='',
            name=provider["name"],
        )

    @staticmethod
    def get_model_list(provider_id: int, verbose: bool = False):
        provider = ProviderService.get_provider_by_id(provider_id)
        if not provider:
            return []

        try:
            config = ModelService._build_model_config(provider)
            gpt = GPTFactory().from_config(config)
            models = gpt.list_models()
            if verbose:
                print(f"[{provider['name']}] 模型列表: {models}")
            return models
        except Exception as e:
            print(f"[{provider['name']}] 获取模型失败: {e}")
            return []

    @staticmethod
    def get_all_models(verbose: bool = False):
        """
        聚合所有已启用供应商的模型列表 (用于 VideoAssistant 首页选择)
        """
        try:
            from app.services.video_assistant.provider import ProviderService
            enabled_providers = ProviderService.get_enabled_providers()
            
            all_aggregated_models = []
            seen_ids = set()

            for provider in enabled_providers:
                p_id = provider.get('id')
                # 调用 get_all_models_by_id 获取该供应商的全量模型 (本地+远程)
                res = ModelService.get_all_models_by_id(p_id)
                if res and "models" in res:
                    for m in res["models"]:
                        # 全局去重（以 id 为准）
                        if m['id'] not in seen_ids:
                            all_aggregated_models.append(m)
                            seen_ids.add(m['id'])
            
            if verbose:
                logger.info(f"全局聚合模型完成，共 {len(all_aggregated_models)} 个")
                
            return all_aggregated_models
        except Exception as e:
            logger.error(f"全局聚合模型失败: {e}", exc_info=True)
            return []
    @staticmethod
    def get_all_models_safe(verbose: bool = False):
        try:
            raw_models = get_all_models()
            if verbose:
                print(f"所有模型列表: {raw_models}")
            return ModelService._format_models(raw_models)
        except Exception as e:
            print(f"获取所有模型失败: {e}")
            return []
    @staticmethod
    def _format_models(raw_models: list) -> list:
        """
        格式化模型列表
        """
        formatted = []
        for model in raw_models:
            formatted.append({
                "id": model.get("id"),
                "provider_id": model.get("provider_id"),
                "model_name": model.get("model_name"),
                "created_at": model.get("created_at", None),  # 如果有created_at字段
            })
        return formatted
    @staticmethod
    def get_enabled_models_by_provider( provider_id: str|int,):
        from app.services.video_assistant.db.model_dao import get_models_by_provider

        all_models = get_models_by_provider(provider_id)
        enabled_models = all_models
        return enabled_models
    @staticmethod
    def _fetch_remote_models(api_key: str, base_url: str, provider_id: str) -> list:
        """
        统一拉取远程模型列表的逻辑，支持掩码识别、环境变量兜底及不同厂商格式兼容
        """
        serializable_models = []
        try:
            # 1. 凭证清理与兜底
            import os
            
            # 掩码识别：如果是前端传回的 sk-*** 这种格式，说明真实 Key 在后端/环境
            is_masked = api_key and '*' in api_key
            
            final_key = api_key
            if not api_key or is_masked:
                # 尝试从环境变量获取 fallback
                env_map = {
                    "openai": ["OPENAI_API_KEY", "GPT_API_KEY"],
                    "deepseek": ["DEEPSEEK_API_KEY"],
                    "qwen": ["QWEN_API_KEY"],
                    "groq": ["GROQ_API_KEY"],
                    "gemini": ["GEMINI_API_KEY"],
                    "claude": ["CLAUDE_API_KEY"]
                }
                possible_keys = env_map.get(provider_id.lower(), [])
                for pk in possible_keys:
                    val = os.getenv(pk)
                    if val:
                        final_key = val
                        logger.info(f"为供应商 {provider_id} 使用环境变量兜底 API Key: {pk}")
                        break
            
            if not final_key:
                logger.warning(f"供应商 {provider_id} 缺失有效 API Key，无法拉取列表")
                return []

            # 2. 初始化 GPT 客户端进行请求
            # 对于 Gemini，如果不使用 OAuth 认证，OpenAI 兼容模式获取 models 列表会失败 (401/403)
            # 所以使用原生 REST API 获取真实模型列表
            if provider_id.lower() == "gemini":
                import requests
                logger.info(f"[{provider_id}] 使用原生 REST API 自动拉取全量模型列表...")
                url = f"https://generativelanguage.googleapis.com/v1beta/models?key={final_key}"
                res = requests.get(url, timeout=10)
                if res.status_code == 200:
                    models_data = res.json().get("models", [])
                    for m in models_data:
                        # 过滤出支持 generateContent 的核心生成模型，去除前缀 "models/"
                        if "generateContent" in m.get("supportedGenerationMethods", []):
                            m_name = m.get("name", "").replace("models/", "")
                            serializable_models.append({
                                "id": m_name,
                                "model_name": m_name,
                                "provider_id": provider_id
                            })
                    logger.info(f"[{provider_id}] 成功拉取 {len(serializable_models)} 个模型")
                    return serializable_models
                else:
                    logger.warning(f"[{provider_id}] 自动拉取失败，回退至预置列表。状态码: {res.status_code}")
                    return [
                        {"id": "gemini-1.5-pro", "model_name": "gemini-1.5-pro", "provider_id": provider_id},
                        {"id": "gemini-1.5-flash", "model_name": "gemini-1.5-flash", "provider_id": provider_id}
                    ]

            config = ModelConfig(
                name=provider_id,
                provider=provider_id,
                api_key=final_key,
                base_url=base_url,
                model_name="list-check"
            )
            
            gpt = GPTFactory.from_config(config)
            raw_models_data = gpt.list_models()
            logger.info(f"[{provider_id}] 原始模型数据类型: {type(raw_models_data)}")

            # 3. 解析不同格式的结果
            data_list = []
            if hasattr(raw_models_data, 'data'):
                # OpenAI SyncPage 格式
                data_list = raw_models_data.data
            elif isinstance(raw_models_data, list):
                data_list = raw_models_data
            else:
                # 尝试强制转换为列表
                try:
                    data_list = list(raw_models_data)
                except:
                    logger.warning(f"[{provider_id}] 无法确定数据格式，解析可能失败: {raw_models_data}")

            # 提取 ID
            for m in data_list:
                m_id = None
                if isinstance(m, dict):
                    m_id = m.get('id')
                elif hasattr(m, 'id'):
                    m_id = getattr(m, 'id')
                else:
                    m_id = str(m)
                
                if m_id:
                    serializable_models.append({
                        "id": m_id,
                        "model_name": m_id,
                        "provider_id": provider_id
                    })
            
            logger.info(f"[{provider_id}] 成功获取 {len(serializable_models)} 个远程模型")
            
        except Exception as e:
            logger.error(f"[{provider_id}] 远程拉取模型列表失败: {e}")
            
        return serializable_models

    @staticmethod
    def get_all_models_by_id(provider_id: str, verbose: bool = False):
        try:
            logger.info(f"开始获取供应商模型列表 (GET): {provider_id}")
            provider = ProviderService.get_provider_by_id(provider_id)
            if not provider:
                logger.error(f"供应商未找到: {provider_id}")
                return {"models": []}

            # 1. 获取本地数据库内容
            serializable_models = []
            try:
                from app.services.video_assistant.db.model_dao import get_models_by_provider
                local_models = get_models_by_provider(provider_id)
                for lm in local_models:
                    m_id = lm.get('model_name')
                    if m_id:
                        serializable_models.append({
                            "id": m_id, 
                            "model_name": m_id,
                            "provider_id": provider_id
                        })
            except Exception as e:
                logger.warning(f"获取本地模型库失败: {e}")

            # 2. 获取远程 API 内容 (使用 stored api_key)
            remote_models = ModelService._fetch_remote_models(
                api_key=provider.get('api_key'),
                base_url=provider.get('base_url'),
                provider_id=provider_id
            )
            
            # 合并去重
            existing_ids = {m['id'] for m in serializable_models}
            for rm in remote_models:
                if rm['id'] not in existing_ids:
                    serializable_models.append(rm)
                    existing_ids.add(rm['id'])

            return {"models": serializable_models}
        except Exception as e:
            logger.error(f"[{provider_id}] 获取模型库全量过程发生异常: {e}", exc_info=True)
            return {"models": []}
    @staticmethod
    def connect_test(id: str) -> bool:
        provider = ProviderService.get_provider_by_id(id)
        if provider:
            api_key = provider.get('api_key')
            # 同样支持连通性测试时的环境变量兜底
            if not api_key or (isinstance(api_key, str) and '*' in api_key):
                import os
                env_map = {"openai": ["OPENAI_API_KEY"], "deepseek": ["DEEPSEEK_API_KEY"], "qwen": ["QWEN_API_KEY"], "gemini": ["GEMINI_API_KEY"]}
                for pk in env_map.get(id.lower(), []):
                    val = os.getenv(pk)
                    if val:
                        api_key = val
                        break

            if not api_key:
                raise ProviderError(code=ProviderErrorEnum.NOT_FOUND.code, message=ProviderErrorEnum.NOT_FOUND.message)
            
            result = OpenAICompatibleProvider.test_connection(
                api_key=api_key,
                base_url=provider.get('base_url')
            )
            if result:
                return True
            else:
                raise ProviderError(code=ProviderErrorEnum.WRONG_PARAMETER.code, message=ProviderErrorEnum.WRONG_PARAMETER.message)
        raise ProviderError(code=ProviderErrorEnum.NOT_FOUND.code, message=ProviderErrorEnum.NOT_FOUND.message)

    @staticmethod
    def get_models_remote_v2(api_key: str, base_url: str, provider_id: str = "custom") -> dict:
        """
        通过手动提供的凭证实时获取模型列表 (POST)
        """
        remote_models = ModelService._fetch_remote_models(
            api_key=api_key,
            base_url=base_url,
            provider_id=provider_id
        )
        return {"models": remote_models}

    @staticmethod
    def test_connectivity(api_key: str, base_url: str) -> bool:
        """
        直接测试 API 连通性，不依赖数据库中的供应商 ID
        """
        if not api_key:
            return False
            
        return OpenAICompatibleProvider.test_connection(
            api_key=api_key,
            base_url=base_url
        )



    @staticmethod
    def delete_model_by_id( model_id: int) -> bool:
        try:
            delete_model(model_id)
            return True
        except Exception as e:
            print(f"[{model_id}] <UNK>: {e}")
            return False
    @staticmethod
    def add_new_model(provider_id: int, model_name: str) -> bool:
        try:
            # 先查供应商是否存在
            provider = ProviderService.get_provider_by_id(provider_id)
            if not provider:
                print(f"供应商ID {provider_id} 不存在，无法添加模型")
                return False

            # 查询是否已存在同名模型
            existing = get_model_by_provider_and_name(provider_id, model_name)
            if existing:
                print(f"模型 {model_name} 已存在于供应商ID {provider_id} 下，跳过插入")
                return False

            # 插入模型
            insert_model(provider_id=provider_id, model_name=model_name)
            print(f"模型 {model_name} 已成功添加到供应商ID {provider_id}")
            return True
        except Exception as e:
            print(f"添加模型失败: {e}")
            return False

if __name__ == '__main__':
    # 单个 Provider 测试
    print(ModelService.get_model_list(1, verbose=True))

    # 所有 Provider 模型测试
    # print(ModelService.get_all_models(verbose=True))

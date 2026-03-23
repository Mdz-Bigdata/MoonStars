from typing import Optional, Union

from openai import OpenAI

from app.services.video_assistant.utils.logger import get_logger

logging= get_logger(__name__)
class OpenAICompatibleProvider:
    def __init__(self, api_key: str, base_url: str, model: Union[str, None]=None):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    @property
    def get_client(self):
        return self.client

    @staticmethod
    def test_connection(api_key: str, base_url: str) -> bool:
        try:
            # 针对 Gemini 和 火山引擎，直接使用 requests 获取模型列表来进行连通性测试
            # 这样可以避免 OpenAI 客户端自动拼接路径导致 404
            if "gemini" in base_url.lower() or "generativelanguage" in base_url.lower():
                import requests
                logging.info("检测到 Gemini，使用原生 REST API 测试连通性...")
                url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
                res = requests.get(url, timeout=10)
                if res.status_code == 200:
                    logging.info("Gemini 连通性测试成功")
                    return True
                else:
                    logging.info(f"Gemini 连通性测试失败: {res.text}")
                    return False
            
            if "volcengine" in base_url.lower() or "volces" in base_url.lower():
                import requests
                logging.info("检测到火山引擎，测试连通性...")
                # 火山引擎的 base_url 通常是 https://ark.cn-beijing.volces.com/api/v3
                url = base_url.rstrip("/") + "/models"
                headers = {"Authorization": f"Bearer {api_key}"}
                res = requests.get(url, headers=headers, timeout=10)
                if res.status_code == 200:
                    logging.info("火山引擎连通性测试成功")
                    return True
                else:
                    logging.info(f"火山引擎连通性测试失败: {res.text}")
                    return False

            client = OpenAI(api_key=api_key, base_url=base_url)
            model = client.models.list()
            logging.info("连通性测试成功")
            return True
        except Exception as e:
            error_msg = str(e)
            logging.info(f"连通性测试失败：{error_msg}")
            return False
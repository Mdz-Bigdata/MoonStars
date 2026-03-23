from openai import OpenAI

from app.services.video_assistant.gpt.base import GPT
from app.services.video_assistant.gpt.provider.OpenAI_compatible_provider import OpenAICompatibleProvider
from app.services.video_assistant.gpt.universal_gpt import UniversalGPT
from app.services.video_assistant.models.model_config import ModelConfig


class GPTFactory:
    @staticmethod
    def from_config(config: ModelConfig) -> GPT:
        client = OpenAICompatibleProvider(api_key=config.api_key, base_url=config.base_url).get_client
        return UniversalGPT(client=client, model=config.model_name, base_url=config.base_url)
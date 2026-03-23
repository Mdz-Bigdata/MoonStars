from app.services.video_assistant.models.model_config import ModelConfig

if __name__ == '__main__':
    from app.services.video_assistant.gpt.gpt_factory import GPTFactory
    # 构建模型config
    config=ModelConfig(
        id='asas',
        api_key='',
        base_url='',
        model_name="gpt-4o",
        provider='openai',
        name='gpt-4o'
    )
    # 构建GPT
    gpt=GPTFactory().from_config(config)



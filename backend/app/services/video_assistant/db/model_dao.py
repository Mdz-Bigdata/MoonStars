from app.services.video_assistant.db.engine import get_db
from app.services.video_assistant.db.models.models import Model


def get_model_by_provider_and_name(provider_id: str, model_name: str):
    db = next(get_db())
    try:
        model = db.query(Model).filter_by(provider_id=provider_id, model_name=model_name).first()
        if model:
            return {
                "id": model.id,
                "provider_id": model.provider_id,
                "model_name": model.model_name,
                "created_at": model.created_at,
            }
        return None
    finally:
        db.close()


def insert_model(provider_id: str, model_name: str):
    db = next(get_db())
    try:
        model = Model(provider_id=provider_id, model_name=model_name)
        db.add(model)
        db.commit()
        db.refresh(model)
        return {
            "id": model.id,
            "provider_id": model.provider_id,
            "model_name": model.model_name,
            "created_at": model.created_at,
        }
    finally:
        db.close()


def get_models_by_provider(provider_id: str):
    db = next(get_db())
    try:
        models = db.query(Model).filter_by(provider_id=provider_id).all()
        return [{"id": m.id, "model_name": m.model_name} for m in models]
    finally:
        db.close()


def delete_model(model_id: int):
    db = next(get_db())
    try:
        model = db.query(Model).filter_by(id=model_id).first()
        if model:
            db.delete(model)
            db.commit()
    finally:
        db.close()


def get_all_models():
    db = next(get_db())
    try:
        models = db.query(Model).all()
        return [
            {"id": m.id, "provider_id": m.provider_id, "model_name": m.model_name}
            for m in models
        ]
    finally:
        db.close()


def seed_default_models():
    """
    预填充默认模型，确保用户开启供应商后有可选模型
    """
    defaults = [
        # OpenAI
        {"provider_id": "openai", "model_name": "gpt-4o"},
        {"provider_id": "openai", "model_name": "gpt-4o-mini"},
        # DeepSeek
        {"provider_id": "deepseek", "model_name": "deepseek-chat"},
        {"provider_id": "deepseek", "model_name": "deepseek-reasoner"},
        # Claude
        {"provider_id": "Claude", "model_name": "claude-3-5-sonnet-latest"},
        {"provider_id": "Claude", "model_name": "claude-3-5-haiku-latest"},
        # Gemini
        {"provider_id": "gemini", "model_name": "gemini-1.5-flash"},
        {"provider_id": "gemini", "model_name": "gemini-1.5-pro"},
        # Qwen
        {"provider_id": "qwen", "model_name": "qwen-max"},
        {"provider_id": "qwen", "model_name": "qwen-plus"},
    ]

    for item in defaults:
        if not get_model_by_provider_and_name(item["provider_id"], item["model_name"]):
            insert_model(item["provider_id"], item["model_name"])
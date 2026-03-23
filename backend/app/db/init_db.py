from app.core.database import init_db as core_init_db

async def init_db():
    """桥接原有 core.database 的初始化逻辑"""
    await core_init_db()

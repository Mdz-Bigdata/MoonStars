import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from dotenv import load_dotenv

# 修正导入路径 - 这种结构下，如果从 backend 目录运行，应当使用 app.xxx
from app.core.database import init_db
from app import create_app

# 尝试导入可选模块
try:
    from app.db.provider_dao import seed_default_providers
except ImportError:
    seed_default_providers = lambda: None

try:
    from app.exceptions.exception_handlers import register_exception_handlers
except ImportError:
    register_exception_handlers = lambda app: None

try:
    # events.py 在 backend 根目录下
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from events import register_handler
except ImportError:
    register_handler = lambda: None

try:
    from app.services.video_assistant.transcriber.transcriber_provider import get_transcriber
except ImportError:
    get_transcriber = lambda **kwargs: None

try:
    from app.services.video_assistant.utils.ffmpeg_helper import ensure_ffmpeg_or_raise
except ImportError:
    ensure_ffmpeg_or_raise = lambda: None

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 路径计算
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
static_path = os.getenv('STATIC', '/static')
out_dir = os.getenv('OUT_DIR', os.path.join(BASE_DIR, 'static/screenshots'))
static_dir = os.path.join(BASE_DIR, "static")
uploads_dir = os.path.join(BASE_DIR, "uploads")

# 自动创建本地目录
for d in [static_dir, uploads_dir, out_dir]:
    if not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 初始化逻辑
    try:
        register_handler()
        await init_db()
        # 初始化转录器
        get_transcriber(transcriber_type=os.getenv("TRANSCRIBER_TYPE", "gemini"))
        seed_default_providers()
        ensure_ffmpeg_or_raise()
    except Exception as e:
        logger.error(f"Error during lifespan startup: {e}")
    yield

# 创建 FastAPI 实例
app = create_app(lifespan=lifespan)

# CORS 配置
origins = [
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://tauri.localhost",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册异常处理
register_exception_handlers(app)

# 挂载静态文件
app.mount(static_path, StaticFiles(directory=static_dir), name="static")
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

if __name__ == "__main__":
    port = int(os.getenv("BACKEND_PORT", 8483))
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    logger.info(f"Starting server on {host}:{port}")
    import uvicorn
    uvicorn.run(app, host=host, port=port)

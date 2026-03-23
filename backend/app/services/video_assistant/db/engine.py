import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

from app.services.video_assistant.utils.path_helper import get_app_dir

load_dotenv()

# 获取数据目录并设置默认 SQLite 路径
data_dir = get_app_dir()
default_db_path = os.path.join(data_dir, "video_assistant.db")
DEFAULT_DB_URL = f"sqlite:///{default_db_path}"

# 隔离数据库配置，避免冲突
# 强制使用专用的环境变量，如果没提供则回退到本地 SQLite
DATABASE_URL = os.getenv("VIDEO_ASSISTANT_DATABASE_URL") or DEFAULT_DB_URL

# SQLite 需要特定连接参数，其他数据库不需要
engine_args = {}
if DATABASE_URL.startswith("sqlite"):
    engine_args["connect_args"] = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    echo=os.getenv("SQLALCHEMY_ECHO", "false").lower() == "true",
    **engine_args
)

# 开启 WAL 模式以减少 "database is locked" 或 "readonly" 错误
if DATABASE_URL.startswith("sqlite"):
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

# 开启 WAL 模式以减少 "database is locked" 或 "readonly" 错误
if DATABASE_URL.startswith("sqlite"):
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_engine():
    return engine


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
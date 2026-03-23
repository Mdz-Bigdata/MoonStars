from app.services.video_assistant.db.models.models import Model
from app.services.video_assistant.db.models.providers import Provider
from app.services.video_assistant.db.models.video_tasks import VideoTask
from app.services.video_assistant.db.engine import get_engine, Base

def init_db():
    engine = get_engine()

    Base.metadata.create_all(bind=engine)
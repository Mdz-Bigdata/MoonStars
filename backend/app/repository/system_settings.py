from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Any
import json

from app.models.system_settings import SystemSettings

class SystemSettingsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_value(self, key: str, default: Any = None) -> Any:
        try:
            result = await self.db.execute(select(SystemSettings).where(SystemSettings.key == key))
            settings = result.scalar_one_or_none()
            if settings:
                return settings.value
            return default if default is not None else SystemSettings.get_default_config(key)
        except Exception:
            return default

    async def set_value(self, key: str, value: Any, description: Optional[str] = None):
        result = await self.db.execute(select(SystemSettings).where(SystemSettings.key == key))
        settings = result.scalar_one_or_none()
        
        if settings:
            settings.value = value
            if description:
                settings.description = description
        else:
            settings = SystemSettings(key=key, value=value, description=description)
            self.db.add(settings)
        
        await self.db.commit()
        return settings

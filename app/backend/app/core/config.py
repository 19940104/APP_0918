"""FastAPI 應用程式核心設定。"""

from __future__ import annotations

from functools import lru_cache

from app.config.settings import Settings, get_settings


@lru_cache
def get_app_settings() -> Settings:
    """提供 FastAPI 使用的設定物件。"""

    return get_settings()



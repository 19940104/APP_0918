"""FastAPI 服務入口（相容 core/api 兩種 config 路徑）。"""

from __future__ import annotations

from typing import Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.backend.app.api.routes.dashboard import router as dashboard_router

# 相容：優先載入 core.config，找不到時退回 api.config
try:
    from app.backend.app.core.config import get_app_settings  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    from app.backend.app.api.config import get_app_settings  # type: ignore


def create_app() -> FastAPI:
    """建立 FastAPI 實例，註冊中介層與路由。"""
    settings = get_app_settings()

    app = FastAPI(
        title=settings.app.name,
        version="0.1.0",
        docs_url=settings.api.docs_url,
        openapi_url=settings.api.openapi_url,
    )

    # CORS（目前全開；若要收斂可放到 settings 再調整）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 路由（dashboard/... 會被掛在 settings.api.prefix 之下）
    app.include_router(dashboard_router, prefix=settings.api.prefix)

    @app.get("/health", tags=["system"])
    def health_check() -> Dict[str, str]:
        """健康檢查端點。"""
        return {"status": "ok"}

    return app


app = create_app()

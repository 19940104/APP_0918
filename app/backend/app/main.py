"""FastAPI 服務入口。"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.backend.app.api.routes.dashboard import router as dashboard_router
from app.backend.app.core.config import get_app_settings


def create_app() -> FastAPI:
    """建立 FastAPI 實例，並註冊路由。"""

    settings = get_app_settings()
    app = FastAPI(title=settings.app.name, version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(dashboard_router, prefix=settings.api.prefix)

    @app.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        """檢查。"""

        return {"status": "ok"}

    return app


app = create_app()



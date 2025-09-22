"""FastAPI 依賴：Dashboard 控制器。"""

from __future__ import annotations

from fastapi import Depends

from app.backend.app.api.controllers.dashboard_controller import DashboardController
from app.backend.app.db.duckdb import get_duckdb_client
from app.backend.app.repositories.dashboard_repository import DashboardRepository
from app.backend.app.services.dashboard_service import DashboardService
from app.etl.storage.duckdb_client import DuckDBClient


def get_dashboard_controller(client: DuckDBClient = Depends(get_duckdb_client)) -> DashboardController:
    """建立並回傳 DashboardController。"""

    repository = DashboardRepository(client)
    service = DashboardService(repository)
    return DashboardController(service)



"""FastAPI 依賴：Dashboard 控制器（強化版，結構更清楚）。"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.backend.app.api.controllers.dashboard_controller import DashboardController
from app.backend.app.db.duckdb import get_duckdb_client
from app.backend.app.repositories.dashboard_repository import DashboardRepository
from app.backend.app.services.dashboard_service import DashboardService
from app.etl.storage.duckdb_client import DuckDBClient


def get_dashboard_repository(
    client: Annotated[DuckDBClient, Depends(get_duckdb_client)]
) -> DashboardRepository:
    """
    產生 Repository 實例。
    若之後要做假資料或換資料來源，覆寫這個依賴即可（tests / startup wiring）。
    """
    return DashboardRepository(client)


def get_dashboard_service(
    repo: Annotated[DashboardRepository, Depends(get_dashboard_repository)]
) -> DashboardService:
    """產生 Service 實例，便於未來插入快取或權限控制邏輯。"""
    return DashboardService(repo)


def get_dashboard_controller(
    service: Annotated[DashboardService, Depends(get_dashboard_service)]
) -> DashboardController:
    """建立並回傳 DashboardController。"""
    return DashboardController(service)

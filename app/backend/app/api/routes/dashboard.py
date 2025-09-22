"""Dashboard API 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.backend.app.api.dependencies.dashboard import get_dashboard_controller
from app.backend.app.api.controllers.dashboard_controller import DashboardController
from app.backend.app.schemas.dashboard import (
    ActivationInsightResponse,
    EngagementResponse,
    MessageInsightResponse,
    OverviewResponse,
    UsageTrendResponse,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=OverviewResponse)
def read_overview(controller: DashboardController = Depends(get_dashboard_controller)) -> OverviewResponse:
    """首頁 KPI 資料。"""

    return controller.get_overview()


@router.get("/usage", response_model=UsageTrendResponse)
def read_usage(controller: DashboardController = Depends(get_dashboard_controller)) -> UsageTrendResponse:
    """使用率趨勢資料。"""

    return controller.get_usage_trends()


@router.get("/engagement", response_model=EngagementResponse)
def read_engagement(controller: DashboardController = Depends(get_dashboard_controller)) -> EngagementResponse:
    """黏著度相關資料。"""

    return controller.get_engagement()


@router.get("/messages", response_model=MessageInsightResponse)
def read_messages(controller: DashboardController = Depends(get_dashboard_controller)) -> MessageInsightResponse:
    """訊息分析資料。"""

    return controller.get_messages()


@router.get("/activation", response_model=ActivationInsightResponse)
def read_activation(controller: DashboardController = Depends(get_dashboard_controller)) -> ActivationInsightResponse:
    """啟用與留存分析資料。"""

    return controller.get_activation()



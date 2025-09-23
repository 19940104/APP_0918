"""Dashboard API 路由（加強版：更完整的文件化與回應設定）。"""

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

router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    responses={404: {"description": "Not found"}},
)


@router.get(
    "/overview",
    response_model=OverviewResponse,
    response_model_exclude_none=True,
    summary="首頁 KPI",
    description="回傳儀表板首頁所需的關鍵指標（當日活躍、週覆蓋、啟用、訊息）。",
)
def read_overview(controller: DashboardController = Depends(get_dashboard_controller)) -> OverviewResponse:
    return controller.get_overview()


@router.get(
    "/usage",
    response_model=UsageTrendResponse,
    response_model_exclude_none=True,
    summary="使用率趨勢",
    description="回傳全公司與各部門的週覆蓋率趨勢，前端可再聚合為月/季/年視角。",
)
def read_usage(controller: DashboardController = Depends(get_dashboard_controller)) -> UsageTrendResponse:
    return controller.get_usage_trends()


@router.get(
    "/engagement",
    response_model=EngagementResponse,
    response_model_exclude_none=True,
    summary="黏著度（活躍）",
    description="回傳工作日活躍（日）與週活躍趨勢。",
)
def read_engagement(controller: DashboardController = Depends(get_dashboard_controller)) -> EngagementResponse:
    return controller.get_engagement()


@router.get(
    "/messages",
    response_model=MessageInsightResponse,
    response_model_exclude_none=True,
    summary="訊息分析",
    description="回傳訊息趨勢、20/60/20 分布與（若有）排行榜資料。",
)
def read_messages(controller: DashboardController = Depends(get_dashboard_controller)) -> MessageInsightResponse:
    return controller.get_messages()


@router.get(
    "/activation",
    response_model=ActivationInsightResponse,
    response_model_exclude_none=True,
    summary="啟用與留存",
    description="回傳當月啟用率與留存率的時間序列資料（公司層級）。",
)
def read_activation(controller: DashboardController = Depends(get_dashboard_controller)) -> ActivationInsightResponse:
    return controller.get_activation()

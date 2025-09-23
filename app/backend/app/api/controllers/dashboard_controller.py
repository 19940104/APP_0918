"""Dashboard 控制器，負責整理 API 回應（強化版）。"""

from __future__ import annotations

from typing import Dict, List, Optional, Type, TypeVar, Any

from app.backend.app.schemas.dashboard import (
    ActivationInsightResponse,
    ActivationItem,
    EngagementResponse,
    MessageInsightResponse,
    MessageLeaderboardItem,
    MessageDistributionItem,
    MessageTrendItem,
    OverviewResponse,
    DailyActiveKPI,
    WeeklyUsageKPI,
    ActivationKPI,
    MessageKPI,
    UsageTrendItem,
    UsageTrendResponse,
    ActiveSeriesItem,
)
from app.backend.app.services.dashboard_service import DashboardService

T = TypeVar("T")


class DashboardController:
    """負責將服務層資料轉為 Pydantic 模型。"""

    def __init__(self, service: DashboardService) -> None:
        self.service = service

    # -------------------------
    # Overview
    # -------------------------
    def get_overview(self) -> OverviewResponse:
        data: Dict[str, Any] = self.service.get_overview_kpis() or {}
        return OverviewResponse(
            daily_active=self._optional_model(DailyActiveKPI, data.get("daily_active")),
            weekly_usage=self._optional_model(WeeklyUsageKPI, data.get("weekly_usage")),
            activation=self._optional_model(ActivationKPI, data.get("activation")),
            message=self._optional_model(MessageKPI, data.get("message")),
        )

    # -------------------------
    # 使用率趨勢
    # -------------------------
    def get_usage_trends(self) -> UsageTrendResponse:
        data: Dict[str, Any] = self.service.get_usage_trends() or {}
        return UsageTrendResponse(
            company=[UsageTrendItem.model_validate(item) for item in (data.get("company") or [])],
            departments=[UsageTrendItem.model_validate(item) for item in (data.get("departments") or [])],
        )

    # -------------------------
    # 黏著度（活躍）
    # -------------------------
    def get_engagement(self) -> EngagementResponse:
        data: Dict[str, Any] = self.service.get_engagement_trends() or {}
        return EngagementResponse(
            daily=[ActiveSeriesItem.model_validate(item) for item in (data.get("daily") or [])],
            weekly=[UsageTrendItem.model_validate(item) for item in (data.get("weekly") or [])],
        )

    # -------------------------
    # 訊息洞察
    # -------------------------
    def get_messages(self) -> MessageInsightResponse:
        data: Dict[str, Any] = self.service.get_message_insights() or {}
        return MessageInsightResponse(
            trend=[MessageTrendItem.model_validate(item) for item in (data.get("trend") or [])],
            distribution=[MessageDistributionItem.model_validate(item) for item in (data.get("distribution") or [])],
            # 新版管線沒有 leaderboard 也不會報錯；回傳空陣列即可
            leaderboard=[MessageLeaderboardItem.model_validate(item) for item in (data.get("leaderboard") or [])],
        )

    # -------------------------
    # 啟用 / 留存
    # -------------------------
    def get_activation(self) -> ActivationInsightResponse:
        data: Dict[str, Any] = self.service.get_activation_insights() or {}
        activation = [ActivationItem.model_validate(item) for item in (data.get("activation") or [])]
        retention = [ActivationItem.model_validate(item) for item in (data.get("retention") or [])]
        return ActivationInsightResponse(activation=activation, retention=retention)

    # -------------------------
    # helper
    # -------------------------
    def _optional_model(self, model_cls: Type[T], payload: Optional[Dict[str, object]]) -> Optional[T]:
        """若 payload 存在則轉成對應 Pydantic 模型；容忍空 dict / None。"""
        if not payload:
            return None
        return model_cls.model_validate(payload)

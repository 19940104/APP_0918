"""Dashboard 控制器，負責整理 API 回應。"""

from __future__ import annotations

from typing import Dict, List, Optional, Type, TypeVar

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

    def get_overview(self) -> OverviewResponse:
        data = self.service.get_overview_kpis()
        return OverviewResponse(
            daily_active=self._optional_model(DailyActiveKPI, data.get("daily_active")),
            weekly_usage=self._optional_model(WeeklyUsageKPI, data.get("weekly_usage")),
            activation=self._optional_model(ActivationKPI, data.get("activation")),
            message=self._optional_model(MessageKPI, data.get("message")),
        )

    def get_usage_trends(self) -> UsageTrendResponse:
        data = self.service.get_usage_trends()
        return UsageTrendResponse(
            company=[UsageTrendItem.model_validate(item) for item in data.get("company", [])],
            departments=[UsageTrendItem.model_validate(item) for item in data.get("departments", [])],
        )

    def get_engagement(self) -> EngagementResponse:
        data = self.service.get_engagement_trends()
        return EngagementResponse(
            daily=[ActiveSeriesItem.model_validate(item) for item in data.get("daily", [])],
            weekly=[UsageTrendItem.model_validate(item) for item in data.get("weekly", [])],
        )

    def get_messages(self) -> MessageInsightResponse:
        data = self.service.get_message_insights()
        return MessageInsightResponse(
            trend=[MessageTrendItem.model_validate(item) for item in data.get("trend", [])],
            distribution=[MessageDistributionItem.model_validate(item) for item in data.get("distribution", [])],
            leaderboard=[MessageLeaderboardItem.model_validate(item) for item in data.get("leaderboard", [])],
        )

    def get_activation(self) -> ActivationInsightResponse:
        data = self.service.get_activation_insights()
        activation = [ActivationItem.model_validate(item) for item in data.get("activation", [])]
        retention = [ActivationItem.model_validate(item) for item in data.get("retention", [])]
        return ActivationInsightResponse(activation=activation, retention=retention)

    def _optional_model(self, model_cls: Type[T], payload: Optional[Dict[str, object]]) -> Optional[T]:
        """若 payload 存在則轉成對應 Pydantic 模型。"""

        if not payload:
            return None
        return model_cls.model_validate(payload)



"""Dashboard API 路由測試。"""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from app.backend.app.main import create_app
from app.backend.app.api.dependencies.dashboard import get_dashboard_controller
from app.backend.app.schemas.dashboard import (
    ActivationInsightResponse,
    ActivationItem,
    EngagementResponse,
    MessageInsightResponse,
    MessageDistributionItem,
    MessageLeaderboardItem,
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


class StubController:
    """提供固定資料的假控制器。"""

    def get_overview(self) -> OverviewResponse:
        return OverviewResponse(
            daily_active=DailyActiveKPI(stat_date=date.today(), active_users=10, total_users=100, active_rate=10.0),
            weekly_usage=WeeklyUsageKPI(stat_date=date.today(), active_users=50, total_users=100, usage_rate=0.5),
            activation=ActivationKPI(
                stat_month=date.today(),
                activated_users=20,
                retained_users=15,
                total_employees=100,
                activation_rate=0.2,
                retention_rate=0.75,
            ),
            message=MessageKPI(stat_date=date.today(), total_messages=200, active_users=50, avg_messages_per_user=4.0),
        )

    def get_usage_trends(self) -> UsageTrendResponse:
        item = UsageTrendItem(stat_date=date.today(), active_users=50, total_users=100, usage_rate=0.5, scope_id=None)
        return UsageTrendResponse(company=[item], departments=[item])

    def get_engagement(self) -> EngagementResponse:
        daily_item = ActiveSeriesItem(stat_date=date.today(), active_users=10, total_users=100, active_rate=10.0)
        weekly_item = UsageTrendItem(stat_date=date.today(), active_users=50, total_users=100, usage_rate=0.5, scope_id=None)
        return EngagementResponse(daily=[daily_item], weekly=[weekly_item])

    def get_messages(self) -> MessageInsightResponse:
        trend = [MessageTrendItem(stat_date=date.today(), total_messages=200, active_users=50, avg_messages_per_user=4.0)]
        distribution = [
            MessageDistributionItem(stat_date=date.today(), segment="top20", user_share=0.2, message_share=0.5, user_count=10)
        ]
        leaderboard = [MessageLeaderboardItem(rank=1, emp_no="E01", unit_id="U1", total_messages=120)]
        return MessageInsightResponse(trend=trend, distribution=distribution, leaderboard=leaderboard)

    def get_activation(self) -> ActivationInsightResponse:
        item = ActivationItem(
            stat_month=date.today(),
            unit_id="U1",
            activated_users=20,
            retained_users=15,
            activation_rate=0.2,
            retention_rate=0.75,
        )
        return ActivationInsightResponse(activation=[item], retention=[item])


app = create_app()
app.dependency_overrides[get_dashboard_controller] = lambda: StubController()
client = TestClient(app)


def test_overview_endpoint_returns_200() -> None:
    """確認 /overview 端點成功回應。"""

    response = client.get("/api/dashboard/overview")
    assert response.status_code == 200
    assert response.json()["daily_active"]["active_users"] == 10


def test_messages_endpoint_contains_leaderboard() -> None:
    """確認 /messages 端點包含排行榜資料。"""

    response = client.get("/api/dashboard/messages")
    assert response.status_code == 200
    data = response.json()
    assert data["leaderboard"][0]["emp_no"] == "E01"



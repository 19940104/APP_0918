"""儀表板服務層，進行商業邏輯運算。"""

from __future__ import annotations

from typing import Any, Dict, List

from app.backend.app.repositories.dashboard_repository import DashboardRepository


class DashboardService:
    """處理儀表板相關商業邏輯。"""

    def __init__(self, repository: DashboardRepository) -> None:
        self.repository = repository

    def get_overview_kpis(self) -> Dict[str, Any]:
        """整合首頁 KPI。"""

        daily_active = self.repository.get_latest_daily_active()
        weekly_usage = self.repository.get_latest_weekly_usage()
        activation = self.repository.get_latest_activation_metrics()
        message_kpi = self.repository.get_latest_message_kpi()

        return {
            "daily_active": daily_active,
            "weekly_usage": weekly_usage,
            "activation": activation,
            "message": message_kpi,
        }

    def get_usage_trends(self) -> Dict[str, List[Dict[str, Any]]]:
        """回傳全公司與部門使用率趨勢。"""

        return {
            "company": self.repository.get_weekly_usage_trend(),
            "departments": self.repository.get_department_usage_trend(),
        }

    def get_engagement_trends(self) -> Dict[str, List[Dict[str, Any]]]:
        """回傳日活躍與週活躍資料。"""

        return {
            "daily": self.repository.get_daily_active_series(),
            "weekly": self.repository.get_weekly_usage_trend(),
        }

    def get_message_insights(self) -> Dict[str, List[Dict[str, Any]]]:
        """回傳訊息量相關資料。"""

        return {
            "trend": self.repository.get_message_trend(),
            "distribution": self.repository.get_message_distribution(),
            "leaderboard": self.repository.get_message_leaderboard(),
        }

    def get_activation_insights(self) -> Dict[str, List[Dict[str, Any]]]:
        """回傳啟用與留存分析資訊。"""

        return {
            "activation": self.repository.get_activation_by_unit(),
            "retention": self.repository.get_retention_by_unit(),
        }



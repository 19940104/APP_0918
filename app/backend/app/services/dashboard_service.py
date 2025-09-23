"""儀表板服務層，進行商業邏輯運算（新版相容、加強容錯）。"""

from __future__ import annotations

from typing import Any, Dict, List

from app.backend.app.repositories.dashboard_repository import DashboardRepository


class DashboardService:
    """處理儀表板相關商業邏輯（薄服務層；主要聚合 Repository 結果）。"""

    def __init__(self, repository: DashboardRepository) -> None:
        self.repository = repository

    def get_overview_kpis(self) -> Dict[str, Any]:
        """
        整合首頁 KPI。
        來源：
          - 日活躍：active_rate_workingday_daily
          - 週覆蓋（公司）：coverage_company_weekly
          - 啟用&留存（公司）：activation_next_month_company + retention_monthly_company
          - 訊息（週彙整對齊舊欄位）：messages_weekly_* 組合
        """
        daily_active = self.repository.get_latest_daily_active() or {}
        weekly_usage = self.repository.get_latest_weekly_usage() or {}
        activation = self.repository.get_latest_activation_metrics() or {}
        message_kpi = self.repository.get_latest_message_kpi() or {}

        return {
            "daily_active": daily_active,
            "weekly_usage": weekly_usage,
            "activation": activation,
            "message": message_kpi,
        }

    def get_usage_trends(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        回傳全公司與部門的週覆蓋率趨勢。
        - company：coverage_company_weekly -> 轉 stat_date / week_label 等欄位
        - departments：coverage_unit_weekly -> 帶出 unit_id/unit_name
        """
        return {
            "company": self.repository.get_weekly_usage_trend() or [],
            "departments": self.repository.get_department_usage_trend() or [],
        }

    def get_engagement_trends(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        黏著度面向：
        - daily：工作日活躍（active_rate_workingday_daily）
        - weekly：沿用公司週覆蓋率作為週活躍趨勢（coverage_company_weekly）
        """
        return {
            "daily": self.repository.get_daily_active_series() or [],
            "weekly": self.repository.get_weekly_usage_trend() or [],
        }

    def get_message_insights(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        訊息相關：
        - trend：messages_weekly_* 組合，對齊舊欄位
        - distribution：message_distribution_weekly_20_60_20（user_share/user_count 目前為 NULL）
        - leaderboard：目前新版未產出，回空陣列
        """
        return {
            "trend": self.repository.get_message_trend() or [],
            "distribution": self.repository.get_message_distribution() or [],
            "leaderboard": self.repository.get_message_leaderboard() or [],
        }

    def get_activation_insights(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        啟用 / 留存（部門層）：
        - 新版暫不產出，Repository 會回空陣列；這裡保持介面相容，前端不會壞。
        """
        return {
            "activation": self.repository.get_activation_by_unit() or [],
            "retention": self.repository.get_retention_by_unit() or [],
        }

"""儀表板資料庫存取層。"""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from app.etl.storage.duckdb_client import DuckDBClient


class DashboardRepository:
    """針對 Dashboard 所需資料的查詢封裝。"""

    def __init__(self, client: DuckDBClient) -> None:
        self.client = client

    def _to_records(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """將 DataFrame 轉換成字典列表。"""

        if df.empty:
            return []
        return df.to_dict(orient="records")

    def get_latest_daily_active(self) -> Dict[str, Any] | None:
        """取得最近一日的日活躍 KPI。"""

        df = self.client.query_dataframe(
            """
            SELECT stat_date, active_users, total_users,
                   COALESCE(active_rate, active_users * 1.0 / NULLIF(total_users, 0)) AS active_rate
            FROM user_active_daily
            ORDER BY stat_date DESC
            LIMIT 1
            """
        )
        return df.iloc[0].to_dict() if not df.empty else None

    def get_latest_weekly_usage(self) -> Dict[str, Any] | None:
        """取得最近一週公司層級使用率。"""

        df = self.client.query_dataframe(
            """
            SELECT stat_date, iso_year, iso_week, week_label, unit_name, active_users, total_users, usage_rate\n            FROM usage_rate_weekly\n            WHERE scope = 'company'\n            ORDER BY iso_year DESC, iso_week DESC
            LIMIT 1
            """
        )
        return df.iloc[0].to_dict() if not df.empty else None

    def get_latest_activation_metrics(self) -> Dict[str, Any] | None:
        """取得最近一個月的啟用與留存。"""

        df = self.client.query_dataframe(
            """
            SELECT stat_month, activated_users, retained_users, total_employees,
                   activation_rate, retention_rate
            FROM activation_monthly
            WHERE unit_id IS NULL
            ORDER BY stat_month DESC
            LIMIT 1
            """
        )
        return df.iloc[0].to_dict() if not df.empty else None

    def get_latest_message_kpi(self) -> Dict[str, Any] | None:
        """取得最近一日訊息量與人均訊息。"""

        df = self.client.query_dataframe(
            """
            SELECT stat_date, total_messages, active_users, avg_messages_per_user, total_employees\n            FROM message_aggregate_daily
            ORDER BY stat_date DESC
            LIMIT 1
            """
        )
        return df.iloc[0].to_dict() if not df.empty else None

    def get_weekly_usage_trend(self) -> List[Dict[str, Any]]:
        """取得公司週使用率趨勢。"""

        df = self.client.query_dataframe(
            """
            SELECT stat_date, iso_year, iso_week, week_label, unit_name, active_users, total_users, usage_rate\n            FROM usage_rate_weekly\n            WHERE scope = 'company'\n            ORDER BY iso_year, iso_week
            """
        )
        return self._to_records(df)

    def get_department_usage_trend(self) -> List[Dict[str, Any]]:
        """取得部門週使用率資料。"""

        df = self.client.query_dataframe(
            """
            SELECT stat_date, iso_year, iso_week, week_label, unit_id, unit_name, usage_rate, active_users, total_users\n            FROM usage_rate_weekly\n            WHERE scope = 'unit'\n            ORDER BY iso_year, iso_week, unit_id
            """
        )
        return self._to_records(df)

    def get_daily_active_series(self) -> List[Dict[str, Any]]:
        """取得日活躍時間序列。"""

        df = self.client.query_dataframe(
            """
            SELECT stat_date, active_users, total_users,
                   COALESCE(active_rate, active_users * 1.0 / NULLIF(total_users, 0)) AS active_rate
            FROM user_active_daily
            ORDER BY stat_date
            """
        )
        return self._to_records(df)

    def get_message_trend(self) -> List[Dict[str, Any]]:
        """取得訊息量趨勢資料。"""

        df = self.client.query_dataframe(
            """
            SELECT stat_date, total_messages, active_users, avg_messages_per_user, total_employees\n            FROM message_aggregate_daily
            ORDER BY stat_date
            """
        )
        return self._to_records(df)

    def get_message_distribution(self) -> List[Dict[str, Any]]:
        """取得 20/60/20 訊息分布資料。"""

        df = self.client.query_dataframe(
            """
            SELECT stat_date, segment, user_share, message_share, user_count
            FROM message_distribution_20_60_20
            ORDER BY stat_date, segment
            """
        )
        return self._to_records(df)

    def get_message_leaderboard(self) -> List[Dict[str, Any]]:
        """取得訊息排行榜前 10。"""

        df = self.client.query_dataframe(
            """
            SELECT rank, emp_no, unit_id, unit_name, total_messages\n            FROM message_leaderboard
            ORDER BY rank
            """
        )
        return self._to_records(df)

    def get_activation_by_unit(self) -> List[Dict[str, Any]]:
        """取得各部門啟用率資料。"""

        df = self.client.query_dataframe(
            """
            SELECT stat_month, unit_id, unit_name, activated_users, activation_rate\n            FROM activation_monthly\n            WHERE unit_id IS NOT NULL\n            ORDER BY stat_month, unit_id
            """
        )
        return self._to_records(df)

    def get_retention_by_unit(self) -> List[Dict[str, Any]]:
        """取得各部門留存率資料。"""

        df = self.client.query_dataframe(
            """
            SELECT stat_month, unit_id, unit_name, retained_users, retention_rate\n            FROM activation_monthly\n            WHERE unit_id IS NOT NULL\n            ORDER BY stat_month, unit_id
            """
        )
        return self._to_records(df)
















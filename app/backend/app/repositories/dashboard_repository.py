"""儀表板資料庫存取層（對齊新版 DuckDB Schema）。"""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from app.etl.storage.duckdb_client import DuckDBClient


class DashboardRepository:
    """針對 Dashboard 所需資料的查詢封裝（使用新版彙總表）。"""

    def __init__(self, client: DuckDBClient) -> None:
        self.client = client

    # ----------------------
    # 小工具
    # ----------------------
    def _to_records(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        if df.empty:
            return []
        return df.to_dict(orient="records")

    # ==========================================================
    # 概觀 KPI
    # ==========================================================
    def get_latest_daily_active(self) -> Dict[str, Any] | None:
        """
        最近一日工作日活躍 KPI
        來源：active_rate_workingday_daily（date, active_users, total_users, active_rate）
        映射：date -> stat_date
        """
        df = self.client.query_dataframe(
            """
            SELECT 
                date AS stat_date,
                active_users,
                total_users,
                COALESCE(active_rate, active_users * 1.0 / NULLIF(total_users, 0)) AS active_rate
            FROM active_rate_workingday_daily
            ORDER BY date DESC
            LIMIT 1
            """
        )
        return df.iloc[0].to_dict() if not df.empty else None

    def get_latest_weekly_usage(self) -> Dict[str, Any] | None:
        """
        最近一週公司層級覆蓋率
        來源：coverage_company_weekly
        映射：
          - stat_date：該 ISO 年週的週一
          - week_label：YYYY-Www
          - active_users := covered_users
          - unit_name 固定 '全公司'
        """
        df = self.client.query_dataframe(
            """
            SELECT
                -- 週一日期
                DATE_TRUNC('week', MAKE_DATE(iso_year, 1, 4)) + (iso_week - 1) * INTERVAL 7 DAY AS stat_date,
                iso_year,
                iso_week,
                printf('%d-W%02d', iso_year, iso_week) AS week_label,
                '全公司' AS unit_name,
                covered_users AS active_users,
                total_users,
                coverage_rate AS usage_rate
            FROM coverage_company_weekly
            ORDER BY iso_year DESC, iso_week DESC
            LIMIT 1
            """
        )
        return df.iloc[0].to_dict() if not df.empty else None

    def get_latest_activation_metrics(self) -> Dict[str, Any] | None:
        """
        最近一個月的「啟用」與「留存」KPI（公司層）。
        來源：
          - activation_next_month_company（hire_month, new_hires, used_next_month, activation_rate）
          - retention_monthly_company（active_month, active_users, registered_total, retention_rate）
        輸出欄位為舊型態相容：
          stat_month, activated_users, retained_users, total_employees, activation_rate, retention_rate
        """
        act = self.client.query_dataframe(
            """
            SELECT 
                hire_month AS stat_month,
                new_hires AS activated_users,
                activation_rate
            FROM activation_next_month_company
            ORDER BY hire_month DESC
            LIMIT 1
            """
        )
        ret = self.client.query_dataframe(
            """
            SELECT 
                active_month AS stat_month,
                active_users AS retained_users,
                registered_total AS total_employees,
                retention_rate
            FROM retention_monthly_company
            ORDER BY active_month DESC
            LIMIT 1
            """
        )

        if act.empty and ret.empty:
            return None

        # 盡量對齊到同一個月份；若無法，取較新的那個月份並盡可能填值
        if not act.empty and not ret.empty:
            # 若月份不同，以較新的為準
            a_month = pd.to_datetime(act.iloc[0]["stat_month"]).date()
            r_month = pd.to_datetime(ret.iloc[0]["stat_month"]).date()
            if a_month >= r_month:
                base = act.iloc[0].to_dict()
                base["retained_users"] = int(ret.iloc[0]["retained_users"])
                base["total_employees"] = int(ret.iloc[0]["total_employees"])
                base["retention_rate"] = float(ret.iloc[0]["retention_rate"])
                return base
            else:
                base = ret.iloc[0].to_dict()
                base["activated_users"] = int(act.iloc[0]["activated_users"])
                base["activation_rate"] = float(act.iloc[0]["activation_rate"])
                return base

        if not act.empty:
            base = act.iloc[0].to_dict()
            base["retained_users"] = None
            base["total_employees"] = None
            base["retention_rate"] = None
            return base

        base = ret.iloc[0].to_dict()
        base["activated_users"] = None
        base["activation_rate"] = None
        return base

    def get_latest_message_kpi(self) -> Dict[str, Any] | None:
        """
        最近一週訊息 KPI（以週粒度輸出，對應舊欄位命名）
        來源：
          - messages_weekly_total（messages）
          - messages_weekly_percapita（messages, total_users, messages_per_user）
        映射：
          stat_date：該週週一
          total_messages := messages
          active_users := total_users（以人均分母表示參與者數）
          avg_messages_per_user := messages_per_user
          total_employees := total_users（無更好分母時沿用）
        """
        df = self.client.query_dataframe(
            """
            WITH t AS (
                SELECT p.iso_year, p.iso_week,
                       p.messages AS messages_percap,
                       p.total_users,
                       p.messages_per_user,
                       COALESCE(t.messages, p.messages) AS total_messages
                FROM messages_weekly_percapita p
                LEFT JOIN messages_weekly_total t
                  ON t.iso_year = p.iso_year AND t.iso_week = p.iso_week
            )
            SELECT
                DATE_TRUNC('week', MAKE_DATE(iso_year, 1, 4)) + (iso_week - 1) * INTERVAL 7 DAY AS stat_date,
                total_messages AS total_messages,
                total_users AS active_users,
                messages_per_user AS avg_messages_per_user,
                total_users AS total_employees
            FROM t
            ORDER BY iso_year DESC, iso_week DESC
            LIMIT 1
            """
        )
        return df.iloc[0].to_dict() if not df.empty else None

    # ==========================================================
    # 趨勢：使用率（公司、部門）、活躍（日）、訊息、分布
    # ==========================================================
    def get_weekly_usage_trend(self) -> List[Dict[str, Any]]:
        """
        公司週覆蓋率趨勢
        來源：coverage_company_weekly
        """
        df = self.client.query_dataframe(
            """
            SELECT
                DATE_TRUNC('week', MAKE_DATE(iso_year, 1, 4)) + (iso_week - 1) * INTERVAL 7 DAY AS stat_date,
                iso_year,
                iso_week,
                printf('%d-W%02d', iso_year, iso_week) AS week_label,
                '全公司' AS unit_name,
                covered_users AS active_users,
                total_users,
                coverage_rate AS usage_rate
            FROM coverage_company_weekly
            ORDER BY iso_year, iso_week
            """
        )
        return self._to_records(df)

    def get_department_usage_trend(self) -> List[Dict[str, Any]]:
        """
        部門週覆蓋率趨勢
        來源：coverage_unit_weekly
        映射：
          unit_id := root_org_id
          unit_name := root_org_name
          active_users := used_users
        """
        df = self.client.query_dataframe(
            """
            SELECT
                DATE_TRUNC('week', MAKE_DATE(iso_year, 1, 4)) + (iso_week - 1) * INTERVAL 7 DAY AS stat_date,
                iso_year,
                iso_week,
                printf('%d-W%02d', iso_year, iso_week) AS week_label,
                root_org_id AS unit_id,
                root_org_name AS unit_name,
                used_users AS active_users,
                total_users,
                coverage_rate AS usage_rate
            FROM coverage_unit_weekly
            ORDER BY iso_year, iso_week, root_org_id
            """
        )
        return self._to_records(df)

    def get_daily_active_series(self) -> List[Dict[str, Any]]:
        """
        工作日（日）活躍趨勢
        來源：active_rate_workingday_daily
        """
        df = self.client.query_dataframe(
            """
            SELECT 
                date AS stat_date,
                active_users,
                total_users,
                COALESCE(active_rate, active_users * 1.0 / NULLIF(total_users, 0)) AS active_rate
            FROM active_rate_workingday_daily
            ORDER BY date
            """
        )
        return self._to_records(df)

    def get_message_trend(self) -> List[Dict[str, Any]]:
        """
        訊息趨勢（週粒度，對齊舊 schema 欄位）
        來源：
          - messages_weekly_total
          - messages_weekly_percapita
        """
        df = self.client.query_dataframe(
            """
            WITH t AS (
                SELECT p.iso_year, p.iso_week,
                       p.messages AS messages_percap,
                       p.total_users,
                       p.messages_per_user,
                       COALESCE(t.messages, p.messages) AS total_messages
                FROM messages_weekly_percapita p
                LEFT JOIN messages_weekly_total t
                  ON t.iso_year = p.iso_year AND t.iso_week = p.iso_week
            )
            SELECT
                DATE_TRUNC('week', MAKE_DATE(iso_year, 1, 4)) + (iso_week - 1) * INTERVAL 7 DAY AS stat_date,
                total_messages AS total_messages,
                total_users AS active_users,
                messages_per_user AS avg_messages_per_user,
                total_users AS total_employees
            FROM t
            ORDER BY iso_year, iso_week
            """
        )
        return self._to_records(df)

    def get_message_distribution(self) -> List[Dict[str, Any]]:
        """
        訊息分布 20/60/20（週）
        來源：message_distribution_weekly_20_60_20
        映射：
          stat_date：該週週一
          目前無 user_share/user_count 欄位，回傳 NULL 以相容舊 schema
        """
        df = self.client.query_dataframe(
            """
            SELECT
                DATE_TRUNC('week', MAKE_DATE(iso_year, 1, 4)) + (iso_week - 1) * INTERVAL 7 DAY AS stat_date,
                segment,
                NULL::DOUBLE AS user_share,
                share_percent / 100.0 AS message_share,
                NULL::INTEGER AS user_count
            FROM message_distribution_weekly_20_60_20
            ORDER BY iso_year, iso_week, segment
            """
        )
        return self._to_records(df)

    def get_message_leaderboard(self) -> List[Dict[str, Any]]:
        """
        訊息排行榜（目前新版管線未產出，回空陣列相容）。
        若日後需要，可新增一張彙總表並在此查詢。
        """
        return []

    # ==========================================================
    # 啟用 / 留存（部門）
    #   ※ 新版管線目前只產出公司層級的啟用/留存；以下兩支暫回空。
    # ==========================================================
    def get_activation_by_unit(self) -> List[Dict[str, Any]]:
        return []

    def get_retention_by_unit(self) -> List[Dict[str, Any]]:
        return []

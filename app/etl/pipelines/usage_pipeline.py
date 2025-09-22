"""APP 使用分析主要 ETL Pipeline。"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, Optional

import pandas as pd

from app.config.settings import settings
from app.etl.pipelines.base import BasePipeline
from app.etl.sources.sql_server import SQLServerSource
from app.etl.storage.duckdb_client import DuckDBClient
from app.etl.utils.logging import get_logger

logger = get_logger(__name__)


class UsageStatsPipeline(BasePipeline):
    """負責將 SQL Server 資料彙整至 DuckDB 的 Pipeline。"""

    name = "usage-stats-pipeline"

    def __init__(
        self,
        sql_source: Optional[SQLServerSource] = None,
        duck_client: Optional[DuckDBClient] = None,
        target_date: Optional[date] = None,
        full_refresh: bool = False,
        lookback_days: int = 90,
    ) -> None:
        self.sql_source = sql_source or SQLServerSource()
        self.duck_client = duck_client or DuckDBClient()
        self.target_date = target_date or date.today() - timedelta(days=1)
        self.full_refresh = full_refresh
        self.lookback_days = lookback_days

    # ------------------------------------------------------------------
    # 抽取階段
    # ------------------------------------------------------------------
    def extract(self) -> Dict[str, pd.DataFrame]:
        """從 SQL Server 擷取各類指標所需原始資料。"""

        logger.info(
            "抽取目標日期：%s (full_refresh=%s, lookback_days=%s)",
            self.target_date,
            self.full_refresh,
            "all" if self.full_refresh else self.lookback_days,
        )

        params = {"target_date": self.target_date}
        if not self.full_refresh:
            params["start_date"] = self.target_date - timedelta(days=self.lookback_days)

        employee_query = """
            WITH RecursiveOrg AS (
                SELECT OrgId AS RootOrgId,
                       OrgName AS RootOrgName,
                       OrgId,
                       OrgName,
                       SuperOrgId
                FROM ClassOrg WITH (NOLOCK)
                WHERE RIGHT(OrgId, 4) = '0000'

                UNION ALL

                SELECT r.RootOrgId,
                       r.RootOrgName,
                       c.OrgId,
                       c.OrgName,
                       c.SuperOrgId
                FROM ClassOrg AS c WITH (NOLOCK)
                INNER JOIN RecursiveOrg AS r ON c.SuperOrgId = r.OrgId
            ),
            EmployeeOrg AS (
                SELECT e.EmpId,
                       e.UnitId,
                       e.OutDate,
                       r.RootOrgId,
                       r.RootOrgName
                FROM empbas AS e WITH (NOLOCK)
                LEFT JOIN RecursiveOrg AS r ON e.UnitId = r.OrgId
            )
            SELECT
                eo.EmpId AS EmpId,
                eo.UnitId AS UnitId,
                eo.OutDate AS OutDate,
                eo.RootOrgId AS RootUnitId,
                eo.RootOrgName AS RootUnitName,
                org.OrgName AS UnitName
            FROM EmployeeOrg AS eo
            LEFT JOIN ClassOrg AS org WITH (NOLOCK)
              ON eo.UnitId = org.OrgId
            OPTION (MAXRECURSION 100)
        """

        if self.full_refresh:
            daily_active_query = """
                SELECT
                    CAST(dua.ActivateTime AS DATE) AS ActiveDate,
                    e.UnitId AS UnitId,
                    dua.EmpId AS EmpId
                FROM UTLife_DailyActivateUser AS dua WITH (NOLOCK)
                INNER JOIN empbas AS e WITH (NOLOCK) ON e.EmpId = dua.EmpId
                WHERE e.OutDate IS NULL
                  AND CAST(dua.ActivateTime AS DATE) <= :target_date
            """

            message_query = """
                SELECT
                    CAST(m.Timestamp AS DATE) AS MsgDate,
                    m.SendEmpid AS EmpId,
                    e.UnitId AS UnitId,
                    COUNT(1) AS MessageCount
                FROM LineGPT_Messages AS m WITH (NOLOCK)
                INNER JOIN empbas AS e WITH (NOLOCK) ON e.EmpId = m.SendEmpid
                WHERE e.OutDate IS NULL
                  AND CAST(m.Timestamp AS DATE) <= :target_date
                GROUP BY CAST(m.Timestamp AS DATE), m.SendEmpid, e.UnitId
            """
        else:
            daily_active_query = """
                SELECT
                    CAST(dua.ActivateTime AS DATE) AS ActiveDate,
                    e.UnitId AS UnitId,
                    dua.EmpId AS EmpId
                FROM UTLife_DailyActivateUser AS dua WITH (NOLOCK)
                INNER JOIN empbas AS e WITH (NOLOCK) ON e.EmpId = dua.EmpId
                WHERE e.OutDate IS NULL
                  AND CAST(dua.ActivateTime AS DATE) BETWEEN :start_date AND :target_date
            """

            message_query = """
                SELECT
                    CAST(m.Timestamp AS DATE) AS MsgDate,
                    m.SendEmpid AS EmpId,
                    e.UnitId AS UnitId,
                    COUNT(1) AS MessageCount
                FROM LineGPT_Messages AS m WITH (NOLOCK)
                INNER JOIN empbas AS e WITH (NOLOCK) ON e.EmpId = m.SendEmpid
                WHERE e.OutDate IS NULL
                  AND CAST(m.Timestamp AS DATE) BETWEEN :start_date AND :target_date
                GROUP BY CAST(m.Timestamp AS DATE), m.SendEmpid, e.UnitId
            """

        device_query = """
            SELECT
                d.EmpId AS EmpId,
                MIN(d.BuildDate) AS FirstInstallDate
            FROM UTLife_DeviceInfoList AS d WITH (NOLOCK)
            INNER JOIN empbas AS e WITH (NOLOCK) ON e.EmpId = d.EmpId
            WHERE e.OutDate IS NULL
            GROUP BY d.EmpId
        """

        return {
            "employees": self.sql_source.fetch_dataframe(employee_query, params=None),
            "daily_active": self.sql_source.fetch_dataframe(daily_active_query, params),
            "messages": self.sql_source.fetch_dataframe(message_query, params),
            "device": self.sql_source.fetch_dataframe(device_query, params=None),
        }

    # ------------------------------------------------------------------
    # 轉換階段
    # ------------------------------------------------------------------
    def transform(self, raw_items: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """利用 pandas 計算指標。"""

        employees = raw_items["employees"].rename(
            columns={
                "EmpId": "emp_id",
                "UnitId": "unit_id",
                "OutDate": "out_date",
                "UnitName": "unit_name",
                "RootUnitId": "root_unit_id",
                "RootUnitName": "root_unit_name",
            }
        )
        if "emp_id" not in employees.columns and "EmpNo" in employees.columns:
            employees.rename(columns={"EmpNo": "emp_id"}, inplace=True)
        required_employee_columns = {
            "emp_id": pd.NA,
            "unit_id": pd.NA,
            "out_date": pd.NA,
            "unit_name": pd.NA,
            "root_unit_id": pd.NA,
            "root_unit_name": pd.NA,
        }
        for column_name, default_value in required_employee_columns.items():
            if column_name not in employees.columns:
                employees[column_name] = default_value
        employees["unit_name"].fillna("\u672a\u5b9a\u7fa9", inplace=True)
        employees["root_unit_name"].fillna(employees["unit_name"], inplace=True)
        employees["agg_unit_id"] = employees["root_unit_id"].where(
            employees["root_unit_id"].notna(), employees["unit_id"]
        )
        employees["agg_unit_name"] = employees["root_unit_name"].where(
            employees["root_unit_name"].notna(), employees["unit_name"]
        )
        employees["agg_unit_name"].fillna("\u672a\u5b9a\u7fa9", inplace=True)

        daily_active = raw_items["daily_active"].rename(
            columns={"ActiveDate": "active_date", "UnitId": "unit_id", "EmpId": "emp_id"}
        )
        if "emp_id" not in daily_active.columns and "EmpNo" in daily_active.columns:
            daily_active.rename(columns={"EmpNo": "emp_id"}, inplace=True)
        messages = raw_items["messages"].rename(
            columns={
                "MsgDate": "stat_date",
                "EmpId": "emp_id",
                "UnitId": "unit_id",
                "MessageCount": "message_count",
            }
        )
        if "emp_id" not in messages.columns:
            for fallback_col in ("SenderEmpNo", "SenderEmpId", "SendEmpid"):
                if fallback_col in messages.columns:
                    messages.rename(columns={fallback_col: "emp_id"}, inplace=True)
                    break
        device = raw_items["device"].rename(
            columns={"EmpId": "emp_id", "FirstInstallDate": "first_install_date"}
        )
        if "emp_id" not in device.columns and "EmpNo" in device.columns:
            device.rename(columns={"EmpNo": "emp_id"}, inplace=True)

        daily_active["active_date"] = pd.to_datetime(daily_active["active_date"], errors="coerce")
        messages["stat_date"] = pd.to_datetime(messages["stat_date"], errors="coerce")
        device["first_install_date"] = pd.to_datetime(device["first_install_date"], errors="coerce")

        active_employees = employees[employees["out_date"].isna()].copy()
        unit_counts = (
            active_employees.groupby(["agg_unit_id", "agg_unit_name"], dropna=False)["emp_id"]
            .nunique()
            .reset_index(name="total_users")
        )
        unit_counts.rename(columns={"agg_unit_id": "unit_id", "agg_unit_name": "unit_name"}, inplace=True)
        company_total = int(active_employees["emp_id"].nunique())
        unit_name_lookup = unit_counts.dropna(subset=["unit_id"]).set_index("unit_id")["unit_name"].to_dict()

        # Attach aggregated root units to usage metrics
        daily_active = daily_active.merge(
            employees[["emp_id", "agg_unit_id", "agg_unit_name"]],
            on="emp_id",
            how="left",
        )
        if "unit_name" not in daily_active.columns:
            daily_active["unit_name"] = pd.NA
        daily_active["unit_id"] = daily_active["agg_unit_id"].where(
            daily_active["agg_unit_id"].notna(), daily_active["unit_id"]
        )
        daily_active["unit_name"] = daily_active["agg_unit_name"].where(
            daily_active["agg_unit_name"].notna(), daily_active["unit_name"]
        )
        daily_active.drop(columns=["agg_unit_id", "agg_unit_name"], inplace=True)

        messages = messages.merge(
            employees[["emp_id", "agg_unit_id", "agg_unit_name"]],
            on="emp_id",
            how="left",
        )
        if "unit_name" not in messages.columns:
            messages["unit_name"] = pd.NA
        messages["unit_id"] = messages["agg_unit_id"].where(
            messages["agg_unit_id"].notna(), messages["unit_id"]
        )
        messages["unit_name"] = messages["agg_unit_name"].where(
            messages["agg_unit_name"].notna(), messages["unit_name"]
        )
        messages.drop(columns=["agg_unit_id", "agg_unit_name"], inplace=True)

        device = device.merge(
            employees[["emp_id", "agg_unit_id", "agg_unit_name"]],
            on="emp_id",
            how="left",
        )
        device["unit_id"] = device["agg_unit_id"].where(
            device["agg_unit_id"].notna(), device.get("unit_id")
        )
        device["unit_name"] = device["agg_unit_name"].where(
            device["agg_unit_name"].notna(), device.get("unit_name")
        )
        device.drop(columns=["agg_unit_id", "agg_unit_name"], inplace=True)

        # ------------------------------------------------------------------
        # 週使用率（全公司 + 部門）
        # ------------------------------------------------------------------
        week_info = daily_active["active_date"].dt.isocalendar()
        daily_active["iso_year"] = week_info["year"].astype("Int64")
        daily_active["iso_week"] = week_info["week"].astype("Int64")
        daily_active["week_label"] = (
            daily_active["iso_year"].astype(str) + "-W" + daily_active["iso_week"].astype(str).str.zfill(2)
        )
        daily_active["week_start"] = daily_active["active_date"] - pd.to_timedelta(
            daily_active["active_date"].dt.weekday, unit="D"
        )
        daily_active["unit_name"] = daily_active["unit_id"].map(unit_name_lookup)

        weekly_unit = (
            daily_active.groupby(
                ["iso_year", "iso_week", "week_label", "week_start", "unit_id", "unit_name"],
                dropna=False,
            )["emp_id"]
            .nunique()
            .reset_index(name="active_users")
        )
        weekly_unit = weekly_unit.merge(unit_counts, how="left", on=["unit_id", "unit_name"])
        weekly_unit["total_users"] = weekly_unit["total_users"].fillna(0).astype(int)
        weekly_unit["usage_rate"] = (
            weekly_unit["active_users"] / weekly_unit["total_users"].replace({0: pd.NA})
        )
        weekly_unit["usage_rate"] = weekly_unit["usage_rate"].fillna(0.0).astype(float)
        weekly_unit["scope"] = "unit"
        weekly_unit["scope_id"] = weekly_unit["unit_id"]
        weekly_unit["unit_name"].fillna("未定義", inplace=True)

        company_weekly = (
            daily_active.groupby(["iso_year", "iso_week", "week_label", "week_start"], dropna=False)["emp_id"]
            .nunique()
            .reset_index(name="active_users")
        )
        company_weekly["total_users"] = company_total
        company_weekly["usage_rate"] = (
            company_weekly["active_users"] / company_weekly["total_users"].replace({0: pd.NA})
        )
        company_weekly["usage_rate"] = company_weekly["usage_rate"].fillna(0.0).astype(float)
        company_weekly["scope"] = "company"
        company_weekly["scope_id"] = None
        company_weekly["unit_id"] = None
        company_weekly["unit_name"] = "全公司"

        usage_all = pd.concat([weekly_unit, company_weekly], ignore_index=True)
        usage_all.rename(columns={"week_start": "stat_date"}, inplace=True)
        usage_all = usage_all[
            [
                "stat_date",
                "iso_year",
                "iso_week",
                "week_label",
                "scope",
                "scope_id",
                "unit_id",
                "unit_name",
                "active_users",
                "total_users",
                "usage_rate",
            ]
        ].sort_values("stat_date")

        # ------------------------------------------------------------------
        # 日活躍
        # ------------------------------------------------------------------
        daily_company = (
            daily_active.groupby("active_date")["emp_id"].nunique().reset_index(name="active_users")
        )
        daily_company["total_users"] = company_total
        daily_company["active_rate"] = (
            daily_company["active_users"] / daily_company["total_users"].replace({0: pd.NA})
        )
        daily_company["active_rate"] = daily_company["active_rate"].fillna(0.0).astype(float)
        daily_company.rename(columns={"active_date": "stat_date"}, inplace=True)

        # ------------------------------------------------------------------
        # 訊息量每日彙總
        # ------------------------------------------------------------------
        device["unit_name"].fillna("\u672a\u5b9a\u7fa9", inplace=True)
        device_active = device[device["emp_id"].isin(active_employees["emp_id"])].copy()
        installed_total = int(device_active["emp_id"].nunique())

        message_daily = messages.groupby("stat_date").agg(
            total_messages=("message_count", "sum"),
            active_users=("emp_id", "nunique"),
        ).reset_index()
        message_daily["avg_messages_per_user"] = (
            message_daily["total_messages"] / message_daily["active_users"].replace({0: pd.NA})
        )
        message_daily["avg_messages_per_user"] = message_daily["avg_messages_per_user"].fillna(0.0).astype(float)
        message_daily["total_employees"] = installed_total

        messages["unit_name"].fillna("\u672a\u5b9a\u7fa9", inplace=True)
        message_user_daily = messages.groupby(["stat_date", "emp_id", "unit_id"], dropna=False).agg(
            message_count=("message_count", "sum")
        ).reset_index()
        message_user_daily["unit_name"] = message_user_daily["unit_id"].map(unit_name_lookup)

        distribution_rows: list[dict[str, object]] = []
        for stat_date, group in message_user_daily.groupby("stat_date"):
            total_messages = group["message_count"].sum()
            user_count = len(group)
            if user_count == 0 or total_messages == 0:
                continue

            sorted_group = group.sort_values("message_count", ascending=False).reset_index(drop=True)
            top_count = max(int(round(user_count * 0.2)), 1)
            mid_count = max(int(round(user_count * 0.6)), 0)
            if top_count + mid_count > user_count:
                mid_count = max(user_count - top_count, 0)
            bottom_count = max(user_count - top_count - mid_count, 0)

            top_messages = sorted_group.iloc[:top_count]["message_count"].sum()
            mid_messages = (
                sorted_group.iloc[top_count : top_count + mid_count]["message_count"]
                .sum()
                if mid_count > 0
                else 0
            )
            bottom_messages = (
                sorted_group.iloc[top_count + mid_count :]["message_count"].sum()
                if bottom_count > 0
                else 0
            )

            distribution_rows.extend(
                [
                    {
                        "stat_date": stat_date,
                        "segment": "\u524d20%",
                        "user_share": top_count / user_count,
                        "message_share": top_messages / total_messages,
                        "user_count": top_count,
                    },
                    {
                        "stat_date": stat_date,
                        "segment": "\u4e2d\u959360%",
                        "user_share": mid_count / user_count,
                        "message_share": mid_messages / total_messages,
                        "user_count": mid_count,
                    },
                    {
                        "stat_date": stat_date,
                        "segment": "\u5f8c20%",
                        "user_share": bottom_count / user_count,
                        "message_share": bottom_messages / total_messages,
                        "user_count": bottom_count,
                    },
                ]
            )

        message_distribution = pd.DataFrame(distribution_rows)

        leaderboard = (
            message_user_daily.groupby("emp_id")
            .agg(total_messages=("message_count", "sum"), unit_id=("unit_id", "first"))
            .reset_index()
            .sort_values("total_messages", ascending=False)
        )
        leaderboard.rename(columns={"emp_id": "emp_no"}, inplace=True)
        leaderboard["unit_name"] = leaderboard["unit_id"].map(unit_name_lookup)
        leaderboard["unit_name"].fillna("未定義", inplace=True)
        leaderboard["rank"] = range(1, len(leaderboard) + 1)
        leaderboard = leaderboard.head(10)

        # ------------------------------------------------------------------
        # 啟用與留存
        # ------------------------------------------------------------------
        device_active["stat_month"] = device_active["first_install_date"].dt.to_period("M").dt.to_timestamp()

        activation_unit = (
            device_active.groupby(["stat_month", "unit_id", "unit_name"], dropna=False)["emp_id"]
            .nunique()
            .reset_index(name="activated_users")
        )

        daily_active["stat_month"] = daily_active["active_date"].dt.to_period("M").dt.to_timestamp()
        retention_monthly = (
            daily_active.groupby(["stat_month", "unit_id", "unit_name"], dropna=False)["emp_id"]
            .nunique()
            .reset_index(name="retained_users")
        )

        activation_summary = activation_unit.merge(
            retention_monthly,
            how="outer",
            on=["stat_month", "unit_id", "unit_name"],
        )
        activation_summary["activated_users"] = activation_summary["activated_users"].fillna(0).astype(int)
        activation_summary["retained_users"] = activation_summary["retained_users"].fillna(0).astype(int)
        activation_summary = activation_summary.merge(
            unit_counts[["unit_id", "unit_name", "total_users"]],
            how="left",
            on=["unit_id", "unit_name"],
        )
        activation_summary.rename(columns={"total_users": "total_employees"}, inplace=True)
        activation_summary["total_employees"] = activation_summary["total_employees"].fillna(0).astype(int)
        activation_summary["activation_rate"] = (
            activation_summary["activated_users"]
            / activation_summary["total_employees"].replace({0: pd.NA})
        )
        activation_summary["activation_rate"] = activation_summary["activation_rate"].fillna(0.0).astype(float)
        activation_summary["retention_rate"] = (
            activation_summary["retained_users"]
            / activation_summary["activated_users"].replace({0: pd.NA})
        )
        activation_summary["retention_rate"] = activation_summary["retention_rate"].fillna(0.0).astype(float)

        company_activation = activation_summary.groupby("stat_month", as_index=False)[
            ["activated_users", "retained_users", "total_employees"]
        ].sum()
        company_activation["activated_users"] = company_activation["activated_users"].astype(int)
        company_activation["retained_users"] = company_activation["retained_users"].astype(int)
        company_activation["total_employees"] = company_activation["total_employees"].astype(int)
        company_activation["activation_rate"] = (
            company_activation["activated_users"]
            / company_activation["total_employees"].replace({0: pd.NA})
        )
        company_activation["activation_rate"] = company_activation["activation_rate"].fillna(0.0).astype(float)
        company_activation["retention_rate"] = (
            company_activation["retained_users"]
            / company_activation["activated_users"].replace({0: pd.NA})
        )
        company_activation["retention_rate"] = company_activation["retention_rate"].fillna(0.0).astype(float)
        company_activation["unit_id"] = None
        company_activation["unit_name"] = "全公司"

        activation_all = pd.concat([activation_summary, company_activation], ignore_index=True)
        activation_all["unit_name"].fillna("未定義", inplace=True)
        activation_all = activation_all[
            [
                "stat_month",
                "unit_id",
                "unit_name",
                "activated_users",
                "retained_users",
                "total_employees",
                "activation_rate",
                "retention_rate",
            ]
        ].sort_values(["stat_month", "unit_id"], na_position="last")

        return {
            "usage_weekly": usage_all,
            "daily_active": daily_company,
            "message_daily": message_daily,
            "message_distribution": message_distribution,
            "message_leaderboard": leaderboard,
            "activation_monthly": activation_all,
        }

    # ------------------------------------------------------------------
    # 載入階段
    # ------------------------------------------------------------------
    def load(self, processed_items: Dict[str, pd.DataFrame]) -> None:
        """將彙總結果寫回 DuckDB。"""

        duck = self.duck_client
        storage = settings.storage

        duck.ensure_table(
            f"""
            CREATE TABLE IF NOT EXISTS {storage.user_daily_table} (
                stat_date DATE,
                active_users INTEGER,
                total_users INTEGER,
                active_rate DOUBLE
            )
            """
        )
        duck.write_dataframe(processed_items["daily_active"], storage.user_daily_table, mode="replace")

        duck.ensure_table(
            f"""
            CREATE TABLE IF NOT EXISTS {storage.message_table} (
                stat_date DATE,
                total_messages INTEGER,
                active_users INTEGER,
                avg_messages_per_user DOUBLE,
                total_employees INTEGER
            )
            """
        )
        duck.write_dataframe(processed_items["message_daily"], storage.message_table, mode="replace")

        duck.ensure_table(
            """
            CREATE TABLE IF NOT EXISTS usage_rate_weekly (
                stat_date DATE,
                iso_year INTEGER,
                iso_week INTEGER,
                week_label VARCHAR,
                scope VARCHAR,
                scope_id VARCHAR,
                unit_id VARCHAR,
                unit_name VARCHAR,
                active_users INTEGER,
                total_users INTEGER,
                usage_rate DOUBLE
            )
            """
        )
        duck.write_dataframe(processed_items["usage_weekly"], "usage_rate_weekly", mode="replace")

        duck.ensure_table(
            """
            CREATE TABLE IF NOT EXISTS message_distribution_20_60_20 (
                stat_date DATE,
                segment VARCHAR,
                user_share DOUBLE,
                message_share DOUBLE,
                user_count INTEGER
            )
            """
        )
        duck.write_dataframe(processed_items["message_distribution"], "message_distribution_20_60_20", mode="replace")

        duck.ensure_table(
            """
            CREATE TABLE IF NOT EXISTS message_leaderboard (
                rank INTEGER,
                emp_no VARCHAR,
                unit_id VARCHAR,
                unit_name VARCHAR,
                total_messages INTEGER
            )
            """
        )
        duck.write_dataframe(processed_items["message_leaderboard"], "message_leaderboard", mode="replace")

        duck.ensure_table(
            """
            CREATE TABLE IF NOT EXISTS activation_monthly (
                stat_month DATE,
                unit_id VARCHAR,
                unit_name VARCHAR,
                activated_users INTEGER,
                retained_users INTEGER,
                total_employees INTEGER,
                activation_rate DOUBLE,
                retention_rate DOUBLE
            )
            """
        )
        duck.write_dataframe(processed_items["activation_monthly"], "activation_monthly", mode="replace")


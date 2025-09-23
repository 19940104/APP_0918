"""APP 使用分析主要 ETL Pipeline（對齊 SQL 定義版）。"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, Optional

import numpy as np
import pandas as pd

from app.etl.pipelines.base import BasePipeline
from app.etl.sources.sql_server import SQLServerSource
from app.etl.storage.duckdb_client import DuckDBClient
from app.etl.utils.logging import get_logger

logger = get_logger(__name__)


class UsageStatsPipeline(BasePipeline):
    """負責將 SQL Server 資料彙整至 DuckDB 的 Pipeline（對齊你提供的 SQL 指標邏輯）。"""

    name = "usage-stats-pipeline"

    # 寫入 DuckDB 的表名（可依需要改名）
    TBL_COVERAGE_COMPANY_WEEKLY = "coverage_company_weekly"
    TBL_COVERAGE_UNIT_WEEKLY = "coverage_unit_weekly"
    TBL_ACTIVE_RATE_WORKINGDAY_DAILY = "active_rate_workingday_daily"
    TBL_ACTIVATION_NEXT_MONTH = "activation_next_month_company"
    TBL_RETENTION_MONTHLY = "retention_monthly_company"
    TBL_MSG_WEEKLY_TOTAL = "messages_weekly_total"
    TBL_MSG_WEEKLY_PERCAPITA = "messages_weekly_percapita"
    TBL_MSG_DISTRIBUTION = "message_distribution_weekly_20_60_20"

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

        # 部門樹（根節點：OrgId 末四碼 = '0000'，排除 '10000'）
        # 員工來源表：empbas_app（含 InDate/OutDate）
        employee_query = """
            WITH RecursiveOrg AS (
                SELECT OrgId AS RootOrgId, OrgName AS RootOrgName,
                       OrgId, OrgName, SuperOrgId
                FROM ClassOrg WITH (NOLOCK)
                WHERE RIGHT(OrgId, 4) = '0000' AND OrgId <> '10000'
                UNION ALL
                SELECT r.RootOrgId, r.RootOrgName,
                       c.OrgId, c.OrgName, c.SuperOrgId
                FROM ClassOrg c WITH (NOLOCK)
                INNER JOIN RecursiveOrg r ON c.SuperOrgId = r.OrgId
            ),
            EmployeeOrg AS (
                SELECT e.EmpId, e.UnitId, e.InDate, e.OutDate,
                       r.RootOrgId, r.RootOrgName
                FROM empbas_app e WITH (NOLOCK)
                LEFT JOIN RecursiveOrg r ON e.UnitId = r.OrgId
            )
            SELECT EmpId, UnitId, InDate, OutDate, RootOrgId, RootOrgName
            FROM EmployeeOrg
            OPTION (MAXRECURSION 100)
        """

        # 活躍紀錄（限定日期範圍）
        if self.full_refresh:
            daily_active_query = """
                SELECT CAST(a.ActivateTime AS DATE) AS ActiveDate,
                       a.EmpId
                FROM UTLife_DailyActivateUser a WITH (NOLOCK)
                WHERE CAST(a.ActivateTime AS DATE) <= :target_date
            """
            message_query = """
                SELECT CAST(m.Timestamp AS DATE) AS MsgDate,
                       m.SendEmpid AS EmpId
                FROM LineGPT_Messages m WITH (NOLOCK)
                WHERE CAST(m.Timestamp AS DATE) <= :target_date
            """
        else:
            daily_active_query = """
                SELECT CAST(a.ActivateTime AS DATE) AS ActiveDate,
                       a.EmpId
                FROM UTLife_DailyActivateUser a WITH (NOLOCK)
                WHERE CAST(a.ActivateTime AS DATE) BETWEEN :start_date AND :target_date
            """
            message_query = """
                SELECT CAST(m.Timestamp AS DATE) AS MsgDate,
                       m.SendEmpid AS EmpId
                FROM LineGPT_Messages m WITH (NOLOCK)
                WHERE CAST(m.Timestamp AS DATE) BETWEEN :start_date AND :target_date
            """

        # 曾經使用過（到 target_date 為止）
        ever_used_query = """
            SELECT DISTINCT a.EmpId
            FROM UTLife_DailyActivateUser a WITH (NOLOCK)
            WHERE CAST(a.ActivateTime AS DATE) <= :target_date
        """

        return {
            "employees": self.sql_source.fetch_dataframe(employee_query, params=None),
            "daily_active": self.sql_source.fetch_dataframe(daily_active_query, params),
            "messages": self.sql_source.fetch_dataframe(message_query, params),
            "ever_used": self.sql_source.fetch_dataframe(ever_used_query, {"target_date": self.target_date}),
        }

    # ------------------------------------------------------------------
    # 轉換階段（完全依照你給的 SQL 指標定義）
    # ------------------------------------------------------------------
    def transform(self, raw: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        # 若缺少新版所需的 ever_used dataset，視為舊版測試/相容情境。
        if "ever_used" not in raw:
            logger.info("使用相容模式轉換舊版資料結構")
            return self._transform_compat(raw)

        employees = raw["employees"].copy()
        daily_active = raw["daily_active"].copy()
        messages = raw["messages"].copy()
        ever_used = raw["ever_used"].copy()

        # 欄位標準化
        employees.rename(
            columns={
                "EmpId": "emp_id",
                "UnitId": "unit_id",
                "InDate": "in_date",
                "OutDate": "out_date",
                "RootOrgId": "root_org_id",
                "RootOrgName": "root_org_name",
            },
            inplace=True,
        )
        daily_active.rename(columns={"ActiveDate": "date", "EmpId": "emp_id"}, inplace=True)
        messages.rename(columns={"MsgDate": "date", "EmpId": "emp_id"}, inplace=True)
        ever_used.rename(columns={"EmpId": "emp_id"}, inplace=True)

        # 轉日期型別
        for col in ("in_date", "out_date"):
            employees[col] = pd.to_datetime(employees[col], errors="coerce")
        daily_active["date"] = pd.to_datetime(daily_active["date"], errors="coerce")
        messages["date"] = pd.to_datetime(messages["date"], errors="coerce")

        # ISO 週資訊 + 每週基準日（使用活躍資料週內最小日期作為基準日）
        if not daily_active.empty:
            iso = daily_active["date"].dt.isocalendar()
            daily_active["iso_year"] = iso["year"].astype(int)
            daily_active["iso_week"] = iso["week"].astype(int)
            week_min = (
                daily_active.groupby(["iso_year", "iso_week"])["date"]
                .min()
                .reset_index()
                .rename(columns={"date": "baseline_date"})
            )
        else:
            week_min = pd.DataFrame(columns=["iso_year", "iso_week", "baseline_date"])

        # 判斷在職：InDate <= d 且 (OutDate 為空 或 OutDate > d)
        def employed_on(d: pd.Timestamp) -> pd.Series:
            return (employees["in_date"] <= d) & (employees["out_date"].isna() | (employees["out_date"] > d))

        # --------------------------------------------------------------
        # 1) 全公司覆蓋率（週）
        # 分子：曾經使用過 ∩ 當週在職；分母：當週在職（以基準日快照）
        # --------------------------------------------------------------
        coverage_company_rows = []
        ever_used_ids = set(ever_used["emp_id"].dropna().astype(str))
        for _, r in week_min.iterrows():
            by = int(r["iso_year"])
            bw = int(r["iso_week"])
            bd = pd.to_datetime(r["baseline_date"])

            mask = employed_on(bd)
            in_service_ids = set(employees.loc[mask, "emp_id"].dropna().astype(str))

            covered = len(in_service_ids & ever_used_ids)
            total = len(in_service_ids)
            rate = (covered / total) if total else 0.0

            coverage_company_rows.append(
                {
                    "iso_year": by,
                    "iso_week": bw,
                    "baseline_date": bd.date(),
                    "covered_users": covered,
                    "total_users": total,
                    "coverage_rate": rate,
                }
            )
        coverage_company_weekly = pd.DataFrame(coverage_company_rows).sort_values(["iso_year", "iso_week"])

        # --------------------------------------------------------------
        # 2) 各部門覆蓋率（週）
        # 分子：該週有使用（週活躍，依 RootOrg）；分母：基準日該部門在職
        # --------------------------------------------------------------
        emp_root = employees[["emp_id", "root_org_id", "root_org_name"]].drop_duplicates()

        if not daily_active.empty:
            weekly_used = (
                daily_active.merge(emp_root, on="emp_id", how="left")
                .groupby(["iso_year", "iso_week", "root_org_id", "root_org_name"])["emp_id"]
                .nunique()
                .reset_index(name="used_users")
            )
        else:
            weekly_used = pd.DataFrame(
                columns=["iso_year", "iso_week", "root_org_id", "root_org_name", "used_users"]
            )

        unit_rows = []
        for _, r in week_min.iterrows():
            by = int(r["iso_year"])
            bw = int(r["iso_week"])
            bd = pd.to_datetime(r["baseline_date"])

            mask = employed_on(bd)
            snap = employees.loc[mask, ["emp_id", "root_org_id", "root_org_name"]].drop_duplicates()
            denom = (
                snap.groupby(["root_org_id", "root_org_name"])["emp_id"].nunique().reset_index(name="total_users")
            )
            if denom.empty:
                continue
            denom["iso_year"] = by
            denom["iso_week"] = bw
            denom["baseline_date"] = bd.date()
            unit_rows.append(denom)

        weekly_unit_den = (
            pd.concat(unit_rows, ignore_index=True)
            if unit_rows
            else pd.DataFrame(
                columns=["root_org_id", "root_org_name", "total_users", "iso_year", "iso_week", "baseline_date"]
            )
        )

        coverage_unit_weekly = (
            weekly_used.merge(
                weekly_unit_den, on=["iso_year", "iso_week", "root_org_id", "root_org_name"], how="left"
            )
            .assign(
                coverage_rate=lambda df: np.where(
                    df["total_users"].fillna(0) > 0, df["used_users"] / df["total_users"], 0.0
                ),
                baseline_date=lambda df: df.get("baseline_date", pd.NaT),
            )
            .sort_values(["iso_year", "iso_week", "root_org_id"])
        )

        # --------------------------------------------------------------
        # 3) 工作日活躍（日）= 週一~週五；分母 = 當日在職（每日快照）
        # --------------------------------------------------------------
        workday = daily_active[daily_active["date"].dt.weekday <= 4].copy()
        daily_active_users = (
            workday.groupby("date")["emp_id"].nunique().reset_index(name="active_users")
            if not workday.empty
            else pd.DataFrame(columns=["date", "active_users"])
        )

        if not daily_active_users.empty:
            unique_days = daily_active_users["date"].drop_duplicates().sort_values()
            denom_rows = []
            for d in unique_days:
                mask = employed_on(pd.to_datetime(d))
                denom_rows.append(
                    {"date": pd.to_datetime(d), "total_users": int(employees.loc[mask, "emp_id"].nunique())}
                )
            daily_total = pd.DataFrame(denom_rows)
        else:
            daily_total = pd.DataFrame(columns=["date", "total_users"])

        active_rate_workingday_daily = (
            daily_active_users.merge(daily_total, on="date", how="left")
            .assign(
                active_rate=lambda df: np.where(
                    df["total_users"].fillna(0) > 0, df["active_users"] / df["total_users"], 0.0
                )
            )
            .sort_values("date")
        )

        # --------------------------------------------------------------
        # 4) 當月啟用率（公司）：入職月份新人 → 次月有使用 / 新人數
        # --------------------------------------------------------------
        employees_nonnull_in = employees.dropna(subset=["in_date"]).copy()
        if employees_nonnull_in.empty:
            activation_next_month_company = pd.DataFrame(
                columns=["hire_month", "new_hires", "used_next_month", "activation_rate"]
            )
        else:
            employees_nonnull_in["hire_month"] = (
                employees_nonnull_in["in_date"].dt.to_period("M").dt.to_timestamp()
            )
            employees_nonnull_in["next_month_start"] = (
                employees_nonnull_in["in_date"].dt.to_period("M").dt.to_timestamp() + pd.offsets.MonthBegin(1)
            )
            employees_nonnull_in["next_month_end"] = (
                employees_nonnull_in["next_month_start"] + pd.offsets.MonthEnd(0)
            )

            da = raw["daily_active"].copy()
            da.rename(columns={"ActiveDate": "date", "EmpId": "emp_id"}, inplace=True) if "ActiveDate" in da.columns else None
            da["date"] = pd.to_datetime(da["date"], errors="coerce")

            nm = employees_nonnull_in[["emp_id", "hire_month", "next_month_start", "next_month_end"]]
            used_nm = (
                da.merge(nm, on="emp_id", how="inner")
                .query("date >= next_month_start and date <= next_month_end")
                .drop_duplicates(subset=["emp_id", "hire_month"])[["emp_id", "hire_month"]]
            )

            agg = employees_nonnull_in.groupby("hire_month")["emp_id"].nunique().reset_index(name="new_hires")
            used = used_nm.groupby("hire_month")["emp_id"].nunique().reset_index(name="used_next_month")
            activation_next_month_company = (
                agg.merge(used, on="hire_month", how="left")
                .fillna({"used_next_month": 0})
                .assign(
                    activation_rate=lambda df: np.where(
                        df["new_hires"] > 0, df["used_next_month"] / df["new_hires"], 0.0
                    )
                )
                .sort_values("hire_month")
            )

        # --------------------------------------------------------------
        # 5) 當月留存率（公司）：自 2025-01-01 起
        # 留存率 = 月活躍人數 / 總註冊人數（>= 2025-01-01 曾經使用過的人數）
        # --------------------------------------------------------------
        baseline = pd.Timestamp("2025-01-01")
        dau = raw["daily_active"].copy()
        dau.rename(columns={"ActiveDate": "date", "EmpId": "emp_id"}, inplace=True) if "ActiveDate" in dau.columns else None
        dau["date"] = pd.to_datetime(dau["date"], errors="coerce")
        dau = dau[dau["date"] >= baseline]

        total_registered = int(dau["emp_id"].dropna().nunique())
        if total_registered == 0:
            retention_monthly_company = pd.DataFrame(
                columns=["active_month", "active_users", "registered_total", "retention_rate"]
            )
        else:
            monthly_active = (
                dau.assign(active_month=dau["date"].dt.to_period("M").dt.to_timestamp())
                .groupby("active_month")["emp_id"]
                .nunique()
                .reset_index(name="active_users")
            )
            monthly_active["registered_total"] = total_registered
            monthly_active["retention_rate"] = monthly_active["active_users"] / monthly_active["registered_total"]
            retention_monthly_company = monthly_active.sort_values("active_month")

        # --------------------------------------------------------------
        # 6) 每週工作日訊息總計 + 人均訊息數（分母 = 該週在職聯集）
        # --------------------------------------------------------------
        msg_wd = messages[messages["date"].dt.weekday <= 4].copy()
        if msg_wd.empty:
            messages_weekly_total = pd.DataFrame(columns=["iso_year", "iso_week", "messages"])
            messages_weekly_percapita = pd.DataFrame(
                columns=["iso_year", "iso_week", "messages", "total_users", "messages_per_user"]
            )
        else:
            iso = msg_wd["date"].dt.isocalendar()
            msg_wd["iso_year"] = iso["year"].astype(int)
            msg_wd["iso_week"] = iso["week"].astype(int)

            messages_weekly_total = (
                msg_wd.groupby(["iso_year", "iso_week"])["emp_id"]
                .size()
                .reset_index(name="messages")
                .sort_values(["iso_year", "iso_week"])
            )

            # 週在職聯集（依該週訊息實際出現的所有日期）
            week_dates = msg_wd[["date", "iso_year", "iso_week"]].drop_duplicates()

            percap_rows = []
            for (by, bw), g in week_dates.groupby(["iso_year", "iso_week"]):
                ds = list(pd.to_datetime(g["date"]).sort_values().unique())
                in_service_ids = set()
                for d in ds:
                    mask = employed_on(d)
                    in_service_ids |= set(employees.loc[mask, "emp_id"].dropna().astype(str))
                total_users = len(in_service_ids)
                msg_cnt = int(messages_weekly_total.query("iso_year==@by and iso_week==@bw")["messages"].sum())
                percap_rows.append(
                    {
                        "iso_year": int(by),
                        "iso_week": int(bw),
                        "messages": msg_cnt,
                        "total_users": total_users,
                        "messages_per_user": (msg_cnt / total_users) if total_users else 0.0,
                    }
                )
            messages_weekly_percapita = pd.DataFrame(percap_rows).sort_values(["iso_year", "iso_week"])

        # --------------------------------------------------------------
        # 7) 訊息分布 20/60/20（週）比例 + 趨勢
        #   依週彙總每位使用者當週訊息數，做排名分層，輸出各分層訊息數占比
        # --------------------------------------------------------------
        if msg_wd.empty:
            message_distribution = pd.DataFrame(
                columns=["iso_year", "iso_week", "segment", "message_sum", "share_percent"]
            )
        else:
            # 每人每週訊息數
            per_user_week = (
                msg_wd.groupby(["iso_year", "iso_week", "emp_id"])["emp_id"]
                .size()
                .reset_index(name="msg_count")
            )

            dist_rows = []
            for (by, bw), g in per_user_week.groupby(["iso_year", "iso_week"]):
                g = g.sort_values("msg_count", ascending=False).reset_index(drop=True)
                total_users = len(g)
                total_msgs = int(g["msg_count"].sum())
                if total_users == 0 or total_msgs == 0:
                    continue

                top_n = max(int(round(total_users * 0.2)), 1)
                mid_n = max(int(round(total_users * 0.6)), 0)
                if top_n + mid_n > total_users:
                    mid_n = max(total_users - top_n, 0)
                bot_n = max(total_users - top_n - mid_n, 0)

                top_sum = int(g.iloc[:top_n]["msg_count"].sum()) if top_n > 0 else 0
                mid_sum = int(g.iloc[top_n : top_n + mid_n]["msg_count"].sum()) if mid_n > 0 else 0
                bot_sum = int(g.iloc[top_n + mid_n :]["msg_count"].sum()) if bot_n > 0 else 0

                for seg, s in (("前20%", top_sum), ("中間60%", mid_sum), ("後20%", bot_sum)):
                    share = (s / total_msgs * 100.0) if total_msgs else 0.0
                    dist_rows.append(
                        {
                            "iso_year": int(by),
                            "iso_week": int(bw),
                            "segment": seg,
                            "message_sum": s,
                            "share_percent": round(share, 2),
                        }
                    )
            message_distribution = pd.DataFrame(dist_rows).sort_values(["iso_year", "iso_week", "segment"])

        return {
            "coverage_company_weekly": coverage_company_weekly,
            "coverage_unit_weekly": coverage_unit_weekly,
            "active_rate_workingday_daily": active_rate_workingday_daily,
            "activation_next_month_company": activation_next_month_company,
            "retention_monthly_company": retention_monthly_company,
            "messages_weekly_total": messages_weekly_total,
            "messages_weekly_percapita": messages_weekly_percapita,
            "message_distribution_weekly_20_60_20": message_distribution,
        }

    # ------------------------------------------------------------------
    # 舊版結構相容：提供給測試或尚未更新的前端使用
    # ------------------------------------------------------------------
    def _transform_compat(self, raw: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        employees = raw.get("employees", pd.DataFrame()).copy()
        employees.rename(
            columns={"EmpId": "emp_id", "EmpNo": "emp_id", "UnitId": "unit_id"}, inplace=True
        )
        total_users = int(employees.get("emp_id", pd.Series(dtype=str)).dropna().nunique())

        daily_active = raw.get("daily_active", pd.DataFrame()).copy()
        daily_active.rename(
            columns={"ActiveDate": "date", "EmpId": "emp_id", "EmpNo": "emp_id", "UnitId": "unit_id"},
            inplace=True,
        )
        if "date" in daily_active:
            daily_active["date"] = pd.to_datetime(daily_active["date"], errors="coerce")
            daily_active.dropna(subset=["date"], inplace=True)

        messages = raw.get("messages", pd.DataFrame()).copy()
        messages.rename(
            columns={"MsgDate": "date", "SenderEmpNo": "emp_id", "EmpId": "emp_id"}, inplace=True
        )
        if "date" in messages:
            messages["date"] = pd.to_datetime(messages["date"], errors="coerce")
            messages.dropna(subset=["date"], inplace=True)
        message_col = "MessageCount" if "MessageCount" in messages.columns else "message_count"
        if message_col not in messages:
            messages[message_col] = 1

        # weekly usage summary
        if not daily_active.empty and "emp_id" in daily_active:
            week_start = daily_active["date"] - pd.to_timedelta(daily_active["date"].dt.weekday, unit="D")
            usage_weekly = (
                daily_active.assign(week_start=week_start)
                .groupby("week_start")["emp_id"].nunique()
                .reset_index(name="active_users")
            )
            usage_weekly.rename(columns={"week_start": "stat_date"}, inplace=True)
            usage_weekly["total_users"] = total_users or usage_weekly["active_users"]
            usage_weekly["usage_rate"] = np.where(
                usage_weekly["total_users"] > 0,
                usage_weekly["active_users"] / usage_weekly["total_users"],
                0.0,
            )
        else:
            usage_weekly = pd.DataFrame(
                columns=["stat_date", "active_users", "total_users", "usage_rate"]
            )

        # daily active summary
        if not daily_active.empty and "emp_id" in daily_active:
            daily_active_out = (
                daily_active.groupby("date")["emp_id"].nunique().reset_index(name="active_users")
            )
            daily_active_out.rename(columns={"date": "stat_date"}, inplace=True)
        else:
            daily_active_out = pd.DataFrame(columns=["stat_date", "active_users"])

        # daily message stats
        if not messages.empty:
            message_daily = (
                messages.groupby("date")[message_col]
                .sum()
                .reset_index(name="total_messages")
            )
            message_daily.rename(columns={"date": "stat_date"}, inplace=True)
            if total_users > 0:
                message_daily["avg_messages_per_user"] = (
                    message_daily["total_messages"] / total_users
                )
            else:
                message_daily["avg_messages_per_user"] = 0.0
        else:
            message_daily = pd.DataFrame(
                columns=["stat_date", "total_messages", "avg_messages_per_user"]
            )

        # message distribution (20/60/20 by sender)
        if not messages.empty and "emp_id" in messages:
            per_user = (
                messages.groupby("emp_id")[message_col]
                .sum()
                .reset_index(name="total_messages")
                .sort_values("total_messages", ascending=False)
            )
            total_msgs = int(per_user["total_messages"].sum())
            seg_rows = []
            if total_msgs > 0 and not per_user.empty:
                n_users = len(per_user)
                top_n = max(int(round(n_users * 0.2)), 1)
                mid_n = max(int(round(n_users * 0.6)), 0)
                if top_n + mid_n > n_users:
                    mid_n = max(n_users - top_n, 0)
                bot_n = max(n_users - top_n - mid_n, 0)

                top_sum = int(per_user.iloc[:top_n]["total_messages"].sum()) if top_n > 0 else 0
                mid_sum = (
                    int(per_user.iloc[top_n : top_n + mid_n]["total_messages"].sum())
                    if mid_n > 0
                    else 0
                )
                bot_sum = (
                    int(per_user.iloc[top_n + mid_n :]["total_messages"].sum())
                    if bot_n > 0
                    else 0
                )

                for label, value in (
                    ("top20", top_sum),
                    ("mid60", mid_sum),
                    ("bottom20", bot_sum),
                ):
                    share = (value / total_msgs) if total_msgs else 0.0
                    seg_rows.append({"segment": label, "message_share": share})
            message_distribution = pd.DataFrame(seg_rows)
        else:
            message_distribution = pd.DataFrame(columns=["segment", "message_share"])

        # message leaderboard
        if not messages.empty and "emp_id" in messages:
            leaderboard = (
                messages.groupby("emp_id")[message_col]
                .sum()
                .reset_index(name="total_messages")
                .sort_values("total_messages", ascending=False)
            )
            leaderboard["rank"] = range(1, len(leaderboard) + 1)
            leaderboard.rename(columns={"emp_id": "emp_no"}, inplace=True)
        else:
            leaderboard = pd.DataFrame(columns=["emp_no", "total_messages", "rank"])

        # activation monthly (based on device installs)
        device = raw.get("device", pd.DataFrame()).copy()
        device.rename(
            columns={"EmpId": "emp_id", "EmpNo": "emp_id", "FirstInstallDate": "install_date"},
            inplace=True,
        )
        if "install_date" in device:
            device["install_date"] = pd.to_datetime(device["install_date"], errors="coerce")
            device.dropna(subset=["install_date"], inplace=True)
            activation_monthly = (
                device.assign(stat_month=device["install_date"].dt.to_period("M").dt.to_timestamp())
                .groupby("stat_month")["emp_id"]
                .nunique()
                .reset_index(name="activated_users")
            )
        else:
            activation_monthly = pd.DataFrame(columns=["stat_month", "activated_users"])

        return {
            "usage_weekly": usage_weekly,
            "daily_active": daily_active_out,
            "message_daily": message_daily,
            "message_distribution": message_distribution,
            "message_leaderboard": leaderboard,
            "activation_monthly": activation_monthly,
        }

    # ------------------------------------------------------------------
    # 載入階段
    # ------------------------------------------------------------------
    def load(self, items: Dict[str, pd.DataFrame]) -> None:
        """將彙總結果寫回 DuckDB。"""
        duck = self.duck_client

        # 1) 全公司覆蓋率（週）
        duck.ensure_table(
            f"""
            CREATE TABLE IF NOT EXISTS {self.TBL_COVERAGE_COMPANY_WEEKLY} (
                iso_year INTEGER,
                iso_week INTEGER,
                baseline_date DATE,
                covered_users INTEGER,
                total_users INTEGER,
                coverage_rate DOUBLE
            )
            """
        )
        duck.write_dataframe(items["coverage_company_weekly"], self.TBL_COVERAGE_COMPANY_WEEKLY, mode="replace")

        # 2) 各部門覆蓋率（週）
        duck.ensure_table(
            f"""
            CREATE TABLE IF NOT EXISTS {self.TBL_COVERAGE_UNIT_WEEKLY} (
                iso_year INTEGER,
                iso_week INTEGER,
                baseline_date DATE,
                root_org_id VARCHAR,
                root_org_name VARCHAR,
                used_users INTEGER,
                total_users INTEGER,
                coverage_rate DOUBLE
            )
            """
        )
        # 確保 baseline_date 欄位存在（transform 已處理，保險再填）
        df_unit = items["coverage_unit_weekly"].copy()
        if "baseline_date" not in df_unit.columns:
            df_unit["baseline_date"] = pd.NaT
        duck.write_dataframe(df_unit, self.TBL_COVERAGE_UNIT_WEEKLY, mode="replace")

        # 3) 工作日活躍（日）
        duck.ensure_table(
            f"""
            CREATE TABLE IF NOT EXISTS {self.TBL_ACTIVE_RATE_WORKINGDAY_DAILY} (
                date DATE,
                active_users INTEGER,
                total_users INTEGER,
                active_rate DOUBLE
            )
            """
        )
        duck.write_dataframe(items["active_rate_workingday_daily"], self.TBL_ACTIVE_RATE_WORKINGDAY_DAILY, mode="replace")

        # 4) 當月啟用率（公司）
        duck.ensure_table(
            f"""
            CREATE TABLE IF NOT EXISTS {self.TBL_ACTIVATION_NEXT_MONTH} (
                hire_month DATE,
                new_hires INTEGER,
                used_next_month INTEGER,
                activation_rate DOUBLE
            )
            """
        )
        duck.write_dataframe(items["activation_next_month_company"], self.TBL_ACTIVATION_NEXT_MONTH, mode="replace")

        # 5) 當月留存率（公司）
        duck.ensure_table(
            f"""
            CREATE TABLE IF NOT EXISTS {self.TBL_RETENTION_MONTHLY} (
                active_month DATE,
                active_users INTEGER,
                registered_total INTEGER,
                retention_rate DOUBLE
            )
            """
        )
        duck.write_dataframe(items["retention_monthly_company"], self.TBL_RETENTION_MONTHLY, mode="replace")

        # 6) 每週工作日訊息總計
        duck.ensure_table(
            f"""
            CREATE TABLE IF NOT EXISTS {self.TBL_MSG_WEEKLY_TOTAL} (
                iso_year INTEGER,
                iso_week INTEGER,
                messages INTEGER
            )
            """
        )
        duck.write_dataframe(items["messages_weekly_total"], self.TBL_MSG_WEEKLY_TOTAL, mode="replace")

        # 7) 每週工作日人均訊息數
        duck.ensure_table(
            f"""
            CREATE TABLE IF NOT EXISTS {self.TBL_MSG_WEEKLY_PERCAPITA} (
                iso_year INTEGER,
                iso_week INTEGER,
                messages INTEGER,
                total_users INTEGER,
                messages_per_user DOUBLE
            )
            """
        )
        duck.write_dataframe(items["messages_weekly_percapita"], self.TBL_MSG_WEEKLY_PERCAPITA, mode="replace")

        # 8) 訊息分布 20/60/20（週）
        duck.ensure_table(
            f"""
            CREATE TABLE IF NOT EXISTS {self.TBL_MSG_DISTRIBUTION} (
                iso_year INTEGER,
                iso_week INTEGER,
                segment VARCHAR,
                message_sum INTEGER,
                share_percent DOUBLE
            )
            """
        )
        duck.write_dataframe(
            items["message_distribution_weekly_20_60_20"], self.TBL_MSG_DISTRIBUTION, mode="replace"
        )

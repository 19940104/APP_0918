"""人員黏著度統計（Engagement 分頁）"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from common import CHART_TOOLTIPS, fetch_engagement, info_badge

KEY_PREFIX = "engagement_tab__"


def _safe_df(records) -> pd.DataFrame:
    if isinstance(records, list) and records:
        return pd.DataFrame(records)
    return pd.DataFrame()


def _prep_daily(df: pd.DataFrame) -> pd.DataFrame:
    """僅保留工作日，整理欄位型別與比率。"""
    if df.empty:
        return df
    out = df.copy()
    if "stat_date" in out.columns:
        out["stat_date"] = pd.to_datetime(out["stat_date"], errors="coerce")
        out = out.dropna(subset=["stat_date"]).sort_values("stat_date")
        # 工作日（週一=0 ~ 週五=4）
        out = out[out["stat_date"].dt.weekday < 5]
    for c in ("active_users", "total_users"):
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    if "active_rate" not in out.columns and {"active_users", "total_users"} <= set(out.columns):
        out["active_rate"] = out["active_users"] / out["total_users"].replace({0: pd.NA})
    out["active_rate"] = pd.to_numeric(out.get("active_rate"), errors="coerce")
    return out


def _aggregate_weekly_from_daily(daily: pd.DataFrame) -> pd.DataFrame:
    """把工作日日資料轉成週（ISO 週），週率 = 週內「有使用過的人/全員」的近似比例：
    這裡採『日平均活躍率』做週代表值（避免分母重複）。"""
    if daily.empty:
        return daily
    df = daily.copy()
    iso = df["stat_date"].dt.isocalendar()
    df["iso_year"], df["iso_week"] = iso["year"], iso["week"]
    grp = (
        df.groupby(["iso_year", "iso_week"], as_index=False)
        .agg(
            # 這裡採平均日活躍率，亦可改為：活躍人數日去重 / 當週平均在職（依你的資料口徑取捨）
            usage_rate=("active_rate", "mean"),
            days=("stat_date", "count"),
        )
        .query("days > 0")
    )
    # 週起日（週一）
    # 將每週的第一個工作日當這週的顯示日期
    first_days = df.sort_values("stat_date").groupby(["iso_year", "iso_week"], as_index=False).first()[["iso_year", "iso_week", "stat_date"]]
    grp = grp.merge(first_days, on=["iso_year", "iso_week"], how="left")
    grp.rename(columns={"stat_date": "week_start"}, inplace=True)
    grp["week_label"] = grp["iso_year"].astype(str) + "-W" + grp["iso_week"].astype(str).str.zfill(2)
    # 對齊欄位給前端使用
    grp["stat_date"] = grp["week_start"]
    return grp[["stat_date", "iso_year", "iso_week", "week_label", "usage_rate", "days"]].sort_values("stat_date")


def _aggregate_monthly_from_daily(daily: pd.DataFrame) -> pd.DataFrame:
    """把工作日日資料轉成月，月率 = 月內『日活躍率平均』（工作日）。"""
    if daily.empty:
        return daily
    df = daily.copy()
    df["stat_month"] = df["stat_date"].dt.to_period("M")
    grp = (
        df.groupby("stat_month", as_index=False)
        .agg(
            active_rate=("active_rate", "mean"),
            workdays=("stat_date", "count"),
        )
        .query("workdays > 0")
    )
    grp["month_start"] = grp["stat_month"].dt.to_timestamp()
    grp["month_label"] = grp["stat_month"].astype(str)
    grp.rename(columns={"active_rate": "monthly_rate"}, inplace=True)
    grp["stat_date"] = grp["month_start"]
    return grp[["stat_date", "month_label", "monthly_rate", "workdays"]].sort_values("stat_date")


def _chart(df: pd.DataFrame, x: str, y: str, kind: str, y_as_percent: bool = True, title_x: str = "", title_y: str = ""):
    """簡化：折線/長條切換。"""
    if kind == "長條圖":
        fig = px.bar(df, x=x, y=y)
    else:
        fig = px.line(df, x=x, y=y, markers=True)
    fig.update_layout(title=None, xaxis_title=title_x or x, yaxis_title=title_y or y)
    if y_as_percent:
        fig.update_yaxes(tickformat=".0%")
    return fig


def render_engagement() -> None:
    """Render the engagement analysis tab."""
    data = fetch_engagement() or {}
    daily_raw = _safe_df(data.get("daily", []))
    weekly_api = _safe_df(data.get("weekly", []))

    # 全部無資料
    if daily_raw.empty and weekly_api.empty:
        st.info("目前沒有黏著度資料。")
        return

    # 整理「工作日」的每日資料
    daily = _prep_daily(daily_raw)

    # 把 daily 聚合成週與月
    weekly_from_daily = _aggregate_weekly_from_daily(daily) if not daily.empty else pd.DataFrame()
    monthly_from_daily = _aggregate_monthly_from_daily(daily) if not daily.empty else pd.DataFrame()

    # UI 兩欄
    cols = st.columns(2, gap="large")

    # =========================================================================
    # 左：工作日活躍（支援：日/週/月；折線/長條；下拉篩選）
    # =========================================================================
    with cols[0]:
        st.markdown(
            info_badge("工作日活躍", CHART_TOOLTIPS.get("daily_active"), font_size="18px"),
            unsafe_allow_html=True,
        )

        # 顯示頻率：日 / 週 / 月
        freq = st.radio(
            "查看頻率",
            ("日", "週", "月"),
            index=0,
            horizontal=True,
            key=f"{KEY_PREFIX}freq",
        )

        chart_type = st.radio(
            "圖表類型",
            ("折線圖", "長條圖"),
            index=0,
            horizontal=True,
            key=f"{KEY_PREFIX}chart_type",
        )

        if freq == "日":
            view_df = daily.dropna(subset=["active_rate"]).copy()
            if view_df.empty:
                st.info("目前沒有可用的工作日資料。")
            else:
                # 期間下拉（近 3/6/12 個月）
                view_df["yyyymm"] = view_df["stat_date"].dt.to_period("M").astype(str)
                months = sorted(view_df["yyyymm"].unique(), reverse=True)
                options = ["全部"] + months[:12]
                chosen = st.selectbox("期間", options, index=0, key=f"{KEY_PREFIX}period_day")
                if chosen != "全部":
                    view_df = view_df[view_df["yyyymm"] == chosen]

                fig = _chart(
                    view_df,
                    x="stat_date",
                    y="active_rate",
                    kind=chart_type,
                    y_as_percent=True,
                    title_x="統計日期",
                    title_y="日活躍率 (%)",
                )
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    config={"modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"], "displaylogo": False},
                )

                # 右側表單（在此欄位底部顯示）
                table_df = view_df[["stat_date", "active_users", "total_users", "active_rate"]].copy()
                table_df.rename(
                    columns={
                        "stat_date": "日期",
                        "active_users": "活躍人數",
                        "total_users": "總人數",
                        "active_rate": "活躍率",
                    },
                    inplace=True,
                )
                table_df["活躍率"] = table_df["活躍率"].map(lambda v: f"{v:.2%}" if pd.notna(v) else "—")
                st.dataframe(table_df, use_container_width=True, hide_index=True)

        elif freq == "週":
            # 用 daily 聚合的週（保證工作日口徑）
            view_df = weekly_from_daily.dropna(subset=["usage_rate"]).copy()
            if view_df.empty:
                st.info("目前沒有可用的週資料（工作日彙總）。")
            else:
                # 期間下拉（近 12/24/48 週選擇）
                weeks = view_df["week_label"].tolist()
                options = ["全部"] + weeks[-24:][::-1]
                chosen = st.selectbox("週次", options, index=0, key=f"{KEY_PREFIX}period_week")
                if chosen != "全部":
                    view_df = view_df[view_df["week_label"] == chosen]

                fig = _chart(
                    view_df,
                    x="stat_date",
                    y="usage_rate",
                    kind=chart_type,
                    y_as_percent=True,
                    title_x="統計週起日",
                    title_y="週活躍率 (%)",
                )
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    config={"modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"], "displaylogo": False},
                )

                # 右側表單（在此欄位底部顯示）
                table_df = view_df[["week_label", "days", "usage_rate"]].copy()
                table_df.rename(
                    columns={
                        "week_label": "週次",
                        "days": "工作日數",
                        "usage_rate": "週活躍率",
                    },
                    inplace=True,
                )
                table_df["週活躍率"] = table_df["週活躍率"].map(lambda v: f"{v:.2%}" if pd.notna(v) else "—")
                st.dataframe(table_df, use_container_width=True, hide_index=True)

        else:  # 月
            view_df = monthly_from_daily.dropna(subset=["monthly_rate"]).copy()
            if view_df.empty:
                st.info("目前沒有可用的月資料（工作日彙總）。")
            else:
                # 期間下拉（近 6/12/24 個月）
                months = view_df["month_label"].tolist()
                options = ["全部"] + months[-12:][::-1]
                chosen = st.selectbox("月份", options, index=0, key=f"{KEY_PREFIX}period_month")
                if chosen != "全部":
                    view_df = view_df[view_df["month_label"] == chosen]

                fig = _chart(
                    view_df,
                    x="stat_date",
                    y="monthly_rate",
                    kind=chart_type,
                    y_as_percent=True,
                    title_x="統計月份",
                    title_y="月活躍率 (%)",
                )
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    config={"modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"], "displaylogo": False},
                )

                # 右側表單（在此欄位底部顯示）
                table_df = view_df[["month_label", "workdays", "monthly_rate"]].copy()
                table_df.rename(
                    columns={
                        "month_label": "月份",
                        "workdays": "工作日數",
                        "monthly_rate": "月活躍率",
                    },
                    inplace=True,
                )
                table_df["月活躍率"] = table_df["月活躍率"].map(lambda v: f"{v:.2%}" if pd.notna(v) else "—")
                st.dataframe(table_df, use_container_width=True, hide_index=True)

    # =========================================================================
    # 右：週活躍（直接顯示後端 weekly；作為參考對照）
    # =========================================================================
    with cols[1]:
        st.markdown(
            info_badge("週活躍（後端彙總）", CHART_TOOLTIPS.get("weekly_active"), font_size="18px"),
            unsafe_allow_html=True,
        )

        if weekly_api.empty:
            st.info("後端沒有提供週活躍資料。")
        else:
            df = weekly_api.copy()
            if "stat_date" in df.columns:
                df["stat_date"] = pd.to_datetime(df["stat_date"], errors="coerce")
                df = df.dropna(subset=["stat_date"]).sort_values("stat_date")
            # 可能欄位名為 usage_rate 或 active_rate
            y_col = "usage_rate" if "usage_rate" in df.columns else "active_rate"
            df = df.dropna(subset=[y_col])

            # 控制：折線 / 長條
            chart_type2 = st.radio(
                "圖表類型",
                ("折線圖", "長條圖"),
                index=0,
                horizontal=True,
                key=f"{KEY_PREFIX}chart_type_week_api",
            )

            fig = _chart(
                df,
                x="stat_date",
                y=y_col,
                kind=chart_type2,
                y_as_percent=True,
                title_x="統計週起日",
                title_y="週活躍率 (%)",
            )
            st.plotly_chart(
                fig,
                use_container_width=True,
                config={"modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"], "displaylogo": False},
            )

            # 表單
            if "iso_year" in df.columns and "iso_week" in df.columns:
                df["week_label"] = df["iso_year"].astype(str) + "-W" + df["iso_week"].astype(int).astype(str).str.zfill(2)
            show_cols = []
            rename = {}
            for c, zh in [
                ("week_label", "週次"),
                ("stat_date", "統計週起日"),
                (y_col, "週活躍率"),
            ]:
                if c in df.columns:
                    show_cols.append(c)
                    rename[c] = zh
            table_df = df[show_cols].rename(columns=rename).copy()
            if "週活躍率" in table_df.columns:
                table_df["週活躍率"] = table_df["週活躍率"].map(lambda v: f"{v:.2%}" if pd.notna(v) else "—")
            st.dataframe(table_df, use_container_width=True, hide_index=True)

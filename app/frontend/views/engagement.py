from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from app.frontend.dashboard_shared import (
    CHART_TOOLTIPS,
    build_month_options,
    ensure_datetime,
    fetch,
    info_badge,
)


def _prepare_daily(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    if df.empty:
        return df
    df = df.copy()
    if "stat_date" in df.columns:
        df["stat_date"] = ensure_datetime(df["stat_date"])
        df = df.dropna(subset=["stat_date"])
    if "active_rate" not in df.columns and {"active_users", "total_users"}.issubset(df.columns):
        total = df["total_users"].replace({0: pd.NA})
        df["active_rate"] = df["active_users"] / total
    df["active_rate"] = pd.to_numeric(df.get("active_rate"), errors="coerce")
    df = df.dropna(subset=["stat_date"])  # 保留有效日期
    df["month_label"] = df["stat_date"].dt.to_period("M").astype(str)
    return df


def _prepare_weekly(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    if df.empty:
        return df
    df = df.copy()
    if "stat_date" in df.columns:
        df["stat_date"] = ensure_datetime(df["stat_date"])
        df = df.dropna(subset=["stat_date"])
        df["month_label"] = df["stat_date"].dt.to_period("M").astype(str)
    if "usage_rate" in df.columns:
        df["usage_rate"] = pd.to_numeric(df["usage_rate"], errors="coerce")
    if "week_label" in df.columns:
        df["display_week"] = df["week_label"].astype(str)
    else:
        df["display_week"] = df["stat_date"].dt.strftime("%G-W%V")
    return df


def render_engagement() -> None:
    """呈現黏著度分析（日活 / 週活）。"""

    try:
        data = fetch("engagement")
    except Exception as exc:  # pragma: no cover - defensive UI message
        st.error(f"取得黏著度資料失敗：{exc}")
        return

    daily_df = _prepare_daily(data.get("daily", []))
    weekly_df = _prepare_weekly(data.get("weekly", []))

    if daily_df.empty and weekly_df.empty:
        st.info("目前沒有黏著度資料。")
        return

    line_tab, table_tab = st.tabs(["折線圖", "資料表"])

    with line_tab:
        columns = st.columns(2, gap="large")

        if daily_df.empty:
            with columns[0]:
                st.info("目前沒有工作日日活躍資料。")
        else:
            month_options = build_month_options(daily_df["stat_date"])
            if month_options:
                selected_month = st.selectbox(
                    "選擇月份檢視工作日日活躍",
                    month_options,
                    index=0,
                    key="daily_active_month",
                )
                month_daily = daily_df[daily_df["month_label"] == selected_month]
            else:
                selected_month = None
                month_daily = daily_df

            with columns[0]:
                st.markdown(
                    info_badge("工作日日活躍", CHART_TOOLTIPS.get("daily_workday_active"), font_size="18px"),
                    unsafe_allow_html=True,
                )
                if month_daily.empty:
                    st.info("所選月份沒有日活躍資料。")
                else:
                    fig = px.line(
                        month_daily,
                        x="stat_date",
                        y="active_rate",
                        markers=True,
                        labels={"stat_date": "統計日期", "active_rate": "日活躍率"},
                    )
                    fig.update_yaxes(tickformat=".0%")
                    fig.update_layout(title=None, xaxis_title="統計日期", yaxis_title="日活躍率 (%)")
                    st.plotly_chart(
                        fig,
                        use_container_width=True,
                        config={"modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"], "displaylogo": False},
                    )
                    if selected_month:
                        st.caption(f"月份：{selected_month}")

        if weekly_df.empty:
            with columns[1]:
                st.info("目前沒有週活躍資料。")
        else:
            month_options = build_month_options(weekly_df["stat_date"])
            if month_options:
                selected_month = st.selectbox(
                    "選擇月份檢視週活躍",
                    month_options,
                    index=0,
                    key="weekly_active_month",
                )
                month_weekly = weekly_df[weekly_df["month_label"] == selected_month]
            else:
                selected_month = None
                month_weekly = weekly_df

            with columns[1]:
                st.markdown(
                    info_badge("週活躍人數", CHART_TOOLTIPS.get("weekly_active"), font_size="18px"),
                    unsafe_allow_html=True,
                )
                if month_weekly.empty:
                    st.info("所選月份沒有週活躍資料。")
                else:
                    fig = px.line(
                        month_weekly,
                        x="stat_date",
                        y="usage_rate",
                        markers=True,
                        labels={"stat_date": "統計週起日", "usage_rate": "週活躍率"},
                    )
                    fig.update_yaxes(tickformat=".0%")
                    fig.update_layout(title=None, xaxis_title="統計週起日", yaxis_title="週活躍率 (%)")
                    st.plotly_chart(
                        fig,
                        use_container_width=True,
                        config={"modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"], "displaylogo": False},
                    )
                    if selected_month:
                        st.caption(f"月份：{selected_month}")

    with table_tab:
        if daily_df.empty:
            st.info("目前沒有工作日日活躍明細。")
        else:
            month_options = build_month_options(daily_df["stat_date"])
            selected = (
                st.selectbox(
                    "選擇月份檢視日活躍明細",
                    month_options,
                    index=0,
                    key="daily_active_table_month",
                )
                if month_options
                else None
            )
            table_daily = daily_df if selected is None else daily_df[daily_df["month_label"] == selected]
            if table_daily.empty:
                st.info("所選月份沒有日活躍資料。")
            else:
                display = table_daily[["stat_date", "active_users", "total_users", "active_rate"]].copy()
                display["stat_date"] = display["stat_date"].dt.strftime("%Y-%m-%d")
                display["active_rate"] = display["active_rate"].map(
                    lambda v: f"{v:.2%}" if pd.notna(v) else "—"
                )
                display.rename(
                    columns={
                        "stat_date": "日期",
                        "active_users": "活躍人數",
                        "total_users": "總員工數",
                        "active_rate": "日活躍率",
                    },
                    inplace=True,
                )
                st.dataframe(display, use_container_width=True, hide_index=True)

        if weekly_df.empty:
            st.info("目前沒有週活躍明細。")
        else:
            month_options = build_month_options(weekly_df["stat_date"])
            selected = (
                st.selectbox(
                    "選擇月份檢視週活躍明細",
                    month_options,
                    index=0,
                    key="weekly_active_table_month",
                )
                if month_options
                else None
            )
            table_weekly = weekly_df if selected is None else weekly_df[weekly_df["month_label"] == selected]
            if table_weekly.empty:
                st.info("所選月份沒有週活躍資料。")
            else:
                display = table_weekly[["stat_date", "display_week", "active_users", "total_users", "usage_rate"]].copy()
                display["stat_date"] = display["stat_date"].dt.strftime("%Y-%m-%d")
                display["usage_rate"] = display["usage_rate"].map(
                    lambda v: f"{v:.2%}" if pd.notna(v) else "—"
                )
                display.rename(
                    columns={
                        "stat_date": "週起日",
                        "display_week": "週次",
                        "active_users": "活躍人數",
                        "total_users": "總員工數",
                        "usage_rate": "週活躍率",
                    },
                    inplace=True,
                )
                st.dataframe(display, use_container_width=True, hide_index=True)

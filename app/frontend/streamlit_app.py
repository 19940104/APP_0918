"""Streamlit 儀表板原型。"""

from __future__ import annotations

import html
import math
import os
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

API_BASE = os.getenv("DASHBOARD_API", "http://localhost:8000/api/dashboard")

st.set_page_config(
    page_title="APP 使用分析儀表板",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.title("APP 使用分析儀表板")
st.caption("資料來源：DuckDB 彙總表")

# ---- 全寬＆隱藏預設工具列 ----
st.markdown(
    """
    <style>
    div[data-testid="stToolbar"] {display: none !important;}
    div[data-testid="stDecoration"] {display: none !important;}
    button[kind="header"] {display: none !important;}
    .stApp > header {background: transparent;}
    .block-container {
        max-width: 100% !important;
        padding-left: 2rem;
        padding-right: 2rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=300)
def fetch(endpoint: str):
    """呼叫後端 API 並快取 5 分鐘。"""
    url = f"{API_BASE}/{endpoint}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


OVERVIEW_TOOLTIPS = {
    "每日活躍": "當日有使用的人數 ÷ 總員工數，用來追蹤每天的實際使用狀況。",
    "當週使用率": "全公司有使用過人數 ÷ 全公司總員工數，用於評估推廣覆蓋率。",
    "當月新人啟用率": "啟用定義：到職後有使用過，可確認新人是否完成安裝並開始使用。",
    "當日訊息": "統計當日產生的訊息總數，用來評估互動熱度與系統負載。",
}

CHART_TOOLTIPS = {
    "company_usage": "全公司有使用過人數 ÷ 總員工數，週別呈現以掌握推廣成效。",
    "department_usage": "各部門有使用過人數 ÷ 部門總員工數，辨識推廣強弱單位。",
    "daily_active": "當日有使用的人數 ÷ 總員工數，快速掌握每日黏著度。",
    "weekly_active": "當週有使用的人數 ÷ 總員工數，觀察每週活躍趨勢穩定度。",
    "workday_messages": "僅統計工作日訊息總數，彙整為每月平均，掌握系統熱度與負載走勢。",
    "per_capita_messages": "工作日訊息總數除以在職員工數，並以月份呈現人均互動深度。",
    "message_distribution": "以前 20% / 中間 60% / 後 20% 分層彙總訊息占比，判斷是否集中在少數人。",
    "message_leaderboard": "訊息量排名前 10 的使用者，協助了解核心使用者。",
    "activation": "啟用率：到職後有使用過的人數比例，評估部署覆蓋。",
    "retention": "留存率：已啟用者在當月至少使用一次的比例，評估持續使用狀況。",
}


def info_badge(title: str, tooltip: str | None = None, *, font_size: str = "16px") -> str:
    """生成包含說明提示的標題（右側 ℹ️ 顯示 title 提示）。"""
    safe_title = html.escape(title)
    if not tooltip:
        return f"<div style='font-size:{font_size}; font-weight:600;'>{safe_title}</div>"
    safe_tip = html.escape(tooltip)
    return (
        f"<div style='display:flex;align-items:center;gap:6px;font-size:{font_size};font-weight:600;'>"
        f"{safe_title}<span style='cursor:help;' title='{safe_tip}'>ℹ️</span></div>"
    )


def _format_metric_value(value, suffix: str, multiplier: float = 1.0) -> str:
    """KPI 顯示數值格式化（% 會自動乘以 100 並保留 2 位小數）。"""
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return "無資料"
    if isinstance(value, (int, float)):
        v = value * multiplier
        if suffix == "%":
            return f"{v:.2f}{suffix}"
        return f"{int(v)}{suffix}" if float(v).is_integer() else f"{v:.2f}{suffix}"
    return f"{value}{suffix}"


def render_overview() -> None:
    """繪製首頁 KPI。"""
    try:
        data = fetch("overview")
    except Exception as e:
        st.error(f"取得總覽資料失敗：{e}")
        return

    cols = st.columns(4, gap="large")
    mapping = [
        ("每日活躍", data.get("daily_active"), "active_users", "人", 1),
        ("當週使用率", data.get("weekly_usage"), "usage_rate", "%", 100),
        ("當月新人啟用率", data.get("activation"), "activation_rate", "%", 100),
        ("當日訊息", data.get("message"), "total_messages", "則", 1),
    ]

    for col, (title, item, field, suffix, multiplier) in zip(cols, mapping):
        with col:
            st.markdown(
                info_badge(title, OVERVIEW_TOOLTIPS.get(title), font_size="18px"),
                unsafe_allow_html=True,
            )
            if not item:
                st.write("無資料")
                continue
            raw = item.get(field)
            label = item.get("stat_date") or "2025-09"
            if not isinstance(label, str):
                label = str(label)
            display = _format_metric_value(raw, suffix, multiplier)
            st.metric(label=label, value=display)


def render_usage() -> None:
    """呈現使用率分析。"""
    try:
        data = fetch("usage")
    except Exception as e:
        st.error(f"取得使用率資料失敗：{e}")
        return

    company = data.get("company", [])
    departments = data.get("departments", [])

    if not company and not departments:
        st.info("目前沒有使用率資料。")
        return

    cols = st.columns(2, gap="large")

    # 全公司週使用率
    if company:
        company_df = pd.DataFrame(company)
        if company_df.empty:
            with cols[0]:
                st.info("全公司週使用率沒有資料。")
        else:
            company_df = company_df.copy()
            if "stat_date" in company_df.columns:
                company_df["stat_date"] = pd.to_datetime(company_df["stat_date"], errors="coerce")
            sort_keys = [col for col in ("iso_year", "iso_week", "stat_date") if col in company_df.columns]
            if sort_keys:
                company_df = company_df.sort_values(sort_keys)
            if "week_label" in company_df.columns:
                company_df["week_display"] = company_df["week_label"].copy()
            else:
                company_df["week_display"] = pd.Series([None] * len(company_df))
            if "stat_date" in company_df.columns:
                company_df["week_display"] = company_df["week_display"].fillna(
                    company_df["stat_date"].dt.strftime("%G-W%V")
                )
                company_df["stat_month"] = company_df["stat_date"].dt.to_period("M")
            else:
                company_df["stat_month"] = pd.Series([pd.NaT] * len(company_df))
            company_df["week_display"] = company_df["week_display"].fillna(
                company_df.index.to_series().add(1).map(lambda idx: f"週次 {idx}")
            )
            company_df["week_display"] = company_df["week_display"].astype(str)
            company_df["usage_rate_display"] = company_df["usage_rate"].apply(
                lambda v: f"{v:.1%}" if pd.notna(v) else "無資料"
            )
            month_options: list[str] = []
            if "stat_month" in company_df.columns:
                unique_months = company_df["stat_month"].dropna().unique()
                if len(unique_months) > 0:
                    month_options = sorted([str(month) for month in unique_months], reverse=True)

            with cols[0]:
                st.markdown(
                    info_badge("全公司週使用率", CHART_TOOLTIPS.get("company_usage"), font_size="18px"),
                    unsafe_allow_html=True,
                )
                display_df = company_df
                if month_options:
                    selected_month = st.selectbox(
                        "選擇月份檢視週使用率",
                        month_options,
                        index=0,
                        key="company_usage_month",
                    )
                    display_df = company_df[company_df["stat_month"].astype(str) == selected_month]
                if display_df.empty:
                    st.info("所選月份沒有週使用率資料。")
                else:
                    display_df = display_df.sort_values(sort_keys) if sort_keys else display_df
                    fig = px.bar(
                        display_df,
                        x="week_display",
                        y="usage_rate",
                        text="usage_rate_display",
                        hover_data={
                            "usage_rate_display": True,
                            "active_users": True,
                            "total_users": True,
                        },
                        labels={"week_display": "ISO 週次", "usage_rate": "使用率"},
                    )
                    fig.update_traces(textposition="outside")
                    fig.update_layout(title=None, xaxis_title="ISO 週次", yaxis_title="使用率 (%)")
                    fig.update_yaxes(tickformat=".0%")

                    st.plotly_chart(
                        fig,
                        use_container_width=True,
                        config={"modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"], "displaylogo": False},
                    )

                    summary_cols = [
                        col for col in ["week_display", "active_users", "total_users", "usage_rate_display"]
                        if col in display_df.columns
                    ]
                    if summary_cols:
                        summary_df = display_df[summary_cols].rename(
                            columns={
                                "week_display": "週次",
                                "active_users": "本週使用人數",
                                "total_users": "全公司總員工數",
                                "usage_rate_display": "使用率",
                            }
                        )
                        st.dataframe(summary_df, use_container_width=True)
    # 各部門週使用率 + 月度排行
    dept_df = pd.DataFrame(departments) if isinstance(departments, list) else pd.DataFrame()

    if dept_df.empty:
        with cols[1]:
            st.info("各部門週使用率沒有資料。")
    else:
        dept_df = dept_df.copy()
        if "stat_date" in dept_df.columns:
            dept_df["stat_date"] = pd.to_datetime(dept_df["stat_date"], errors="coerce")
        for col in ["usage_rate", "active_users", "total_users", "iso_year", "iso_week"]:
            if col in dept_df.columns:
                dept_df[col] = pd.to_numeric(dept_df[col], errors="coerce")

        def _build_unit_label(row: pd.Series) -> str:
            unit_id = row.get("unit_id")
            unit_name = row.get("unit_name")
            parts: list[str] = []
            if isinstance(unit_id, str) and unit_id.strip():
                parts.append(unit_id.strip())
            elif pd.notna(unit_id):
                parts.append(str(unit_id))
            if isinstance(unit_name, str) and unit_name.strip():
                parts.append(unit_name.strip())
            elif pd.notna(unit_name):
                parts.append(str(unit_name))
            return " ".join(parts) if parts else "未命名單位"

        dept_df["unit_label"] = dept_df.apply(_build_unit_label, axis=1)

        def _derive_iso_tuple(row: pd.Series) -> tuple[int, int] | None:
            year = row.get("iso_year")
            week = row.get("iso_week")
            try:
                if pd.notna(year) and pd.notna(week):
                    return int(year), int(week)
            except (TypeError, ValueError):
                pass
            stat_date = row.get("stat_date")
            if isinstance(stat_date, pd.Timestamp) and not pd.isna(stat_date):
                iso = stat_date.isocalendar()
                return int(iso.year), int(iso.week)
            return None

        dept_df["iso_tuple"] = dept_df.apply(_derive_iso_tuple, axis=1)

        def _make_week_display(row: pd.Series) -> str:
            label = row.get("week_label")
            if isinstance(label, str) and label.strip():
                return label.strip()
            iso_tuple = row.get("iso_tuple")
            if isinstance(iso_tuple, tuple):
                year, week = iso_tuple
                return f"{year}-W{week:02d}"
            stat_date = row.get("stat_date")
            if isinstance(stat_date, pd.Timestamp) and not pd.isna(stat_date):
                return stat_date.strftime("%G-W%V")
            return "未知週次"

        dept_df["week_display"] = dept_df.apply(_make_week_display, axis=1)

        def _make_week_key(row: pd.Series) -> str:
            iso_tuple = row.get("iso_tuple")
            if isinstance(iso_tuple, tuple):
                year, week = iso_tuple
                return f"{year:04d}-W{week:02d}"
            display = row.get("week_display")
            if isinstance(display, str) and display.strip():
                return display
            stat_date = row.get("stat_date")
            if isinstance(stat_date, pd.Timestamp) and not pd.isna(stat_date):
                iso = stat_date.isocalendar()
                return f"{int(iso.year):04d}-W{int(iso.week):02d}"
            return f"week-{row.name}"

        dept_df["week_key"] = dept_df.apply(_make_week_key, axis=1)
        dept_df["week_sort"] = dept_df["iso_tuple"].apply(
            lambda iso_val: iso_val[0] * 100 + iso_val[1] if isinstance(iso_val, tuple) else float("nan")
        )
        if "stat_date" in dept_df.columns:
            missing_week_sort_mask = dept_df["week_sort"].isna()
            if missing_week_sort_mask.any():
                ordinal_values = pd.to_numeric(
                    dept_df.loc[missing_week_sort_mask, "stat_date"].map(
                        lambda d: d.toordinal()
                        if isinstance(d, pd.Timestamp) and not pd.isna(d)
                        else float("nan")
                    ),
                    errors="coerce",
                )
                dept_df.loc[missing_week_sort_mask, "week_sort"] = ordinal_values

        week_options_df = (
            dept_df[["week_key", "week_display", "week_sort"]]
            .drop_duplicates()
            .sort_values(by=["week_sort", "week_display"], ascending=[False, True], na_position="last")
        )
        week_records = week_options_df.to_dict("records")
        week_labels = {rec["week_key"]: rec.get("week_display") or rec["week_key"] for rec in week_records}

        with cols[1]:
            st.markdown(
                info_badge("各部門週使用率", CHART_TOOLTIPS.get("department_usage"), font_size="18px"),
                unsafe_allow_html=True,
            )

            if not week_records:
                st.info("部門資料缺少週次資訊，無法顯示週別使用狀況。")
            else:
                default_index = 0
                selected_week = st.selectbox(
                    "選擇週次",
                    options=[rec["week_key"] for rec in week_records],
                    index=default_index,
                    key="department_usage_week",
                    format_func=lambda key: week_labels.get(key, key),
                )

                week_df = dept_df.loc[dept_df["week_key"] == selected_week].copy()
                if week_df.empty:
                    st.info("所選週次沒有部門使用率資料。")
                else:
                    chart_type = st.radio(
                        "圖表類型",
                        ("圓餅圖", "長條圖"),
                        horizontal=True,
                        key="department_usage_chart_type",
                    )

                    chart_df = week_df.dropna(subset=["usage_rate"]).copy()
                    chart_df["usage_rate_pct"] = chart_df["usage_rate"] * 100
                    chart_df["usage_rate_label"] = chart_df["usage_rate_pct"].map(
                        lambda v: f"{v:.2f}%" if pd.notna(v) else "無資料"
                    )

                    if chart_df.empty:
                        st.info("所選週次缺少啟用率資料，無法繪製圖表。")
                    else:
                        chart_labels = {
                            "unit_label": "單位",
                            "usage_rate_pct": "啟用率 (%)",
                            "usage_rate_label": "啟用率",
                            "active_users": "使用人數",
                            "total_users": "總人數",
                        }

                        hover_data = {
                            key: True
                            for key in ["usage_rate_label", "active_users", "total_users"]
                            if key in chart_df.columns
                        }

                        if chart_type == "圓餅圖":
                            fig = px.pie(
                                chart_df,
                                names="unit_label",
                                values="usage_rate_pct",
                                hover_data=hover_data,
                                labels=chart_labels,
                            )
                            fig.update_traces(texttemplate="%{label}<br>%{value:.2f}%", textposition="inside")
                            fig.update_layout(legend_title_text="單位")
                        else:
                            chart_df = chart_df.sort_values("usage_rate_pct", ascending=False)
                            fig = px.bar(
                                chart_df,
                                x="unit_label",
                                y="usage_rate_pct",
                                text="usage_rate_label",
                                hover_data=hover_data,
                                labels=chart_labels,
                            )
                            fig.update_traces(textposition="outside")
                            fig.update_layout(
                                xaxis_title="單位",
                                yaxis_title="啟用率 (%)",
                                xaxis_tickangle=-30,
                            )

                        st.plotly_chart(
                            fig,
                            use_container_width=True,
                            config={"modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"], "displaylogo": False},
                        )

                    st.caption(f"週次：{week_labels.get(selected_week, selected_week)}")

                    table_df = week_df.copy()
                    if "usage_rate" in table_df.columns:
                        table_df["usage_rate_pct"] = table_df["usage_rate"] * 100
                        table_df["usage_rate_label"] = table_df["usage_rate_pct"].map(
                            lambda v: f"{v:.2f}%" if pd.notna(v) else "無資料"
                        )
                    for col in ["active_users", "total_users"]:
                        if col in table_df.columns:
                            table_df[col] = pd.to_numeric(table_df[col], errors="coerce").astype("Int64")
                    display_cols = []
                    rename_map = {}
                    if "unit_id" in table_df.columns:
                        display_cols.append("unit_id")
                        rename_map["unit_id"] = "處級代碼"
                    if "unit_name" in table_df.columns:
                        display_cols.append("unit_name")
                        rename_map["unit_name"] = "處級名稱"
                    if "total_users" in table_df.columns:
                        display_cols.append("total_users")
                        rename_map["total_users"] = "總人數"
                    if "active_users" in table_df.columns:
                        display_cols.append("active_users")
                        rename_map["active_users"] = "使用人數"
                    if "usage_rate_label" in table_df.columns:
                        display_cols.append("usage_rate_label")
                        rename_map["usage_rate_label"] = "啟用率百分比"

                    if display_cols:
                        table_df = table_df.sort_values("usage_rate", ascending=False, na_position="last")
                        st.dataframe(
                            table_df[display_cols].rename(columns=rename_map),
                            use_container_width=True,
                            hide_index=True,
                        )

        # --- 月度平均使用率排行（依 unit_name 或 scope_id 彈性分組） ---
        # if "stat_date" in dept_df.columns:
        #     month_df = dept_df.dropna(subset=["stat_date"]).copy()
        #     if not month_df.empty:
        #         month_df["stat_month_label"] = month_df["stat_date"].dt.to_period("M").astype(str)
        #         month_options = sorted(month_df["stat_month_label"].dropna().unique(), reverse=True)
        #         if month_options:
        #             selected_month = st.selectbox(
        #                 "選擇月份檢視部門平均使用率排行",
        #                 month_options,
        #                 index=0,
        #                 key="department_usage_month",
        #             )

        #             month_filtered = month_df.loc[month_df["stat_month_label"] == selected_month]
        #             if month_filtered.empty:
        #                 st.info("所選月份沒有部門使用率資料。")
        #             elif "usage_rate" not in month_filtered.columns:
        #                 st.info("部門資料缺少使用率欄位，無法顯示月度排行。")
        #             else:
        #                 group_cols = [c for c in ["unit_name", "scope_id", "unit_id"] if c in month_filtered.columns]
        #                 if not group_cols:
        #                     st.info("部門資料缺少可分組欄位（unit_name / scope_id / unit_id）。")
        #                 else:
        #                     summary = month_filtered.groupby(group_cols, as_index=False)["usage_rate"].mean()
        #                     if summary.empty:
        #                         st.info("所選月份沒有有效的部門使用率資料。")
        #                     else:
        #                         label_col = "unit_name" if "unit_name" in summary.columns else group_cols[0]
        #                         summary["unit_label"] = summary[label_col].astype(str)
        #                         summary = summary.sort_values("usage_rate", ascending=False)

        #                         st.markdown(
        #                             info_badge(
        #                                 f"各部門月使用率（{selected_month}）",
        #                                 CHART_TOOLTIPS.get("department_usage"),
        #                                 font_size="18px",
        #                             ),
        #                             unsafe_allow_html=True,
        #                         )
        #                         fig_bar = px.bar(
        #                             summary,
        #                             x="unit_label",
        #                             y="usage_rate",
        #                             labels={"unit_label": "單位", "usage_rate": "使用率"},
        #                         )
        #                         fig_bar.update_layout(title=None, xaxis_title="單位", yaxis_title="使用率 (%)")
        #                         fig_bar.update_yaxes(tickformat=".0%")
        #                         fig_bar.update_traces(texttemplate="%{y:.1%}", textposition="outside")
        #                         st.plotly_chart(
        #                             fig_bar,
        #                             use_container_width=True,
        #                             config={"modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"], "displaylogo": False},
        #                         )
        #         else:
        #             st.info("沒有可供選擇的月份。")
        #     else:
        #         st.info("部門資料沒有有效日期，無法提供月度檢視。")
        # else:
        #     st.info("無法建立部門月度排行（缺少 stat_date 欄位或資料為空）。")


def render_engagement() -> None:
    """呈現黏著度分析（日活 / 週活）。"""
    try:
        data = fetch("engagement")
    except Exception as e:
        st.error(f"取得黏著度資料失敗：{e}")
        return

    daily = data.get("daily", [])
    weekly = data.get("weekly", [])

    if not daily and not weekly:
        st.info("目前沒有黏著度資料。")
        return

    cols = st.columns(2, gap="large")

    if daily:
        with cols[0]:
            st.markdown(
                info_badge("工作日日活躍趨勢", CHART_TOOLTIPS.get("daily_active"), font_size="18px"),
                unsafe_allow_html=True,
            )
            fig = px.line(
                daily,
                x="stat_date",
                y="active_rate",
                labels={"stat_date": "統計日期", "active_rate": "日活躍率"},
            )
            fig.update_yaxes(tickformat=".0%")
            fig.update_layout(title=None, xaxis_title="統計日期", yaxis_title="日活躍率 (%)")
            st.plotly_chart(
                fig,
                use_container_width=True,
                config={"modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"], "displaylogo": False},
            )

    if weekly:
        target_col = cols[1 if daily else 0]
        with target_col:
            st.markdown(
                info_badge("週活躍人數", CHART_TOOLTIPS.get("weekly_active"), font_size="18px"),
                unsafe_allow_html=True,
            )
            fig = px.line(
                weekly,
                x="stat_date",
                y="usage_rate",
                labels={"stat_date": "統計週起日", "usage_rate": "週活躍率"},
            )
            fig.update_yaxes(tickformat=".0%")
            fig.update_layout(title=None, xaxis_title="統計週起日", yaxis_title="週活躍率 (%)")
            st.plotly_chart(
                fig,
                use_container_width=True,
                config={"modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"], "displaylogo": False},
            )


def render_messages() -> None:
    """呈現訊息量分析。"""
    try:
        data = fetch("messages")
    except Exception as e:
        st.error(f"取得訊息量資料失敗：{e}")
        return

    trend_data = data.get("trend", [])
    distribution_data = data.get("distribution", [])
    leaderboard = data.get("leaderboard", [])

    if not trend_data and not distribution_data and not leaderboard:
        st.info("目前沒有訊息量相關資料。")
        return

    trend_df = pd.DataFrame(trend_data) if isinstance(trend_data, list) else pd.DataFrame()
    if not trend_df.empty:
        trend_df = trend_df.copy()
        if "stat_date" in trend_df.columns:
            trend_df["stat_date"] = pd.to_datetime(trend_df["stat_date"], errors="coerce")
            trend_df = trend_df.dropna(subset=["stat_date"]).sort_values("stat_date")
        if "total_employees" not in trend_df.columns and "total_installed" in trend_df.columns:
            trend_df["total_employees"] = trend_df["total_installed"]

    workday_df = (
        trend_df.loc[trend_df["stat_date"].dt.weekday < 5].copy()
        if not trend_df.empty
        else pd.DataFrame()
    )

    show_workday_trend = not workday_df.empty
    show_per_capita = (
        show_workday_trend
        and "total_employees" in workday_df.columns
        and workday_df["total_employees"].fillna(0).gt(0).any()
    )

    monthly_avg_df = pd.DataFrame()
    if show_workday_trend:
        monthly_source = workday_df.dropna(subset=["total_messages"]).copy()
        if not monthly_source.empty:
            monthly_source["total_messages"] = pd.to_numeric(
                monthly_source["total_messages"], errors="coerce"
            )
            monthly_source = monthly_source.dropna(subset=["total_messages"])
            if not monthly_source.empty:
                monthly_source["stat_month"] = monthly_source["stat_date"].dt.to_period("M")
                monthly_avg_df = (
                    monthly_source.groupby("stat_month", as_index=False)
                    .agg(
                        total_messages=("total_messages", "sum"),
                        workdays=("stat_date", "count"),
                    )
                )
                monthly_avg_df = monthly_avg_df[monthly_avg_df["workdays"] > 0]
                if not monthly_avg_df.empty:
                    monthly_avg_df["avg_messages"] = (
                        monthly_avg_df["total_messages"] / monthly_avg_df["workdays"]
                    )
                    monthly_avg_df["month_start"] = (
                        monthly_avg_df["stat_month"].dt.to_timestamp()
                    )
                    monthly_avg_df["month_label"] = monthly_avg_df["stat_month"].astype(str)
                    monthly_avg_df.sort_values("stat_month", inplace=True)

    monthly_per_capita_df = pd.DataFrame()
    if show_per_capita:
        per_capita_source = workday_df.dropna(
            subset=["total_messages", "total_employees"]
        ).copy()
        if not per_capita_source.empty:
            per_capita_source["total_messages"] = pd.to_numeric(
                per_capita_source["total_messages"], errors="coerce"
            )
            per_capita_source["total_employees"] = pd.to_numeric(
                per_capita_source["total_employees"], errors="coerce"
            )
            per_capita_source["total_employees"] = per_capita_source["total_employees"].replace({0: pd.NA})
            per_capita_source = per_capita_source.dropna(
                subset=["total_messages", "total_employees"]
            )
            per_capita_source = per_capita_source[per_capita_source["total_employees"] > 0]
            if not per_capita_source.empty:
                per_capita_source["stat_month"] = per_capita_source["stat_date"].dt.to_period("M")
                monthly_per_capita_df = (
                    per_capita_source.groupby("stat_month", as_index=False)
                    .agg(
                        total_messages=("total_messages", "sum"),
                        total_employees=("total_employees", "sum"),
                        workdays=("stat_date", "count"),
                    )
                )
                monthly_per_capita_df = monthly_per_capita_df[
                    monthly_per_capita_df["total_employees"] > 0
                ]
                if not monthly_per_capita_df.empty:
                    monthly_per_capita_df["messages_per_employee"] = (
                        monthly_per_capita_df["total_messages"]
                        / monthly_per_capita_df["total_employees"]
                    )
                    monthly_per_capita_df["avg_employees"] = (
                        monthly_per_capita_df["total_employees"]
                        / monthly_per_capita_df["workdays"]
                    )
                    monthly_per_capita_df["month_start"] = (
                        monthly_per_capita_df["stat_month"].dt.to_timestamp()
                    )
                    monthly_per_capita_df["month_label"] = (
                        monthly_per_capita_df["stat_month"].astype(str)
                    )
                    monthly_per_capita_df.sort_values("stat_month", inplace=True)

    if show_workday_trend:
        st.markdown(
            info_badge("工作日平均訊息數", CHART_TOOLTIPS.get("workday_messages"), font_size="18px"),
            unsafe_allow_html=True,
        )
        chart_col, table_col = st.columns((2, 1), gap="large")

        if monthly_avg_df.empty:
            with chart_col:
                st.info("目前沒有可用的工作日訊息資料。")
            with table_col:
                st.info("沒有資料可供列出。")
        else:
            with chart_col:
                customdata = monthly_avg_df[["month_label", "workdays", "total_messages"]].to_numpy()
                fig = go.Figure()
                fig.add_trace(
                    go.Bar(
                        x=monthly_avg_df["month_start"],
                        y=monthly_avg_df["avg_messages"],
                        name="平均訊息數",
                        customdata=customdata,
                        hovertemplate=(
                            "月份=%{customdata[0]}<br>"
                            "平均訊息數=%{y:,.2f} 則<br>"
                            "工作日數=%{customdata[1]:,.0f} 天<br>"
                            "訊息總數=%{customdata[2]:,.0f} 則<extra></extra>"
                        ),
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=monthly_avg_df["month_start"],
                        y=monthly_avg_df["avg_messages"],
                        mode="lines+markers",
                        name="趨勢線",
                        line=dict(color="#ff7f0e"),
                        hoverinfo="skip",
                    )
                )
                fig.update_layout(
                    title=None,
                    xaxis_title="統計月份",
                    yaxis_title="平均訊息數 (則)",
                    legend_title_text=None,
                )
                fig.update_xaxes(dtick="M1", tickformat="%Y-%m")
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    config={
                        "modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"],
                        "displaylogo": False,
                    },
                )

            with table_col:
                table_df = monthly_avg_df[
                    ["month_label", "avg_messages", "workdays", "total_messages"]
                ].copy()
                table_df["workdays"] = table_df["workdays"].round().astype("Int64")
                table_df.rename(
                    columns={
                        "month_label": "月份",
                        "avg_messages": "平均訊息數 (則)",
                        "workdays": "工作日數 (天)",
                        "total_messages": "訊息總數 (則)",
                    },
                    inplace=True,
                )
                table_df["平均訊息數 (則)"] = table_df["平均訊息數 (則)"].map(
                    lambda v: f"{v:,.2f}" if pd.notna(v) else "—"
                )
                table_df["工作日數 (天)"] = table_df["工作日數 (天)"].map(
                    lambda v: f"{int(v):,}" if pd.notna(v) else "—"
                )
                table_df["訊息總數 (則)"] = table_df["訊息總數 (則)"].map(
                    lambda v: f"{v:,.0f}" if pd.notna(v) else "—"
                )
                st.dataframe(table_df, use_container_width=True, hide_index=True)

    if show_per_capita:
        st.markdown(
            info_badge("工作日人均訊息數", CHART_TOOLTIPS.get("per_capita_messages"), font_size="18px"),
            unsafe_allow_html=True,
        )
        chart_col, table_col = st.columns((2, 1), gap="large")

        if monthly_per_capita_df.empty:
            with chart_col:
                st.info("目前沒有足夠的資料計算人均訊息數。")
            with table_col:
                st.info("沒有資料可供列出。")
        else:
            with chart_col:
                customdata = monthly_per_capita_df[
                    ["month_label", "avg_employees", "workdays", "total_messages"]
                ].to_numpy()
                fig = go.Figure()
                fig.add_trace(
                    go.Bar(
                        x=monthly_per_capita_df["month_start"],
                        y=monthly_per_capita_df["messages_per_employee"],
                        name="人均訊息數",
                        customdata=customdata,
                        hovertemplate=(
                            "月份=%{customdata[0]}<br>"
                            "人均訊息數=%{y:,.2f} 則<br>"
                            "平均在職員工=%{customdata[1]:,.0f} 人<br>"
                            "工作日數=%{customdata[2]:,.0f} 天<br>"
                            "訊息總數=%{customdata[3]:,.0f} 則<extra></extra>"
                        ),
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=monthly_per_capita_df["month_start"],
                        y=monthly_per_capita_df["messages_per_employee"],
                        mode="lines+markers",
                        name="趨勢線",
                        line=dict(color="#ff7f0e"),
                        hoverinfo="skip",
                    )
                )
                fig.update_layout(
                    title=None,
                    xaxis_title="統計月份",
                    yaxis_title="人均訊息數 (則)",
                    legend_title_text=None,
                )
                fig.update_xaxes(dtick="M1", tickformat="%Y-%m")
                fig.update_yaxes(tickformat=".2f")
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    config={
                        "modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"],
                        "displaylogo": False,
                    },
                )

            with table_col:
                table_df = monthly_per_capita_df[
                    [
                        "month_label",
                        "messages_per_employee",
                        "avg_employees",
                        "workdays",
                        "total_messages",
                    ]
                ].copy()
                table_df["avg_employees"] = table_df["avg_employees"].round()
                table_df["workdays"] = table_df["workdays"].round().astype("Int64")
                table_df.rename(
                    columns={
                        "month_label": "月份",
                        "messages_per_employee": "人均訊息數 (則)",
                        "avg_employees": "平均在職員工 (人)",
                        "workdays": "工作日數 (天)",
                        "total_messages": "訊息總數 (則)",
                    },
                    inplace=True,
                )
                table_df["人均訊息數 (則)"] = table_df["人均訊息數 (則)"].map(
                    lambda v: f"{v:,.2f}" if pd.notna(v) else "—"
                )
                table_df["平均在職員工 (人)"] = table_df["平均在職員工 (人)"].map(
                    lambda v: f"{v:,.0f}" if pd.notna(v) else "—"
                )
                table_df["工作日數 (天)"] = table_df["工作日數 (天)"].map(
                    lambda v: f"{int(v):,}" if pd.notna(v) else "—"
                )
                table_df["訊息總數 (則)"] = table_df["訊息總數 (則)"].map(
                    lambda v: f"{v:,.0f}" if pd.notna(v) else "—"
                )
                st.dataframe(table_df, use_container_width=True, hide_index=True)

    if distribution_data:
        dist_df = pd.DataFrame(distribution_data)
        if not dist_df.empty and "stat_date" in dist_df.columns:
            dist_df = dist_df.copy()
            dist_df["stat_date"] = pd.to_datetime(dist_df["stat_date"], errors="coerce")
            dist_df = dist_df.dropna(subset=["stat_date"]).sort_values(["stat_date", "segment"])
        else:
            dist_df = pd.DataFrame()

        st.markdown(
            info_badge("20/60/20 訊息分布", CHART_TOOLTIPS.get("message_distribution"), font_size="18px"),
            unsafe_allow_html=True,
        )

        if dist_df.empty:
            st.info("目前沒有足夠的訊息分布資料。")
        else:
            if not trend_df.empty and "total_messages" in trend_df.columns:
                totals_map = trend_df.set_index("stat_date")["total_messages"]
                dist_df["total_messages"] = dist_df["stat_date"].map(totals_map).fillna(0.0)
            else:
                dist_df["total_messages"] = 0.0
            dist_df["message_share"] = dist_df["message_share"].fillna(0.0)
            dist_df["message_count"] = dist_df["message_share"] * dist_df["total_messages"]
            dist_df["stat_month"] = dist_df["stat_date"].dt.to_period("M")

            segment_order = ["前20%", "中間60%", "後20%"]
            monthly_counts = (
                dist_df.groupby(["stat_month", "segment"], as_index=False)["message_count"].sum()
            )
            daily_totals = (
                dist_df[["stat_month", "stat_date", "total_messages"]]
                .drop_duplicates(subset=["stat_date"])
                .groupby("stat_month", as_index=False)["total_messages"].sum()
                .rename(columns={"total_messages": "month_total_messages"})
            )
            monthly_distribution = monthly_counts.merge(daily_totals, on="stat_month", how="left")
            monthly_distribution = monthly_distribution[monthly_distribution["month_total_messages"] > 0]

            if monthly_distribution.empty:
                st.info("目前沒有足夠的訊息分布資料。")
            else:
                monthly_distribution["message_share"] = (
                    monthly_distribution["message_count"] / monthly_distribution["month_total_messages"]
                )
                monthly_distribution["month_label"] = monthly_distribution["stat_month"].dt.strftime("%Y-%m")
                monthly_distribution["segment"] = pd.Categorical(
                    monthly_distribution["segment"],
                    categories=segment_order,
                    ordered=True,
                )
                monthly_distribution.sort_values(["stat_month", "segment"], inplace=True)

                fig = px.bar(
                    monthly_distribution,
                    x="month_label",
                    y="message_share",
                    color="segment",
                    custom_data=["message_count"],
                    category_orders={"segment": segment_order},
                    labels={"month_label": "月份", "message_share": "訊息佔比", "segment": "族群"},
                )
                fig.update_layout(
                    title=None,
                    xaxis_title="月份",
                    yaxis_title="訊息佔比 (%)",
                    barmode="stack",
                    legend_title_text="族群",
                )
                fig.update_yaxes(tickformat=".0%")
                fig.update_traces(
                    hovertemplate="月份=%{x}<br>%{fullData.name}占比=%{y:.2%}<br>訊息數=%{customdata[0]:,.0f} 則<extra></extra>"
                )
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    config={
                        "modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"],
                        "displaylogo": False,
                    },
                )

    if leaderboard:
        st.markdown(
            info_badge("Top 10 使用者", CHART_TOOLTIPS.get("message_leaderboard"), font_size="18px"),
            unsafe_allow_html=True,
        )
        df = pd.DataFrame(leaderboard) if isinstance(leaderboard, list) else leaderboard
        st.table(df)


def render_activation() -> None:
    """呈現啟用與留存分析。"""
    try:
        data = fetch("activation")
    except Exception as e:
        st.error(f"取得啟用/留存資料失敗：{e}")
        return

    activation = [item for item in data.get("activation", []) if item.get("unit_id") or item.get("unit_name")]
    retention = [item for item in data.get("retention", []) if item.get("unit_id") or item.get("unit_name")]

    if not activation and not retention:
        st.info("目前沒有啟用與留存資料。")
        return

    cols = st.columns(2, gap="large")

    if activation:
        with cols[0]:
            st.markdown(
                info_badge("部門啟用率", CHART_TOOLTIPS.get("activation"), font_size="18px"),
                unsafe_allow_html=True,
            )
            fig = px.bar(
                activation,
                x="stat_month",
                y="activation_rate",
                color="unit_id" if any("unit_id" in d for d in activation) else None,
                labels={"stat_month": "統計月份", "activation_rate": "啟用率", "unit_id": "處級代碼"},
                hover_data={"unit_name": True, "activated_users": True} if any("unit_name" in d for d in activation) else None,
            )
            fig.update_yaxes(tickformat=".0%")
            fig.update_layout(title=None, xaxis_title="統計月份", yaxis_title="啟用率 (%)")
            st.plotly_chart(
                fig,
                use_container_width=True,
                config={"modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"], "displaylogo": False},
            )

    if retention:
        target_col = cols[1 if activation else 0]
        with target_col:
            st.markdown(
                info_badge("部門留存率", CHART_TOOLTIPS.get("retention"), font_size="18px"),
                unsafe_allow_html=True,
            )
            fig = px.line(
                retention,
                x="stat_month",
                y="retention_rate",
                color="unit_id" if any("unit_id" in d for d in retention) else None,
                labels={"stat_month": "統計月份", "retention_rate": "留存率", "unit_id": "處級代碼"},
                hover_data={"unit_name": True, "retained_users": True} if any("unit_name" in d for d in retention) else None,
            )
            fig.update_yaxes(tickformat=".0%")
            fig.update_layout(title=None, xaxis_title="統計月份", yaxis_title="留存率 (%)")
            st.plotly_chart(
                fig,
                use_container_width=True,
                config={"modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"], "displaylogo": False},
            )


# ---- 頁面組裝 ----
render_overview()

usage_tab, engagement_tab, message_tab, activation_tab = st.tabs(
    ["使用人數分析", "訊息量分析" , "黏著度分析", "啟用與留存"]
)

with usage_tab:
    render_usage()
with engagement_tab:
    render_engagement()
with message_tab:
    render_messages()
with activation_tab:
    render_activation()

st.caption(f"最後更新：{datetime.now():%Y-%m-%d %H:%M:%S}")

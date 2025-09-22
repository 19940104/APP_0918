"""Streamlit 儀表板原型。"""

from __future__ import annotations

import html
import math
import os
from datetime import datetime

import pandas as pd
import plotly.express as px
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
    "message_trend": "每日訊息總數，觀察整體訊息量趨勢並評估系統負載。",
    "message_distribution": "20/60/20 分布，判斷訊息是否集中在少數人。",
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
            company_df["week_display"] = company_df["week_display"].fillna(
                company_df.index.to_series().add(1).map(lambda idx: f"週次 {idx}")
            )
            company_df["week_display"] = company_df["week_display"].astype(str)
            company_df["usage_rate_display"] = company_df["usage_rate"].apply(
                lambda v: f"{v:.1%}" if pd.notna(v) else "無資料"
            )

            with cols[0]:
                st.markdown(
                    info_badge("全公司週使用率", CHART_TOOLTIPS.get("company_usage"), font_size="18px"),
                    unsafe_allow_html=True,
                )
                fig = px.bar(
                    company_df,
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
                    if col in company_df.columns
                ]
                if summary_cols:
                    summary_df = company_df[summary_cols].rename(
                        columns={
                            "week_display": "週次",
                            "active_users": "本週使用人數",
                            "total_users": "全公司總員工數",
                            "usage_rate_display": "使用率",
                        }
                    )
                    st.dataframe(summary_df, use_container_width=True)
    # 各部門週使用率 + 月度排行
    if departments:
        with cols[1]:
            st.markdown(
                info_badge("各部門週使用率", CHART_TOOLTIPS.get("department_usage"), font_size="18px"),
                unsafe_allow_html=True,
            )
            fig = px.line(
                departments,
                x="stat_date",
                y="usage_rate",
                color="unit_name",
                labels={"stat_date": "統計日期", "usage_rate": "使用率", "unit_name": "部門"},
            )
            fig.update_layout(title=None, xaxis_title="統計日期", yaxis_title="使用率 (%)")
            fig.update_yaxes(tickformat=".0%")
            st.plotly_chart(
                fig,
                use_container_width=True,
                config={"modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"], "displaylogo": False},
            )

        # --- 月度平均使用率排行（依 unit_name 或 scope_id 彈性分組） ---
        dept_df = pd.DataFrame(departments)
        if not dept_df.empty and "stat_date" in dept_df.columns:
            dept_df = dept_df.copy()
            dept_df["stat_date"] = pd.to_datetime(dept_df["stat_date"], errors="coerce")
            dept_df = dept_df.dropna(subset=["stat_date"])
            if not dept_df.empty:
                dept_df["stat_month_label"] = dept_df["stat_date"].dt.to_period("M").astype(str)
                month_options = sorted(dept_df["stat_month_label"].dropna().unique(), reverse=True)
                if month_options:
                    selected_month = st.selectbox("選擇月份檢視部門平均使用率排行", month_options, index=0, key="department_usage_month")

                    month_df = dept_df.loc[dept_df["stat_month_label"] == selected_month]
                    if month_df.empty:
                        st.info("所選月份沒有部門使用率資料。")
                    elif "usage_rate" not in month_df.columns:
                        st.info("部門資料缺少使用率欄位，無法顯示月度排行。")
                    else:
                        group_cols = [c for c in ["unit_name", "scope_id", "unit_id"] if c in month_df.columns]
                        if not group_cols:
                            st.info("部門資料缺少可分組欄位（unit_name / scope_id / unit_id）。")
                        else:
                            summary = (
                                month_df.groupby(group_cols, as_index=False)["usage_rate"].mean()
                            )
                            if summary.empty:
                                st.info("所選月份沒有有效的部門使用率資料。")
                            else:
                                # 產生顯示用標籤
                                label_col = "unit_name" if "unit_name" in summary.columns else group_cols[0]
                                summary["unit_label"] = summary[label_col].astype(str)
                                summary = summary.sort_values("usage_rate", ascending=False)

                                st.markdown(
                                    info_badge(f"各部門月使用率（{selected_month}）", CHART_TOOLTIPS.get("department_usage"), font_size="18px"),
                                    unsafe_allow_html=True,
                                )
                                fig_bar = px.bar(
                                    summary,
                                    x="unit_label",
                                    y="usage_rate",
                                    labels={"unit_label": "單位", "usage_rate": "使用率"},
                                )
                                fig_bar.update_layout(title=None, xaxis_title="單位", yaxis_title="使用率 (%)")
                                fig_bar.update_yaxes(tickformat=".0%")
                                fig_bar.update_traces(texttemplate="%{y:.1%}", textposition="outside")
                                st.plotly_chart(
                                    fig_bar,
                                    use_container_width=True,
                                    config={"modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"], "displaylogo": False},
                                )
                else:
                    st.info("沒有可供選擇的月份。")
            else:
                st.info("部門資料沒有有效日期，無法提供月度檢視。")
        else:
            st.info("無法建立部門月度排行（缺少 stat_date 欄位或資料為空）。")


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

    trend = data.get("trend", [])
    dist = data.get("distribution", [])
    leaderboard = data.get("leaderboard", [])

    if not trend and not dist and not leaderboard:
        st.info("目前沒有訊息量相關資料。")
        return

    cols = st.columns(2, gap="large")

    if trend:
        with cols[0]:
            st.markdown(
                info_badge("訊息量趨勢", CHART_TOOLTIPS.get("message_trend"), font_size="18px"),
                unsafe_allow_html=True,
            )
            fig = px.bar(
                trend,
                x="stat_date",
                y="total_messages",
                labels={"stat_date": "統計日期", "total_messages": "訊息數"},
            )
            fig.update_layout(title=None, xaxis_title="統計日期", yaxis_title="訊息數 (則)")
            st.plotly_chart(
                fig,
                use_container_width=True,
                config={"modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"], "displaylogo": False},
            )

    if dist:
        target_col = cols[1 if trend else 0]
        with target_col:
            st.markdown(
                info_badge("20/60/20 訊息分布", CHART_TOOLTIPS.get("message_distribution"), font_size="18px"),
                unsafe_allow_html=True,
            )
            fig = px.area(
                dist,
                x="stat_date",
                y="message_share",
                color="segment",
                labels={"stat_date": "統計日期", "message_share": "訊息占比", "segment": "族群"},
            )
            fig.update_yaxes(tickformat=".0%")
            fig.update_layout(title=None, xaxis_title="統計日期", yaxis_title="訊息占比 (%)")
            st.plotly_chart(
                fig,
                use_container_width=True,
                config={"modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"], "displaylogo": False},
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
    ["使用人數分析", "黏著度分析", "訊息量分析", "啟用與留存"]
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

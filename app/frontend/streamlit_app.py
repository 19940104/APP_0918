"""Streamlit 儀表板原型。"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from app.frontend.common import OVERVIEW_TOOLTIPS, fetch, format_metric_value, info_badge
from app.frontend.tabs import (
    render_activation,
    render_engagement,
    render_messages,
    render_usage,
)

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


def render_overview() -> None:
    """繪製首頁 KPI。"""
    try:
        data = fetch("overview")
    except Exception as exc:  # pragma: no cover - Streamlit handles display
        st.error(f"取得總覽資料失敗：{exc}")
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
            display = format_metric_value(raw, suffix, multiplier)
            st.metric(label=label, value=display)


# ---- 頁面組裝 ----
render_overview()

usage_tab, message_tab, engagement_tab, activation_tab = st.tabs(
    ["使用人數分析", "訊息量分析", "黏著度分析", "啟用與留存"]
)

with usage_tab:
    render_usage()
with message_tab:
    render_messages()
with engagement_tab:
    render_engagement()
with activation_tab:
    render_activation()

st.caption(f"最後更新：{datetime.now():%Y-%m-%d %H:%M:%S}")

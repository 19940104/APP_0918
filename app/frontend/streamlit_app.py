"""
Streamlit 儀表板原型 (Main Entry Point)。

此模組負責：
1. 設定儀表板基本資訊 (標題、版面配置、樣式)。
2. 引用共用工具 (common.py) 與分頁模組 (tabs)。
3. 繪製首頁 KPI 總覽。
4. 組裝主要分析分頁：
   - 人員覆蓋率統計
   - 人員黏著度統計
   - 人員啟用率與留存率
   - 訊息量統計
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

# 共用工具
from common import OVERVIEW_TOOLTIPS, fetch, format_metric_value, info_badge

# 各分頁
from tabs.activation import render_activation
from tabs.engagement import render_engagement
from tabs.messages import render_messages
from tabs.usage import render_usage


# =============================================================================
# 頁面初始化
# =============================================================================
st.set_page_config(
    page_title="APP 使用分析儀表板",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.title("APP 使用分析儀表板")
st.caption("資料來源：DuckDB 彙總表 / 透過 FastAPI 提供")

# ---- 自訂 CSS：全寬版面 & 隱藏 Streamlit 預設工具列 ----
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


# =============================================================================
# 首頁 KPI 總覽
# =============================================================================
def _label_from_weekly(item: Dict[str, Any]) -> str:
    """週 KPI 的顯示標籤：優先使用 week_label，否則用 stat_date(YYYY-Wxx)。"""
    if not item:
        return "—"
    week_label = item.get("week_label")
    if isinstance(week_label, str) and week_label.strip():
        return week_label
    stat_date = item.get("stat_date")
    try:
        # 若後端有給 stat_date 就轉成週標籤
        ts = pd.to_datetime(stat_date)
        iso = ts.isocalendar()
        return f"{int(iso.year)}-W{int(iso.week):02d}"
    except Exception:
        return str(stat_date or "—")


def _label_from_month(item: Dict[str, Any]) -> str:
    """月 KPI 的顯示標籤：stat_month -> YYYY-MM。"""
    if not item:
        return "—"
    stat_month = item.get("stat_month")
    try:
        return pd.to_datetime(stat_month).strftime("%Y-%m")
    except Exception:
        return str(stat_month or "—")


def _label_from_date(item: Dict[str, Any]) -> str:
    """日 KPI 的顯示標籤：stat_date -> YYYY-MM-DD。"""
    if not item:
        return "—"
    stat_date = item.get("stat_date")
    try:
        return pd.to_datetime(stat_date).strftime("%Y-%m-%d")
    except Exception:
        return str(stat_date or "—")


def render_overview() -> None:
    """繪製首頁 KPI。"""
    try:
        data: Dict[str, Any] = fetch("overview")
    except Exception as exc:  # pragma: no cover
        st.error(f"取得總覽資料失敗：{exc}")
        return

    daily_active = data.get("daily_active") or {}
    weekly_usage = data.get("weekly_usage") or {}
    activation = data.get("activation") or {}
    message_kpi = data.get("message") or {}

    cols = st.columns(4, gap="large")

    # 每日活躍
    with cols[0]:
        st.markdown(
            info_badge("每日活躍", OVERVIEW_TOOLTIPS.get("每日活躍"), font_size="18px"),
            unsafe_allow_html=True,
        )
        val = daily_active.get("active_users")
        label = _label_from_date(daily_active)
        st.metric(label=label, value=format_metric_value(val, "人", 1))

    # 當週使用率
    with cols[1]:
        st.markdown(
            info_badge("當週使用率", OVERVIEW_TOOLTIPS.get("當週使用率"), font_size="18px"),
            unsafe_allow_html=True,
        )
        val = weekly_usage.get("usage_rate")
        label = _label_from_weekly(weekly_usage)
        st.metric(label=label, value=format_metric_value(val, "%", 100))

    # 當月新人啟用率
    with cols[2]:
        st.markdown(
            info_badge("當月新人啟用率", OVERVIEW_TOOLTIPS.get("當月新人啟用率"), font_size="18px"),
            unsafe_allow_html=True,
        )
        val = activation.get("activation_rate")
        label = _label_from_month(activation)
        st.metric(label=label, value=format_metric_value(val, "%", 100))

    # 當日訊息
    with cols[3]:
        st.markdown(
            info_badge("當日訊息", OVERVIEW_TOOLTIPS.get("當日訊息"), font_size="18px"),
            unsafe_allow_html=True,
        )
        val = message_kpi.get("total_messages")
        label = _label_from_date(message_kpi)
        st.metric(label=label, value=format_metric_value(val, "則", 1))


# =============================================================================
# 分頁組裝
# =============================================================================
render_overview()

tab1, tab2, tab3, tab4 = st.tabs(
    [
        "人員覆蓋率統計",
        "人員黏著度統計",
        "人員啟用率與留存率",
        "訊息量統計",
    ]
)

with tab1:
    render_usage()
with tab2:
    render_engagement()
with tab3:
    render_activation()
with tab4:
    render_messages()

# =============================================================================
# 更新時間
# =============================================================================
st.caption(f"最後更新：{datetime.now():%Y-%m-%d %H:%M:%S}")

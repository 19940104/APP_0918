"""
Streamlit 儀表板原型 (Main Entry Point)。

此模組負責：
1. 設定儀表板基本資訊 (標題、版面配置、樣式)。
2. 引用共用工具 (common.py) 與分頁模組 (tabs)。
3. 繪製首頁 KPI 總覽。
4. 組裝四個主要分析分頁：
   - 使用人數分析
   - 訊息量分析
   - 黏著度分析
   - 啟用與留存

結構設計：
- 初始化設定：頁面配置、標題、樣式覆寫。
- render_overview(): 繪製首頁 KPI 區塊 (每日活躍、週使用率、新人啟用率、當日訊息)。
- 分頁組裝：引用 tabs 內的 render_xxx() 函式，將各子頁面插入主頁面。

此模組是整個 Streamlit 儀表板的主框架。
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

# 直接引用同層的 common.py
from common import OVERVIEW_TOOLTIPS, fetch, format_metric_value, info_badge

# 直接引用 tabs 資料夾裡的模組
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
st.caption("資料來源：DuckDB 彙總表")

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


# =============================================================================
# 分頁組裝
# =============================================================================
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

# =============================================================================
# 更新時間
# =============================================================================
st.caption(f"最後更新：{datetime.now():%Y-%m-%d %H:%M:%S}")

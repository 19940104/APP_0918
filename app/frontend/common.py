"""Streamlit 儀表板的通用程式和常數"""

from __future__ import annotations

import html
import math
import os
from typing import Any, Optional, Dict

import requests
import streamlit as st


# 後端 API 的基礎路徑，預設為本機端口，亦可透過環境變數 DASHBOARD_API 覆寫
API_BASE = os.getenv("DASHBOARD_API", "http://localhost:8000/api/dashboard")

# 儀表板總覽卡片的提示文字 (對應 KPI 指標)
OVERVIEW_TOOLTIPS: Dict[str, str] = {
    "每日活躍": "當日有使用的人數 ÷ 總員工數，用來追蹤每天的實際使用狀況。",
    "當週使用率": "全公司有使用過人數 ÷ 全公司總員工數，用於評估推廣覆蓋率。",
    "當月新人啟用率": "啟用定義：到職後有使用過，可確認新人是否完成安裝並開始使用。",
    "當日訊息": "統計當日產生的訊息總數，用來評估互動熱度與系統負載。",
}

# 各圖表專用提示文字
CHART_TOOLTIPS: Dict[str, str] = {
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

# =============================================================================
# 資料存取工具 (Data Access Utilities)
# =============================================================================

def _request_json(url: str) -> Any:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()

def fetch(endpoint: str, *, ttl: int = 300) -> Any:
    """
    取得 API JSON，支援動態 ttl。
    注意：Streamlit 的 cache 是 decorator，不是 context manager。
    這裡在函式內部動態建立一個被 @st.cache_data 包住的內部函式，達成可調整 ttl 的效果。
    """
    url = f"{API_BASE}/{endpoint}"

    @st.cache_data(ttl=ttl, show_spinner=False)
    def _cached_fetch(_url: str) -> Any:
        return _request_json(_url)

    return _cached_fetch(url)

# 方便呼叫的封裝（需要不同 ttl 可以在這裡調整）
def fetch_overview() -> Any:   return fetch("overview", ttl=120)
def fetch_usage() -> Any:      return fetch("usage", ttl=300)
def fetch_engagement() -> Any: return fetch("engagement", ttl=300)
def fetch_messages() -> Any:   return fetch("messages", ttl=300)
def fetch_activation_api() -> Any: return fetch("activation", ttl=600)

# =============================================================================
# UI 元件工具 (UI Utilities)
# =============================================================================
def info_badge(title: str, tooltip: str | None = None, *, font_size: str = "16px") -> str:
    """標題 + ℹ️ 提示文字（滑鼠移入顯示）"""
    safe_title = html.escape(title)
    if not tooltip:
        return f"<div style='font-size:{font_size}; font-weight:600;'>{safe_title}</div>"
    safe_tip = html.escape(tooltip)
    return (
        "<div style='display:flex;align-items:center;gap:6px;"
        f"font-size:{font_size};font-weight:600;'>{safe_title}"
        f"<span style='cursor:help;' title='{safe_tip}'>ℹ️</span></div>"
    )

# =============================================================================
# 格式化工具 (Formatting Utilities)
# =============================================================================
def format_metric_value(value: Any, suffix: str, multiplier: float = 1.0) -> str:
    """格式化 KPI 值（百分比乘以 100，保留兩位小數）"""
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return "無資料"
    if isinstance(value, (int, float)):
        scaled_value = value * multiplier
        if suffix == "%":
            return f"{scaled_value:.2f}{suffix}"
        return f"{int(scaled_value)}{suffix}" if float(scaled_value).is_integer() else f"{scaled_value:.2f}{suffix}"
    return f"{value}{suffix}"

__all__ = [
    "API_BASE",
    "CHART_TOOLTIPS",
    "OVERVIEW_TOOLTIPS",
    "fetch",
    "fetch_overview",
    "fetch_usage",
    "fetch_engagement",
    "fetch_messages",
    "fetch_activation_api",
    "format_metric_value",
    "info_badge",
]

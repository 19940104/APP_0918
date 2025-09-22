from __future__ import annotations

import html
import math
import os
from typing import Sequence

import pandas as pd
import requests
import streamlit as st

API_BASE = os.getenv("DASHBOARD_API", "http://localhost:8000/api/dashboard")

_APP_PAGE_TITLE = "APP 使用分析儀表板"
_APP_PAGE_ICON = ":bar_chart:"
_GLOBAL_STYLE = """
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
"""


OVERVIEW_TOOLTIPS = {
    "每日活躍": "當日有使用的人數 ÷ 總員工數，用來追蹤每天的實際使用狀況。",
    "當週使用率": "全公司有使用過人數 ÷ 全公司總員工數，用於評估推廣覆蓋率。",
    "當月新人啟用率": "啟用定義：到職後有使用過，可確認新人是否完成安裝並開始使用。",
    "當日訊息": "統計當日產生的訊息總數，用來評估互動熱度與系統負載。",
}

CHART_TOOLTIPS = {
    "company_usage": "全公司有使用過人數 ÷ 總員工數，週別呈現以掌握推廣成效。",
    "department_usage": "各部門有使用過人數 ÷ 部門總員工數，辨識推廣強弱單位。",
    "daily_workday_active": "統計工作日的實際使用人數與在職人數，協助掌握每日黏著度。",
    "weekly_active": "當週有使用的人數 ÷ 總員工數，觀察定期使用的穩定度。",
    "workday_message_trend": "僅統計工作日訊息總數，逐日檢視互動熱度與系統負載。",
    "per_capita_messages": "工作日訊息總數除以在職員工數，評估人均互動深度。",
    "message_distribution": "以前 20% / 中間 60% / 後 20% 分層彙總訊息占比，判斷是否集中在少數人。",
    "message_leaderboard": "訊息量排名前 10 的使用者，協助了解核心使用者。",
    "activation_by_unit": "啟用率：到職後有使用過的人數比例，可確認新人是否完成安裝並啟用。",
    "activation_trend": "各部門啟用率的月度趨勢，快速掌握推廣成果。",
    "retention_trend": "已啟用者在當月至少登入一次的比例，用來評估留存狀況。",
}


def setup_page(page_title: str | None = None) -> None:
    """Set global Streamlit configuration and styles."""

    st.set_page_config(
        page_title=page_title or _APP_PAGE_TITLE,
        page_icon=_APP_PAGE_ICON,
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(_GLOBAL_STYLE, unsafe_allow_html=True)


@st.cache_data(ttl=300)
def fetch(endpoint: str):
    """Call backend API and cache results for 5 minutes."""

    url = f"{API_BASE}/{endpoint}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def info_badge(title: str, tooltip: str | None = None, *, font_size: str = "16px") -> str:
    """Render a heading with tooltip (ℹ️)."""

    safe_title = html.escape(title)
    if not tooltip:
        return f"<div style='font-size:{font_size}; font-weight:600;'>{safe_title}</div>"
    safe_tip = html.escape(tooltip)
    return (
        f"<div style='display:flex;align-items:center;gap:6px;font-size:{font_size};font-weight:600;'>"
        f"{safe_title}<span style='cursor:help;' title='{safe_tip}'>ℹ️</span></div>"
    )


def format_metric_value(value, suffix: str, multiplier: float = 1.0) -> str:
    """Format KPI value for display."""

    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return "無資料"
    if isinstance(value, (int, float)):
        display_value = value * multiplier
        if suffix == "%":
            return f"{display_value:.2f}{suffix}"
        return (
            f"{int(display_value)}{suffix}"
            if float(display_value).is_integer()
            else f"{display_value:.2f}{suffix}"
        )
    return f"{value}{suffix}"


def build_month_options(dates: pd.Series) -> list[str]:
    """Return sorted month options (YYYY-MM) from a datetime-like Series."""

    if dates.empty:
        return []
    months = (
        pd.to_datetime(dates, errors="coerce")
        .dropna()
        .to_series()
        .dt.to_period("M")
        .astype(str)
        .unique()
    )
    return sorted(months, reverse=True)


def filter_by_month(df: pd.DataFrame, month: str, *, date_col: str = "stat_date") -> pd.DataFrame:
    """Filter DataFrame rows that fall into a specific month label."""

    if df.empty or month is None:
        return df
    working = df.copy()
    working[date_col] = pd.to_datetime(working[date_col], errors="coerce")
    working = working.dropna(subset=[date_col])
    working["_month"] = working[date_col].dt.to_period("M").astype(str)
    return working.loc[working["_month"] == month].drop(columns="_month")


def ensure_datetime(series: pd.Series) -> pd.Series:
    """Convert a Series to datetime, ignoring invalid entries."""

    return pd.to_datetime(series, errors="coerce")


def ensure_numeric(series: pd.Series) -> pd.Series:
    """Convert Series to numeric with coercion."""

    return pd.to_numeric(series, errors="coerce")


def unique_sorted(values: Sequence[str]) -> list[str]:
    """Return unique sorted string values preserving descending order."""

    seen: set[str] = set()
    ordered: list[str] = []
    for item in values:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return sorted(ordered, reverse=True)


__all__ = [
    "API_BASE",
    "CHART_TOOLTIPS",
    "OVERVIEW_TOOLTIPS",
    "build_month_options",
    "ensure_datetime",
    "ensure_numeric",
    "fetch",
    "filter_by_month",
    "format_metric_value",
    "info_badge",
    "setup_page",
    "unique_sorted",
]

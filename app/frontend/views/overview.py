from __future__ import annotations

from datetime import date
from typing import Any, Dict

import streamlit as st

from app.frontend.dashboard_shared import (
    OVERVIEW_TOOLTIPS,
    fetch,
    format_metric_value,
    info_badge,
)


def _resolve_label(payload: Dict[str, Any]) -> str:
    """Best-effort extraction of the KPI label (date/month)."""

    for key in ("stat_date", "stat_month"):
        value = payload.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            return value
        if isinstance(value, date):
            return value.strftime("%Y-%m-%d") if key == "stat_date" else value.strftime("%Y-%m")
    return "—"


def render_overview() -> None:
    """Render top-level KPIs for the dashboard."""

    try:
        data = fetch("overview")
    except Exception as exc:  # pragma: no cover - defensive UI message
        st.error(f"取得總覽資料失敗：{exc}")
        return

    cols = st.columns(4, gap="large")
    mapping = [
        ("每日活躍", data.get("daily_active"), "active_users", "人", 1),
        ("當週使用率", data.get("weekly_usage"), "usage_rate", "%", 100),
        ("當月新人啟用率", data.get("activation"), "activation_rate", "%", 100),
        ("當日訊息", data.get("message"), "total_messages", "則", 1),
    ]

    for col, (title, payload, field, suffix, multiplier) in zip(cols, mapping):
        with col:
            st.markdown(
                info_badge(title, OVERVIEW_TOOLTIPS.get(title), font_size="18px"),
                unsafe_allow_html=True,
            )
            if not payload:
                st.write("無資料")
                continue
            raw_value = payload.get(field)
            label = _resolve_label(payload)
            display_value = format_metric_value(raw_value, suffix, multiplier)
            st.metric(label=label, value=display_value)

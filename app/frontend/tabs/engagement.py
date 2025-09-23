"""人員黏著度統計"""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from common import CHART_TOOLTIPS, fetch, info_badge



def render_engagement() -> None:
    """Render the engagement analysis tab."""
    try:
        data = fetch("engagement")
    except Exception as exc:  # pragma: no cover - Streamlit handles display
        st.error(f"取得黏著度資料失敗：{exc}")
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

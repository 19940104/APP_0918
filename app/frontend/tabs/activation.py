"""Activation and retention analytics tab."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from app.frontend.common import CHART_TOOLTIPS, fetch, info_badge


def render_activation() -> None:
    """Render the activation and retention analysis tab."""
    try:
        data = fetch("activation")
    except Exception as exc:  # pragma: no cover - Streamlit handles display
        st.error(f"取得啟用/留存資料失敗：{exc}")
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

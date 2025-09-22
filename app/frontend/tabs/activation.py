"""Activation and Retention Analytics Tab (安全版，模組化)."""

from __future__ import annotations
import pandas as pd
import plotly.express as px
import streamlit as st

from common import CHART_TOOLTIPS, fetch, info_badge


# ============================================================================
# 共用工具函式
# ============================================================================

def _apply_common_style(fig, x_title: str, y_title: str) -> None:
    """統一圖表樣式 (白底、動畫、百分比軸)。"""
    fig.update_layout(
        template="plotly_white",
        xaxis_title=x_title,
        yaxis_title=y_title,
        transition_duration=500,
    )
    fig.update_yaxes(tickformat=".0%")  # y 軸顯示為百分比


# ============================================================================
# 啟用率子模組
# ============================================================================

def render_activation_chart(activation: list[dict]) -> None:
    """渲染部門啟用率 (長條圖)。"""
    df = pd.DataFrame(activation)
    if df.empty:
        st.info("⚠️ 沒有啟用率資料")
        return

    # 處理月份
    if "stat_month" in df.columns:
        df["stat_month"] = pd.to_datetime(df["stat_month"], errors="coerce").dt.to_period("M").astype(str)

    # 繪製長條圖
    fig = px.bar(
        df,
        x="stat_month",
        y="activation_rate",
        color="activation_rate",
        color_continuous_scale="Blues",
        text=df["activation_rate"].map(lambda v: f"{v:.1%}"),
        hover_data=[
            col for col in ["unit_id", "unit_name", "activated_users"] if col in df.columns
        ],
        labels={"stat_month": "統計月份", "activation_rate": "啟用率"},
    )
    fig.update_traces(textposition="outside")
    _apply_common_style(fig, "統計月份", "啟用率 (%)")

    # 呈現圖表
    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"], "displaylogo": False},
    )


# ============================================================================
# 留存率子模組
# ============================================================================

def render_retention_chart(retention: list[dict]) -> None:
    """渲染部門留存率 (折線圖)。"""
    df = pd.DataFrame(retention)
    if df.empty:
        st.info("⚠️ 沒有留存率資料")
        return

    # 處理月份
    if "stat_month" in df.columns:
        df["stat_month"] = pd.to_datetime(df["stat_month"], errors="coerce").dt.to_period("M").astype(str)

    # 繪製折線圖 (平滑 + 數值點)
    fig = px.line(
        df,
        x="stat_month",
        y="retention_rate",
        color="unit_id" if "unit_id" in df.columns else None,
        markers=True,
        hover_data=[
            col for col in ["unit_id", "unit_name", "retained_users"] if col in df.columns
        ],
        labels={"stat_month": "統計月份", "retention_rate": "留存率"},
    )
    fig.update_traces(mode="lines+markers", line_shape="spline")
    _apply_common_style(fig, "統計月份", "留存率 (%)")

    # 呈現圖表
    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"], "displaylogo": False},
    )


# ============================================================================
# 主入口
# ============================================================================

def render_activation() -> None:
    """主入口：渲染部門啟用率 + 留存率 (左右並排)。"""
    try:
        data = fetch("activation")
    except Exception as exc:  # pragma: no cover
        st.error(f"取得啟用/留存資料失敗：{exc}")
        return

    activation = [i for i in data.get("activation", []) if i.get("unit_id") or i.get("unit_name")]
    retention = [i for i in data.get("retention", []) if i.get("unit_id") or i.get("unit_name")]

    if not activation and not retention:
        st.info("目前沒有啟用與留存資料。")
        return

    cols = st.columns(2, gap="large")

    if activation:
        with cols[0]:
            st.markdown(info_badge("部門啟用率", CHART_TOOLTIPS.get("activation"), font_size="18px"),
                        unsafe_allow_html=True)
            render_activation_chart(activation)

    if retention:
        with cols[1 if activation else 0]:
            st.markdown(info_badge("部門留存率", CHART_TOOLTIPS.get("retention"), font_size="18px"),
                        unsafe_allow_html=True)
            render_retention_chart(retention)

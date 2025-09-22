from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from app.frontend.dashboard_shared import CHART_TOOLTIPS, fetch, info_badge


def _build_unit_label(row: pd.Series) -> str:
    parts: list[str] = []
    unit_id = row.get("unit_id")
    unit_name = row.get("unit_name")
    if isinstance(unit_id, str) and unit_id.strip():
        parts.append(unit_id.strip())
    elif pd.notna(unit_id):
        parts.append(str(unit_id))
    if isinstance(unit_name, str) and unit_name.strip():
        parts.append(unit_name.strip())
    elif pd.notna(unit_name):
        parts.append(str(unit_name))
    return " ".join(parts) if parts else "未命名單位"


def _prepare_activation(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    if df.empty:
        return df
    df = df.copy()
    if "stat_month" in df.columns:
        df["stat_month"] = pd.to_datetime(df["stat_month"], errors="coerce")
        df = df.dropna(subset=["stat_month"])
        df["month_label"] = df["stat_month"].dt.strftime("%Y-%m")
    for col in ["activation_rate", "retention_rate", "activated_users", "retained_users"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["unit_label"] = df.apply(_build_unit_label, axis=1)
    return df


def _month_range_selector(label: str, options: list[str], *, key: str) -> tuple[str, str]:
    if not options:
        return "", ""
    options = sorted(options)
    if len(options) == 1:
        st.select_slider(label, options=options, value=options[0], key=key)
        return options[0], options[0]
    default_start = options[max(len(options) - 6, 0)]
    default_end = options[-1]
    start, end = st.select_slider(
        label,
        options=options,
        value=(default_start, default_end),
        key=key,
    )
    if start > end:
        start, end = end, start
    return start, end


def _default_units(df: pd.DataFrame, *, rate_col: str, limit: int = 5) -> list[str]:
    if df.empty or rate_col not in df.columns:
        return []
    latest_month = df["month_label"].max()
    if pd.isna(latest_month):
        return []
    latest_df = df[df["month_label"] == latest_month].dropna(subset=[rate_col])
    if latest_df.empty:
        return []
    latest_df = latest_df.sort_values(rate_col, ascending=False)
    return latest_df["unit_label"].head(limit).tolist()


def render_activation() -> None:
    """呈現啟用與留存分析。"""

    try:
        data = fetch("activation")
    except Exception as exc:  # pragma: no cover - defensive UI message
        st.error(f"取得啟用/留存資料失敗：{exc}")
        return

    activation_df = _prepare_activation(data.get("activation", []))
    retention_df = _prepare_activation(data.get("retention", []))

    if activation_df.empty and retention_df.empty:
        st.info("目前沒有啟用與留存資料。")
        return

    tab_bar, tab_trend = st.tabs(["柱狀圖", "趨勢圖"])

    with tab_bar:
        st.markdown(
            info_badge("部門啟用率", CHART_TOOLTIPS.get("activation_by_unit"), font_size="18px"),
            unsafe_allow_html=True,
        )
        if activation_df.empty:
            st.info("目前沒有部門啟用率資料。")
        else:
            month_options = sorted(activation_df["month_label"].unique(), reverse=True)
            selected_month = st.selectbox(
                "選擇月份檢視啟用率",
                month_options,
                index=0,
                key="activation_month_select",
            )
            month_data = activation_df[activation_df["month_label"] == selected_month].copy()
            if month_data.empty:
                st.info("所選月份沒有啟用率資料。")
            else:
                month_data = month_data.sort_values("activation_rate", ascending=False)
                month_data["activation_display"] = month_data["activation_rate"].map(
                    lambda v: f"{v:.2%}" if pd.notna(v) else "—"
                )
                fig = px.bar(
                    month_data,
                    x="unit_label",
                    y="activation_rate",
                    text="activation_display",
                    labels={"unit_label": "單位", "activation_rate": "啟用率"},
                )
                fig.update_layout(title=None, xaxis_title="單位", yaxis_title="啟用率 (%)")
                fig.update_yaxes(tickformat=".0%")
                fig.update_traces(textposition="outside")
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    config={"modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"], "displaylogo": False},
                )

                table = month_data[["unit_label", "activated_users", "activation_display"]].copy()
                table.rename(
                    columns={
                        "unit_label": "單位",
                        "activated_users": "啟用人數",
                        "activation_display": "啟用率",
                    },
                    inplace=True,
                )
                st.dataframe(table, use_container_width=True, hide_index=True)

    with tab_trend:
        columns = st.columns(2, gap="large")

        if activation_df.empty:
            with columns[0]:
                st.info("目前沒有啟用率趨勢資料。")
        else:
            month_options = sorted(activation_df["month_label"].unique())
            start_month, end_month = _month_range_selector(
                "選擇月份區間",
                month_options,
                key="activation_trend_range",
            )
            trend_data = activation_df[
                (activation_df["month_label"] >= start_month)
                & (activation_df["month_label"] <= end_month)
            ].copy()
            with columns[0]:
                st.markdown(
                    info_badge("啟用率趨勢", CHART_TOOLTIPS.get("activation_trend"), font_size="18px"),
                    unsafe_allow_html=True,
                )
                if trend_data.empty:
                    st.info("所選月份區間沒有啟用率資料。")
                else:
                    default_units = _default_units(trend_data, rate_col="activation_rate")
                    unit_choices = sorted(trend_data["unit_label"].unique())
                    selected_units = st.multiselect(
                        "選擇單位對比啟用率",
                        unit_choices,
                        default=default_units or unit_choices[:5],
                        key="activation_trend_units",
                    )
                    if not selected_units:
                        st.info("請至少選擇一個單位。")
                    else:
                        display = trend_data[trend_data["unit_label"].isin(selected_units)].copy()
                        fig = px.line(
                            display,
                            x="stat_month",
                            y="activation_rate",
                            color="unit_label",
                            markers=True,
                            labels={"stat_month": "統計月份", "activation_rate": "啟用率", "unit_label": "單位"},
                        )
                        fig.update_yaxes(tickformat=".0%")
                        fig.update_xaxes(dtick="M1", tickformat="%Y-%m")
                        fig.update_layout(title=None, legend_title_text="單位")
                        st.plotly_chart(
                            fig,
                            use_container_width=True,
                            config={"modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"], "displaylogo": False},
                        )

        if retention_df.empty:
            with columns[1]:
                st.info("目前沒有留存率趨勢資料。")
        else:
            month_options = sorted(retention_df["month_label"].unique())
            start_month, end_month = _month_range_selector(
                "選擇月份區間 (留存率)",
                month_options,
                key="retention_trend_range",
            )
            trend_data = retention_df[
                (retention_df["month_label"] >= start_month)
                & (retention_df["month_label"] <= end_month)
            ].copy()
            with columns[1]:
                st.markdown(
                    info_badge("留存率趨勢", CHART_TOOLTIPS.get("retention_trend"), font_size="18px"),
                    unsafe_allow_html=True,
                )
                if trend_data.empty:
                    st.info("所選月份區間沒有留存率資料。")
                else:
                    default_units = _default_units(trend_data, rate_col="retention_rate")
                    unit_choices = sorted(trend_data["unit_label"].unique())
                    selected_units = st.multiselect(
                        "選擇單位對比留存率",
                        unit_choices,
                        default=default_units or unit_choices[:5],
                        key="retention_trend_units",
                    )
                    if not selected_units:
                        st.info("請至少選擇一個單位。")
                    else:
                        display = trend_data[trend_data["unit_label"].isin(selected_units)].copy()
                        fig = px.line(
                            display,
                            x="stat_month",
                            y="retention_rate",
                            color="unit_label",
                            markers=True,
                            labels={"stat_month": "統計月份", "retention_rate": "留存率", "unit_label": "單位"},
                        )
                        fig.update_yaxes(tickformat=".0%")
                        fig.update_xaxes(dtick="M1", tickformat="%Y-%m")
                        fig.update_layout(title=None, legend_title_text="單位")
                        st.plotly_chart(
                            fig,
                            use_container_width=True,
                            config={"modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"], "displaylogo": False},
                        )

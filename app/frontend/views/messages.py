from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.frontend.dashboard_shared import (
    CHART_TOOLTIPS,
    build_month_options,
    ensure_datetime,
    fetch,
    info_badge,
)


def _prepare_trend(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    if df.empty:
        return df
    df = df.copy()
    if "stat_date" in df.columns:
        df["stat_date"] = ensure_datetime(df["stat_date"])
        df = df.dropna(subset=["stat_date"]).sort_values("stat_date")
        df["month_label"] = df["stat_date"].dt.to_period("M").astype(str)
        df["is_workday"] = df["stat_date"].dt.weekday < 5
    for col in ["total_messages", "active_users", "total_employees"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _prepare_distribution(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    if df.empty:
        return df
    df = df.copy()
    if "stat_date" in df.columns:
        df["stat_date"] = ensure_datetime(df["stat_date"])
        df = df.dropna(subset=["stat_date"])
        df["month_label"] = df["stat_date"].dt.to_period("M").astype(str)
    for col in ["user_share", "message_share"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def render_messages() -> None:
    """呈現訊息量分析。"""

    try:
        data = fetch("messages")
    except Exception as exc:  # pragma: no cover - defensive UI message
        st.error(f"取得訊息量資料失敗：{exc}")
        return

    trend_df = _prepare_trend(data.get("trend", []))
    distribution_df = _prepare_distribution(data.get("distribution", []))
    leaderboard_df = pd.DataFrame(data.get("leaderboard", []))

    if trend_df.empty and distribution_df.empty and leaderboard_df.empty:
        st.info("目前沒有訊息量相關資料。")
        return

    tabs = st.tabs(["折線圖", "柱狀圖", "結構圖", "排行榜"])

    with tabs[0]:
        st.markdown(
            info_badge("工作日平均訊息數", CHART_TOOLTIPS.get("workday_message_trend"), font_size="18px"),
            unsafe_allow_html=True,
        )
        if trend_df.empty:
            st.info("目前沒有可用的訊息資料。")
        else:
            workday_df = (
                trend_df.loc[trend_df["is_workday"]].copy()
                if "is_workday" in trend_df.columns
                else pd.DataFrame()
            )
            if workday_df.empty:
                st.info("目前沒有工作日訊息資料。")
            else:
                month_options = build_month_options(workday_df["stat_date"])
                if month_options:
                    selected_month = st.selectbox(
                        "選擇月份檢視訊息趨勢",
                        month_options,
                        index=0,
                        key="message_trend_month",
                    )
                    month_data = workday_df[workday_df["month_label"] == selected_month]
                else:
                    selected_month = None
                    month_data = workday_df

                if month_data.empty:
                    st.info("所選月份沒有訊息資料。")
                else:
                    fig = px.line(
                        month_data,
                        x="stat_date",
                        y="total_messages",
                        markers=True,
                        labels={"stat_date": "統計日期", "total_messages": "訊息數"},
                    )
                    fig.update_layout(title=None, xaxis_title="統計日期", yaxis_title="訊息數 (則)")
                    st.plotly_chart(
                        fig,
                        use_container_width=True,
                        config={"modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"], "displaylogo": False},
                    )
                    if selected_month:
                        st.caption(f"月份：{selected_month}")

    with tabs[1]:
        st.markdown(
            info_badge("工作日人均訊息數", CHART_TOOLTIPS.get("per_capita_messages"), font_size="18px"),
            unsafe_allow_html=True,
        )
        if trend_df.empty or "total_employees" not in trend_df.columns:
            st.info("目前沒有足夠的訊息資料計算人均訊息數。")
        else:
            workday_df = (
                trend_df.loc[trend_df["is_workday"]].copy()
                if "is_workday" in trend_df.columns
                else pd.DataFrame()
            )
            workday_df = workday_df.dropna(subset=["total_messages", "total_employees"])
            workday_df = workday_df[workday_df["total_employees"] > 0]
            if workday_df.empty:
                st.info("目前沒有足夠的訊息資料計算人均訊息數。")
            else:
                month_options = build_month_options(workday_df["stat_date"])
                if month_options:
                    selected_month = st.selectbox(
                        "選擇月份檢視人均訊息",
                        month_options,
                        index=0,
                        key="per_capita_month",
                    )
                    month_data = workday_df[workday_df["month_label"] == selected_month]
                else:
                    selected_month = None
                    month_data = workday_df

                if month_data.empty:
                    st.info("所選月份沒有訊息資料。")
                else:
                    month_data = month_data.sort_values("stat_date")
                    month_data["messages_per_employee"] = (
                        month_data["total_messages"] / month_data["total_employees"]
                    )
                    fig = go.Figure()
                    fig.add_trace(
                        go.Bar(
                            x=month_data["stat_date"],
                            y=month_data["messages_per_employee"],
                            name="人均訊息數",
                            marker_color="#1f77b4",
                        )
                    )
                    fig.add_trace(
                        go.Scatter(
                            x=month_data["stat_date"],
                            y=month_data["messages_per_employee"],
                            mode="lines+markers",
                            name="趨勢線",
                            line=dict(color="#ff7f0e"),
                        )
                    )
                    fig.update_layout(
                        title=None,
                        xaxis_title="統計日期",
                        yaxis_title="人均訊息數 (則)",
                        legend_title_text=None,
                    )
                    st.plotly_chart(
                        fig,
                        use_container_width=True,
                        config={"modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"], "displaylogo": False},
                    )
                    table = month_data[["stat_date", "total_messages", "total_employees", "messages_per_employee"]].copy()
                    table["stat_date"] = table["stat_date"].dt.strftime("%Y-%m-%d")
                    table.rename(
                        columns={
                            "stat_date": "日期",
                            "total_messages": "訊息數",
                            "total_employees": "在職員工數",
                            "messages_per_employee": "人均訊息數",
                        },
                        inplace=True,
                    )
                    table["人均訊息數"] = table["人均訊息數"].map(lambda v: f"{v:.2f}" if pd.notna(v) else "—")
                    st.dataframe(table, use_container_width=True, hide_index=True)

    with tabs[2]:
        st.markdown(
            info_badge("20/60/20 訊息分布", CHART_TOOLTIPS.get("message_distribution"), font_size="18px"),
            unsafe_allow_html=True,
        )
        if distribution_df.empty:
            st.info("目前沒有足夠的訊息分布資料。")
        else:
            month_options = build_month_options(distribution_df["stat_date"])
            if month_options:
                selected_month = st.selectbox(
                    "選擇月份檢視分布",
                    month_options,
                    index=0,
                    key="message_distribution_month",
                )
                month_dist = distribution_df[distribution_df["month_label"] == selected_month].copy()
            else:
                selected_month = None
                month_dist = distribution_df.copy()

            if month_dist.empty:
                st.info("所選月份沒有訊息分布資料。")
            else:
                if not trend_df.empty:
                    totals_map = trend_df.set_index("stat_date")["total_messages"]
                    month_dist["total_messages"] = month_dist["stat_date"].map(totals_map).fillna(0.0)
                else:
                    month_dist["total_messages"] = 0.0
                month_dist["message_count"] = month_dist["message_share"] * month_dist["total_messages"]
                summary = (
                    month_dist.groupby("segment", as_index=False)["message_count"].sum()
                )
                total_messages = summary["message_count"].sum()
                summary["message_share"] = (
                    summary["message_count"] / total_messages if total_messages else 0
                )
                summary.sort_values("segment", inplace=True)
                summary["segment"] = pd.Categorical(
                    summary["segment"],
                    categories=["前20%", "中間60%", "後20%"],
                    ordered=True,
                )
                summary.sort_values("segment", inplace=True)

                fig = px.bar(
                    summary,
                    x="segment",
                    y="message_share",
                    text=summary["message_share"].map(lambda v: f"{v:.2%}" if pd.notna(v) else "—"),
                    labels={"segment": "族群", "message_share": "訊息佔比"},
                )
                fig.update_layout(title=None, xaxis_title="族群", yaxis_title="訊息佔比 (%)")
                fig.update_yaxes(tickformat=".0%")
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    config={"modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"], "displaylogo": False},
                )
                table = summary.copy()
                table.rename(
                    columns={
                        "segment": "族群",
                        "message_count": "訊息數",
                        "message_share": "訊息佔比",
                    },
                    inplace=True,
                )
                table["訊息佔比"] = table["訊息佔比"].map(lambda v: f"{v:.2%}" if pd.notna(v) else "—")
                st.dataframe(table, use_container_width=True, hide_index=True)

    with tabs[3]:
        st.markdown(
            info_badge("Top 10 使用者", CHART_TOOLTIPS.get("message_leaderboard"), font_size="18px"),
            unsafe_allow_html=True,
        )
        if leaderboard_df.empty:
            st.info("目前沒有排行榜資料。")
        else:
            leaderboard_df = leaderboard_df.copy()
            leaderboard_df.rename(
                columns={
                    "rank": "名次",
                    "emp_no": "員工編號",
                    "unit_id": "處級代碼",
                    "unit_name": "處級名稱",
                    "total_messages": "訊息數",
                },
                inplace=True,
            )
            st.dataframe(leaderboard_df, use_container_width=True, hide_index=True)

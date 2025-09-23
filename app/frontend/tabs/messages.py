"""訊息量統計（Messages 分頁）"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from common import CHART_TOOLTIPS, fetch_messages, info_badge

KEY_PREFIX = "messages_tab__"


def _fmt_int(x: float | int | None) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "—"
    try:
        return f"{int(round(float(x))):,}"
    except Exception:
        return "—"


def render_messages() -> None:
    """Render the message analysis tab（含趨勢 / 人均 / 20-60-20 / 排行榜）。"""
    data = fetch_messages() or {}

    trend_data = data.get("trend", []) or []
    distribution_data = data.get("distribution", []) or []
    leaderboard = data.get("leaderboard", []) or []

    if not trend_data and not distribution_data and not leaderboard:
        st.info("目前沒有訊息量相關資料。")
        return

    # =====================================================================
    # 1) 將 trend 轉為 DataFrame，並只取「工作日」做月平均/人均
    # =====================================================================
    trend_df = pd.DataFrame(trend_data) if isinstance(trend_data, list) else pd.DataFrame()
    if not trend_df.empty:
        trend_df = trend_df.copy()
        if "stat_date" in trend_df.columns:
            trend_df["stat_date"] = pd.to_datetime(trend_df["stat_date"], errors="coerce")
            trend_df = trend_df.dropna(subset=["stat_date"]).sort_values("stat_date")

        # 後端可能用 total_employees 或 total_installed，做個相容
        if "total_employees" not in trend_df.columns and "total_installed" in trend_df.columns:
            trend_df["total_employees"] = pd.to_numeric(trend_df["total_installed"], errors="coerce")

        # 僅保留一～五為工作日
        workday_df = trend_df.loc[trend_df["stat_date"].dt.weekday < 5].copy()
    else:
        workday_df = pd.DataFrame()

    show_workday_trend = not workday_df.empty
    show_per_capita = (
        show_workday_trend
        and "total_employees" in workday_df.columns
        and pd.to_numeric(workday_df["total_employees"], errors="coerce").fillna(0).gt(0).any()
    )

    # =====================================================================
    # 2) 工作日「月平均訊息數」
    # =====================================================================
    monthly_avg_df = pd.DataFrame()
    if show_workday_trend:
        monthly_source = workday_df.dropna(subset=["total_messages"]).copy()
        monthly_source["total_messages"] = pd.to_numeric(monthly_source["total_messages"], errors="coerce")
        monthly_source = monthly_source.dropna(subset=["total_messages"])
        if not monthly_source.empty:
            monthly_source["stat_month"] = monthly_source["stat_date"].dt.to_period("M")
            monthly_avg_df = (
                monthly_source.groupby("stat_month", as_index=False)
                .agg(total_messages=("total_messages", "sum"), workdays=("stat_date", "count"))
            )
            monthly_avg_df = monthly_avg_df[monthly_avg_df["workdays"] > 0]
            if not monthly_avg_df.empty:
                monthly_avg_df["avg_messages"] = monthly_avg_df["total_messages"] / monthly_avg_df["workdays"]
                monthly_avg_df["month_start"] = monthly_avg_df["stat_month"].dt.to_timestamp()
                monthly_avg_df["month_label"] = monthly_avg_df["stat_month"].astype(str)
                monthly_avg_df.sort_values("stat_month", inplace=True)

    # =====================================================================
    # 3) 工作日「月人均訊息數」
    # =====================================================================
    monthly_per_capita_df = pd.DataFrame()
    if show_per_capita:
        per_capita_source = workday_df.dropna(subset=["total_messages", "total_employees"]).copy()
        per_capita_source["total_messages"] = pd.to_numeric(per_capita_source["total_messages"], errors="coerce")
        per_capita_source["total_employees"] = pd.to_numeric(per_capita_source["total_employees"], errors="coerce")
        # 分母 0 剔除
        per_capita_source = per_capita_source[per_capita_source["total_employees"] > 0]
        if not per_capita_source.empty:
            per_capita_source["stat_month"] = per_capita_source["stat_date"].dt.to_period("M")
            monthly_per_capita_df = (
                per_capita_source.groupby("stat_month", as_index=False)
                .agg(
                    total_messages=("total_messages", "sum"),
                    total_employees=("total_employees", "sum"),
                    workdays=("stat_date", "count"),
                )
            )
            monthly_per_capita_df = monthly_per_capita_df[monthly_per_capita_df["total_employees"] > 0]
            if not monthly_per_capita_df.empty:
                monthly_per_capita_df["messages_per_employee"] = (
                    monthly_per_capita_df["total_messages"] / monthly_per_capita_df["total_employees"]
                )
                monthly_per_capita_df["avg_employees"] = (
                    monthly_per_capita_df["total_employees"] / monthly_per_capita_df["workdays"]
                )
                monthly_per_capita_df["month_start"] = monthly_per_capita_df["stat_month"].dt.to_timestamp()
                monthly_per_capita_df["month_label"] = monthly_per_capita_df["stat_month"].astype(str)
                monthly_per_capita_df.sort_values("stat_month", inplace=True)

    # =====================================================================
    # 4) 工作日平均訊息數（圖＋表）
    # =====================================================================
    if show_workday_trend:
        st.markdown(
            info_badge("工作日平均訊息數", CHART_TOOLTIPS.get("workday_messages"), font_size="18px"),
            unsafe_allow_html=True,
        )
        chart_col, table_col = st.columns((2, 1), gap="large")

        if monthly_avg_df.empty:
            with chart_col:
                st.info("目前沒有可用的工作日訊息資料。")
            with table_col:
                st.info("沒有資料可供列出。")
        else:
            with chart_col:
                customdata = monthly_avg_df[["month_label", "workdays", "total_messages"]].to_numpy()
                fig = go.Figure()
                fig.add_trace(
                    go.Bar(
                        x=monthly_avg_df["month_start"],
                        y=monthly_avg_df["avg_messages"],
                        name="平均訊息數",
                        customdata=customdata,
                        hovertemplate=(
                            "月份=%{customdata[0]}<br>"
                            "平均訊息數=%{y:,.2f} 則<br>"
                            "工作日數=%{customdata[1]:,.0f} 天<br>"
                            "訊息總數=%{customdata[2]:,.0f} 則<extra></extra>"
                        ),
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=monthly_avg_df["month_start"],
                        y=monthly_avg_df["avg_messages"],
                        mode="lines+markers",
                        name="趨勢線",
                        hoverinfo="skip",
                    )
                )
                fig.update_layout(
                    title=None,
                    xaxis_title="統計月份",
                    yaxis_title="平均訊息數 (則)",
                    legend_title_text=None,
                )
                fig.update_xaxes(dtick="M1", tickformat="%Y-%m")
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    config={
                        "modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"],
                        "displaylogo": False,
                    },
                )

            with table_col:
                table_df = monthly_avg_df[
                    ["month_label", "avg_messages", "workdays", "total_messages"]
                ].copy()
                table_df.rename(
                    columns={
                        "month_label": "月份",
                        "avg_messages": "平均訊息數 (則)",
                        "workdays": "工作日數 (天)",
                        "total_messages": "訊息總數 (則)",
                    },
                    inplace=True,
                )
                table_df["平均訊息數 (則)"] = table_df["平均訊息數 (則)"].map(lambda v: f"{v:,.2f}" if pd.notna(v) else "—")
                table_df["工作日數 (天)"] = table_df["工作日數 (天)"].map(lambda v: _fmt_int(v))
                table_df["訊息總數 (則)"] = table_df["訊息總數 (則)"].map(lambda v: _fmt_int(v))
                st.dataframe(table_df, use_container_width=True, hide_index=True)

    # =====================================================================
    # 5) 工作日人均訊息數（圖＋表）
    # =====================================================================
    if show_per_capita:
        st.markdown(
            info_badge("工作日人均訊息數", CHART_TOOLTIPS.get("per_capita_messages"), font_size="18px"),
            unsafe_allow_html=True,
        )
        chart_col, table_col = st.columns((2, 1), gap="large")

        if monthly_per_capita_df.empty:
            with chart_col:
                st.info("目前沒有足夠的資料計算人均訊息數。")
            with table_col:
                st.info("沒有資料可供列出。")
        else:
            with chart_col:
                customdata = monthly_per_capita_df[
                    ["month_label", "avg_employees", "workdays", "total_messages"]
                ].to_numpy()
                fig = go.Figure()
                fig.add_trace(
                    go.Bar(
                        x=monthly_per_capita_df["month_start"],
                        y=monthly_per_capita_df["messages_per_employee"],
                        name="人均訊息數",
                        customdata=customdata,
                        hovertemplate=(
                            "月份=%{customdata[0]}<br>"
                            "人均訊息數=%{y:,.2f} 則<br>"
                            "平均在職員工=%{customdata[1]:,.0f} 人<br>"
                            "工作日數=%{customdata[2]:,.0f} 天<br>"
                            "訊息總數=%{customdata[3]:,.0f} 則<extra></extra>"
                        ),
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=monthly_per_capita_df["month_start"],
                        y=monthly_per_capita_df["messages_per_employee"],
                        mode="lines+markers",
                        name="趨勢線",
                        hoverinfo="skip",
                    )
                )
                fig.update_layout(
                    title=None,
                    xaxis_title="統計月份",
                    yaxis_title="人均訊息數 (則)",
                    legend_title_text=None,
                )
                fig.update_xaxes(dtick="M1", tickformat="%Y-%m")
                fig.update_yaxes(tickformat=".2f")
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    config={
                        "modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"],
                        "displaylogo": False,
                    },
                )

            with table_col:
                table_df = monthly_per_capita_df[
                    ["month_label", "messages_per_employee", "avg_employees", "workdays", "total_messages"]
                ].copy()
                table_df.rename(
                    columns={
                        "month_label": "月份",
                        "messages_per_employee": "人均訊息數 (則)",
                        "avg_employees": "平均在職員工 (人)",
                        "workdays": "工作日數 (天)",
                        "total_messages": "訊息總數 (則)",
                    },
                    inplace=True,
                )
                table_df["人均訊息數 (則)"] = table_df["人均訊息數 (則)"].map(lambda v: f"{v:,.2f}" if pd.notna(v) else "—")
                table_df["平均在職員工 (人)"] = table_df["平均在職員工 (人)"].map(lambda v: _fmt_int(v))
                table_df["工作日數 (天)"] = table_df["工作日數 (天)"].map(lambda v: _fmt_int(v))
                table_df["訊息總數 (則)"] = table_df["訊息總數 (則)"].map(lambda v: _fmt_int(v))
                st.dataframe(table_df, use_container_width=True, hide_index=True)

    # =====================================================================
    # 6) 20 / 60 / 20 訊息分布（以月堆疊圖顯示）
    # =====================================================================
    if distribution_data:
        dist_df = pd.DataFrame(distribution_data)
        if not dist_df.empty and "stat_date" in dist_df.columns:
            dist_df = dist_df.copy()
            dist_df["stat_date"] = pd.to_datetime(dist_df["stat_date"], errors="coerce")
            dist_df = dist_df.dropna(subset=["stat_date"]).sort_values(["stat_date", "segment"])
        else:
            dist_df = pd.DataFrame()

        st.markdown(
            info_badge("20/60/20 訊息分布", CHART_TOOLTIPS.get("message_distribution"), font_size="18px"),
            unsafe_allow_html=True,
        )

        if dist_df.empty:
            st.info("目前沒有足夠的訊息分布資料。")
        else:
            # 取每日總訊息量，月彙總（若 trend 有提供）
            if not trend_df.empty and "total_messages" in trend_df.columns:
                totals_map = trend_df.set_index("stat_date")["total_messages"]
                dist_df["total_messages"] = dist_df["stat_date"].map(totals_map).fillna(0.0)
            else:
                dist_df["total_messages"] = 0.0

            # 以 daily share 還原 daily count，再彙總到月
            dist_df["message_share"] = pd.to_numeric(dist_df["message_share"], errors="coerce").fillna(0.0)
            dist_df["message_count"] = dist_df["message_share"] * dist_df["total_messages"]
            dist_df["stat_month"] = dist_df["stat_date"].dt.to_period("M")

            segment_order = ["前20%", "中間60%", "後20%"]
            monthly_counts = (
                dist_df.groupby(["stat_month", "segment"], as_index=False)["message_count"].sum()
            )
            daily_totals = (
                dist_df[["stat_month", "stat_date", "total_messages"]]
                .drop_duplicates(subset=["stat_date"])
                .groupby("stat_month", as_index=False)["total_messages"].sum()
                .rename(columns={"total_messages": "month_total_messages"})
            )
            monthly_distribution = monthly_counts.merge(daily_totals, on="stat_month", how="left")
            monthly_distribution = monthly_distribution[monthly_distribution["month_total_messages"] > 0]

            if monthly_distribution.empty:
                st.info("目前沒有足夠的訊息分布資料。")
            else:
                monthly_distribution["message_share"] = (
                    monthly_distribution["message_count"] / monthly_distribution["month_total_messages"]
                )
                monthly_distribution["month_label"] = monthly_distribution["stat_month"].dt.strftime("%Y-%m")
                monthly_distribution["segment"] = pd.Categorical(
                    monthly_distribution["segment"], categories=segment_order, ordered=True
                )
                monthly_distribution.sort_values(["stat_month", "segment"], inplace=True)

                fig = px.bar(
                    monthly_distribution,
                    x="month_label",
                    y="message_share",
                    color="segment",
                    custom_data=["message_count"],
                    category_orders={"segment": segment_order},
                    labels={"month_label": "月份", "message_share": "訊息佔比", "segment": "族群"},
                )
                fig.update_layout(
                    title=None,
                    xaxis_title="月份",
                    yaxis_title="訊息佔比 (%)",
                    barmode="stack",
                    legend_title_text="族群",
                )
                fig.update_yaxes(tickformat=".0%")
                fig.update_traces(
                    hovertemplate="月份=%{x}<br>%{fullData.name}占比=%{y:.2%}<br>訊息數=%{customdata[0]:,.0f} 則<extra></extra>"
                )
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    config={
                        "modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"],
                        "displaylogo": False,
                    },
                )

    # =====================================================================
    # 7) Top 10 使用者排行榜
    # =====================================================================
    if leaderboard:
        st.markdown(
            info_badge("Top 10 使用者", CHART_TOOLTIPS.get("message_leaderboard"), font_size="18px"),
            unsafe_allow_html=True,
        )
        df = pd.DataFrame(leaderboard) if isinstance(leaderboard, list) else pd.DataFrame()
        if df.empty:
            st.info("目前沒有排行榜資料。")
        else:
            rename = {
                "rank": "名次",
                "emp_no": "員工編號",
                "unit_id": "單位代碼",
                "unit_name": "單位名稱",
                "total_messages": "訊息數",
            }
            for c in ["total_messages"]:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors="coerce")

            show_cols = [c for c in ["rank", "emp_no", "unit_id", "unit_name", "total_messages"] if c in df.columns]
            df = df[show_cols].rename(columns=rename)
            if "訊息數" in df.columns:
                df["訊息數"] = df["訊息數"].map(_fmt_int)

            st.dataframe(df, use_container_width=True, hide_index=True)

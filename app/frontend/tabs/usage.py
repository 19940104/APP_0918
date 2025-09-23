"""
人員覆蓋率統計（Usage 分頁）

功能：
1) 全公司週使用率：月/季/年切換；左圖(柱＋線) / 右表
2) 各部門週使用率：選週；圖表類型切換(圓餅/長條)；左圖 / 右表
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from common import CHART_TOOLTIPS, fetch_usage, info_badge

KEY_PREFIX = "usage_tab__"


def render_usage() -> None:
    """Render the usage analysis tab with safe checks."""
    data = fetch_usage() or {}
    company = data.get("company", []) or []
    departments = data.get("departments", []) or []

    if not company and not departments:
        st.info("目前沒有使用率資料。")
        return

    cols = st.columns(2, gap="large")

    # =========================================================================
    # 全公司週使用率 (月/季/年切換 + 柱狀 + 折線)
    # =========================================================================
    if company:
        company_df = pd.DataFrame(company)
        if not company_df.empty:
            company_df = company_df.copy()

            # 時間欄位處理
            if "stat_date" in company_df.columns:
                company_df["stat_date"] = pd.to_datetime(company_df["stat_date"], errors="coerce")

            # 排序
            sort_keys = [c for c in ("iso_year", "iso_week", "stat_date") if c in company_df.columns]
            if sort_keys:
                company_df = company_df.sort_values(sort_keys).reset_index(drop=True)

            # 週次顯示欄
            if "week_label" in company_df.columns:
                company_df["week_display"] = company_df["week_label"].astype(str)
            elif "stat_date" in company_df.columns:
                company_df["week_display"] = company_df["stat_date"].dt.strftime("%G-W%V")
            else:
                company_df["week_display"] = company_df.index.to_series().add(1).map(lambda i: f"週次 {i}")

            # 期間欄位（供篩選）
            if "stat_date" in company_df.columns:
                company_df["stat_month"] = company_df["stat_date"].dt.to_period("M").astype(str)
                company_df["stat_quarter"] = company_df["stat_date"].dt.to_period("Q").astype(str)
                company_df["stat_year"] = company_df["stat_date"].dt.to_period("Y").astype(str)
            else:
                company_df["stat_month"] = pd.NA
                company_df["stat_quarter"] = pd.NA
                company_df["stat_year"] = pd.NA

            # 顯示文字
            if "usage_rate" in company_df.columns:
                company_df["usage_rate_display"] = company_df["usage_rate"].apply(
                    lambda v: f"{v:.1%}" if pd.notna(v) else "無資料"
                )

            with cols[0]:
                st.markdown(
                    info_badge("全公司週使用率", CHART_TOOLTIPS.get("company_usage"), font_size="18px"),
                    unsafe_allow_html=True,
                )

                # 篩選方式
                filter_mode = st.radio(
                    "篩選方式",
                    ["月", "季", "年"],
                    index=0,
                    horizontal=True,
                    key=f"{KEY_PREFIX}company_filter_mode",
                )

                # 建立選單
                if filter_mode == "月":
                    options = sorted(set(company_df["stat_month"].dropna().astype(str)), reverse=True)
                    selected = st.selectbox("選擇月份", options, key=f"{KEY_PREFIX}company_month")
                    mask = company_df["stat_month"].astype(str) == selected
                elif filter_mode == "季":
                    options = sorted(set(company_df["stat_quarter"].dropna().astype(str)), reverse=True)
                    selected = st.selectbox("選擇季度", options, key=f"{KEY_PREFIX}company_quarter")
                    mask = company_df["stat_quarter"].astype(str) == selected
                else:
                    options = sorted(set(company_df["stat_year"].dropna().astype(str)), reverse=True)
                    selected = st.selectbox("選擇年份", options, key=f"{KEY_PREFIX}company_year")
                    mask = company_df["stat_year"].astype(str) == selected

                display_df = company_df.loc[mask].copy() if options else pd.DataFrame()
                if display_df.empty:
                    st.info(f"所選{filter_mode}沒有週使用率資料")
                else:
                    # dropna 防呆
                    display_df = display_df.dropna(subset=["usage_rate"])
                    if display_df.empty:
                        st.info("⚠️ 沒有有效的使用率資料")
                    else:
                        # 柱狀圖 + 折線圖
                        fig_bar = px.bar(
                            display_df,
                            x="week_display",
                            y="usage_rate",
                            text="usage_rate_display",
                            hover_data={
                                "usage_rate_display": True,
                                "active_users": True,
                                "total_users": True,
                            },
                            labels={"week_display": "ISO 週次", "usage_rate": "使用率"},
                        )
                        fig_bar.update_traces(textposition="outside")

                        fig_line = px.line(
                            display_df,
                            x="week_display",
                            y="usage_rate",
                            markers=True,
                        )
                        for tr in fig_line.data:
                            fig_bar.add_trace(tr)

                        fig_bar.update_layout(title=None, xaxis_title="ISO 週次", yaxis_title="使用率 (%)")
                        fig_bar.update_yaxes(tickformat=".0%")

                        chart_col, table_col = st.columns([2, 1], gap="medium")
                        with chart_col:
                            st.plotly_chart(
                                fig_bar,
                                use_container_width=True,
                                config={
                                    "modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"],
                                    "displaylogo": False,
                                },
                            )
                        with table_col:
                            summary_cols = [c for c in ["week_display", "active_users", "total_users", "usage_rate_display"]
                                            if c in display_df.columns]
                            if summary_cols:
                                summary_df = display_df[summary_cols].rename(
                                    columns={
                                        "week_display": "週次",
                                        "active_users": "本週使用人數",
                                        "total_users": "全公司總員工數",
                                        "usage_rate_display": "使用率",
                                    }
                                )
                                st.dataframe(summary_df, use_container_width=True, hide_index=True)
                            else:
                                st.info("⚠️ 無表格資料")
        else:
            with cols[0]:
                st.info("全公司週使用率沒有資料。")

    # =========================================================================
    # 各部門週使用率 
    # =========================================================================
    dept_df = pd.DataFrame(departments) if isinstance(departments, list) else pd.DataFrame()
    if not dept_df.empty:
        dept_df = dept_df.copy()
        if "stat_date" in dept_df.columns:
            dept_df["stat_date"] = pd.to_datetime(dept_df["stat_date"], errors="coerce")

        # 數值欄位轉型
        for col in ["usage_rate", "active_users", "total_users", "iso_year", "iso_week"]:
            if col in dept_df.columns:
                dept_df[col] = pd.to_numeric(dept_df[col], errors="coerce")

        # 單位標籤
        def _unit_label(row: pd.Series) -> str:
            unit_id = str(row.get("unit_id") or "").strip()
            unit_name = str(row.get("unit_name") or "").strip()
            return " ".join(p for p in [unit_id, unit_name] if p) or "未命名單位"

        dept_df["unit_label"] = dept_df.apply(_unit_label, axis=1)

        # 週次顯示
        if "week_label" in dept_df.columns:
            dept_df["week_display"] = dept_df["week_label"].astype(str)
        elif "stat_date" in dept_df.columns:
            dept_df["week_display"] = dept_df["stat_date"].dt.strftime("%G-W%V")
        else:
            dept_df["week_display"] = "未知週次"

        week_options = sorted(set(dept_df["week_display"].dropna().astype(str)), reverse=True)

        with cols[1]:
            st.markdown(
                info_badge("各部門週使用率", CHART_TOOLTIPS.get("department_usage"), font_size="18px"),
                unsafe_allow_html=True,
            )

            if week_options:
                selected_week = st.selectbox(
                    "選擇週次",
                    options=week_options,
                    index=0,
                    key=f"{KEY_PREFIX}dept_week",
                )
                week_df = dept_df.loc[dept_df["week_display"] == selected_week].copy()

                if not week_df.empty:
                    chart_type = st.radio(
                        "圖表類型",
                        ("圓餅圖", "長條圖"),
                        horizontal=True,
                        key=f"{KEY_PREFIX}dept_chart_type",
                    )
                    chart_df = week_df.dropna(subset=["usage_rate"]).copy()
                    chart_df["usage_rate_pct"] = chart_df["usage_rate"] * 100.0
                    chart_df["usage_rate_label"] = chart_df["usage_rate_pct"].map(
                        lambda v: f"{v:.2f}%" if pd.notna(v) else "無資料"
                    )

                    if not chart_df.empty:
                        chart_labels = {
                            "unit_label": "單位",
                            "usage_rate_pct": "使用率 (%)",
                            "usage_rate_label": "使用率",
                            "active_users": "使用人數",
                            "total_users": "總人數",
                        }
                        hover_data = {
                            k: True for k in ["usage_rate_label", "active_users", "total_users"] if k in chart_df.columns
                        }

                        # 圖表
                        if chart_type == "圓餅圖":
                            fig = px.pie(
                                chart_df,
                                names="unit_label",
                                values="usage_rate_pct",
                                hover_data=hover_data,
                                labels=chart_labels,
                            )
                            fig.update_traces(texttemplate="%{label}<br>%{value:.2f}%", textposition="inside")
                            fig.update_layout(legend_title_text="單位")
                        else:
                            chart_df = chart_df.sort_values("usage_rate_pct", ascending=False)
                            fig = px.bar(
                                chart_df,
                                x="unit_label",
                                y="usage_rate_pct",
                                text="usage_rate_label",
                                hover_data=hover_data,
                                labels=chart_labels,
                            )
                            fig.update_traces(textposition="outside")
                            fig.update_layout(
                                xaxis_title="單位",
                                yaxis_title="使用率 (%)",
                                xaxis_tickangle=-30,
                            )

                        chart_col, table_col = st.columns([2, 1], gap="medium")
                        with chart_col:
                            st.plotly_chart(
                                fig,
                                use_container_width=True,
                                config={
                                    "modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"],
                                    "displaylogo": False,
                                },
                            )
                        with table_col:
                            table_df = week_df.copy()
                            table_df["usage_rate_pct"] = table_df["usage_rate"] * 100.0
                            table_df["usage_rate_label"] = table_df["usage_rate_pct"].map(
                                lambda v: f"{v:.2f}%" if pd.notna(v) else "無資料"
                            )
                            for c in ["active_users", "total_users"]:
                                if c in table_df.columns:
                                    table_df[c] = pd.to_numeric(table_df[c], errors="coerce").astype("Int64")

                            display_cols = []
                            rename_map = {}
                            if "unit_id" in table_df.columns:
                                display_cols.append("unit_id")
                                rename_map["unit_id"] = "處級代碼"
                            if "unit_name" in table_df.columns:
                                display_cols.append("unit_name")
                                rename_map["unit_name"] = "處級名稱"
                            if "total_users" in table_df.columns:
                                display_cols.append("total_users")
                                rename_map["total_users"] = "總人數"
                            if "active_users" in table_df.columns:
                                display_cols.append("active_users")
                                rename_map["active_users"] = "使用人數"
                            if "usage_rate_label" in table_df.columns:
                                display_cols.append("usage_rate_label")
                                rename_map["usage_rate_label"] = "使用率百分比"

                            if display_cols:
                                st.dataframe(
                                    table_df[display_cols].rename(columns=rename_map),
                                    use_container_width=True,
                                    hide_index=True,
                                )
                            else:
                                st.info("⚠️ 無表格資料")
                    else:
                        st.info("⚠️ 所選週次缺少使用率資料")
                else:
                    st.info("所選週次沒有部門使用率資料")
            else:
                st.info("部門資料缺少週次資訊，無法顯示週別使用狀況")
    else:
        with cols[1]:
            st.info("各部門週使用率沒有資料。")

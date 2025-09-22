"""
Usage Analytics Tab (安全版)。

此模組負責繪製「使用率分析」分頁，包含：
1. 全公司週使用率
   - 提供月份篩選
   - 圖表 (左) + 資料表 (右)，左右擺放
2. 各部門週使用率
   - 提供週次篩選
   - 支援圖表類型切換 (圓餅圖 / 長條圖)
   - 圖表 (左) + 資料表 (右)，左右擺放

改良重點：
- 繪圖前會 dropna，避免 NaN 導致 Plotly schema 壞掉。
- 每次繪製前先檢查 DataFrame 是否為空，空的話顯示提示訊息，不丟給前端。
- 所有 Streamlit widget key 都加上前綴，避免衝突。

數據來源：
- API: /usage
- 回傳格式: { "company": [...], "departments": [...] }

主要函式：
- render_usage(): 主渲染入口
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from common import CHART_TOOLTIPS, fetch, info_badge


def render_usage() -> None:
    """Render the usage analysis tab with safe checks."""
    try:
        data = fetch("usage")
    except Exception as exc:  # pragma: no cover - Streamlit handles display
        st.error(f"取得使用率資料失敗：{exc}")
        return

    company = data.get("company", [])
    departments = data.get("departments", [])

    if not company and not departments:
        st.info("目前沒有使用率資料。")
        return

    cols = st.columns(2, gap="large")

    # =========================================================================
    # 全公司週使用率
    # =========================================================================
    if company:
        company_df = pd.DataFrame(company)
        if not company_df.empty:
            company_df = company_df.copy()
            if "stat_date" in company_df.columns:
                company_df["stat_date"] = pd.to_datetime(company_df["stat_date"], errors="coerce")

            # 排序用 keys
            sort_keys = [col for col in ("iso_year", "iso_week", "stat_date") if col in company_df.columns]
            if sort_keys:
                company_df = company_df.sort_values(sort_keys)

            # 顯示週次
            if "week_label" in company_df.columns:
                company_df["week_display"] = company_df["week_label"].copy()
            else:
                company_df["week_display"] = pd.Series([None] * len(company_df))

            if "stat_date" in company_df.columns:
                company_df["week_display"] = company_df["week_display"].fillna(
                    company_df["stat_date"].dt.strftime("%G-W%V")
                )
                company_df["stat_month"] = company_df["stat_date"].dt.to_period("M")
            else:
                company_df["stat_month"] = pd.Series([pd.NaT] * len(company_df))

            company_df["week_display"] = company_df["week_display"].fillna(
                company_df.index.to_series().add(1).map(lambda idx: f"週次 {idx}")
            )
            company_df["week_display"] = company_df["week_display"].astype(str)
            company_df["usage_rate_display"] = company_df["usage_rate"].apply(
                lambda v: f"{v:.1%}" if pd.notna(v) else "無資料"
            )

            # 月份篩選選項
            month_options: list[str] = []
            if "stat_month" in company_df.columns:
                unique_months = company_df["stat_month"].dropna().unique()
                if len(unique_months) > 0:
                    month_options = sorted([str(month) for month in unique_months], reverse=True)

            with cols[0]:
                st.markdown(
                    info_badge("全公司週使用率", CHART_TOOLTIPS.get("company_usage"), font_size="18px"),
                    unsafe_allow_html=True,
                )
                display_df = company_df
                if month_options:
                    selected_month = st.selectbox(
                        "選擇月份檢視週使用率",
                        month_options,
                        index=0,
                        key="company_usage_month_select",
                    )
                    display_df = company_df[company_df["stat_month"].astype(str) == selected_month]

                if not display_df.empty:
                    display_df = display_df.dropna(subset=["usage_rate"])
                    if display_df.empty:
                        st.info("⚠️ 沒有有效的使用率資料")
                    else:
                        fig = px.bar(
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
                        fig.update_traces(textposition="outside")
                        fig.update_layout(title=None, xaxis_title="ISO 週次", yaxis_title="使用率 (%)")
                        fig.update_yaxes(tickformat=".0%")

                        # ---- 左右擺放 (圖表 | 表格) ----
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
                            summary_cols = [
                                col for col in ["week_display", "active_users", "total_users", "usage_rate_display"]
                                if col in display_df.columns
                            ]
                            if summary_cols:
                                summary_df = display_df[summary_cols].rename(
                                    columns={
                                        "week_display": "週次",
                                        "active_users": "本週使用人數",
                                        "total_users": "全公司總員工數",
                                        "usage_rate_display": "使用率",
                                    }
                                )
                                if not summary_df.empty:
                                    st.dataframe(summary_df, use_container_width=True, hide_index=True)
                                else:
                                    st.info("⚠️ 無表格資料")
                else:
                    st.info("所選月份沒有週使用率資料")
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

        for col in ["usage_rate", "active_users", "total_users", "iso_year", "iso_week"]:
            if col in dept_df.columns:
                dept_df[col] = pd.to_numeric(dept_df[col], errors="coerce")

        # 單位標籤
        def _build_unit_label(row: pd.Series) -> str:
            unit_id = str(row.get("unit_id") or "").strip()
            unit_name = str(row.get("unit_name") or "").strip()
            return " ".join(p for p in [unit_id, unit_name] if p) or "未命名單位"

        dept_df["unit_label"] = dept_df.apply(_build_unit_label, axis=1)

        # 週次顯示
        if "stat_date" in dept_df.columns:
            dept_df["week_display"] = dept_df["stat_date"].dt.strftime("%G-W%V")
        else:
            dept_df["week_display"] = "未知週次"

        week_options = dept_df["week_display"].dropna().unique().tolist()
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
                    key="department_usage_week_select",
                )
                week_df = dept_df.loc[dept_df["week_display"] == selected_week].copy()

                if not week_df.empty:
                    chart_type = st.radio(
                        "圖表類型",
                        ("圓餅圖", "長條圖"),
                        horizontal=True,
                        key="department_usage_chart_type_radio",
                    )
                    chart_df = week_df.dropna(subset=["usage_rate"]).copy()
                    chart_df["usage_rate_pct"] = chart_df["usage_rate"] * 100
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
                            key: True
                            for key in ["usage_rate_label", "active_users", "total_users"]
                            if key in chart_df.columns
                        }

                        # 繪製圖表
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

                        # ---- 左右擺放 (圖表 | 表格) ----
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
                            if not week_df.empty:
                                table_df = week_df.copy()
                                table_df["usage_rate_pct"] = table_df["usage_rate"] * 100
                                table_df["usage_rate_label"] = table_df["usage_rate_pct"].map(
                                    lambda v: f"{v:.2f}%" if pd.notna(v) else "無資料"
                                )
                                for col in ["active_users", "total_users"]:
                                    if col in table_df.columns:
                                        table_df[col] = (
                                            pd.to_numeric(table_df[col], errors="coerce").astype("Int64")
                                        )
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

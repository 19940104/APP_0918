from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from app.frontend.dashboard_shared import CHART_TOOLTIPS, fetch, info_badge


def render_usage() -> None:
    """呈現使用率分析。"""
    try:
        data = fetch("usage")
    except Exception as e:  # pragma: no cover - defensive UI message
        st.error(f"取得使用率資料失敗：{e}")
        return

    company = data.get("company", [])
    departments = data.get("departments", [])

    if not company and not departments:
        st.info("目前沒有使用率資料。")
        return

    cols = st.columns(2, gap="large")

    # 全公司週使用率
    if company:
        company_df = pd.DataFrame(company)
        if company_df.empty:
            with cols[0]:
                st.info("全公司週使用率沒有資料。")
        else:
            company_df = company_df.copy()
            if "stat_date" in company_df.columns:
                company_df["stat_date"] = pd.to_datetime(company_df["stat_date"], errors="coerce")
            sort_keys = [col for col in ("iso_year", "iso_week", "stat_date") if col in company_df.columns]
            if sort_keys:
                company_df = company_df.sort_values(sort_keys)
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
                        key="company_usage_month",
                    )
                    display_df = company_df[company_df["stat_month"].astype(str) == selected_month]
                if display_df.empty:
                    st.info("所選月份沒有週使用率資料。")
                else:
                    display_df = display_df.sort_values(sort_keys) if sort_keys else display_df
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

                    st.plotly_chart(
                        fig,
                        use_container_width=True,
                        config={"modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"], "displaylogo": False},
                    )

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
                        st.dataframe(summary_df, use_container_width=True)
    # 各部門週使用率 + 月度排行
    dept_df = pd.DataFrame(departments) if isinstance(departments, list) else pd.DataFrame()

    if dept_df.empty:
        with cols[1]:
            st.info("各部門週使用率沒有資料。")
    else:
        dept_df = dept_df.copy()
        if "stat_date" in dept_df.columns:
            dept_df["stat_date"] = pd.to_datetime(dept_df["stat_date"], errors="coerce")
        for col in ["usage_rate", "active_users", "total_users", "iso_year", "iso_week"]:
            if col in dept_df.columns:
                dept_df[col] = pd.to_numeric(dept_df[col], errors="coerce")

        def _build_unit_label(row: pd.Series) -> str:
            unit_id = row.get("unit_id")
            unit_name = row.get("unit_name")
            parts: list[str] = []
            if isinstance(unit_id, str) and unit_id.strip():
                parts.append(unit_id.strip())
            elif pd.notna(unit_id):
                parts.append(str(unit_id))
            if isinstance(unit_name, str) and unit_name.strip():
                parts.append(unit_name.strip())
            elif pd.notna(unit_name):
                parts.append(str(unit_name))
            return " ".join(parts) if parts else "未命名單位"

        dept_df["unit_label"] = dept_df.apply(_build_unit_label, axis=1)

        def _derive_iso_tuple(row: pd.Series) -> tuple[int, int] | None:
            year = row.get("iso_year")
            week = row.get("iso_week")
            try:
                if pd.notna(year) and pd.notna(week):
                    return int(year), int(week)
            except (TypeError, ValueError):
                pass
            stat_date = row.get("stat_date")
            if isinstance(stat_date, pd.Timestamp) and not pd.isna(stat_date):
                iso = stat_date.isocalendar()
                return int(iso.year), int(iso.week)
            return None

        dept_df["iso_tuple"] = dept_df.apply(_derive_iso_tuple, axis=1)

        def _make_week_display(row: pd.Series) -> str:
            label = row.get("week_label")
            if isinstance(label, str) and label.strip():
                return label.strip()
            iso_tuple = row.get("iso_tuple")
            if isinstance(iso_tuple, tuple):
                year, week = iso_tuple
                return f"{year}-W{week:02d}"
            stat_date = row.get("stat_date")
            if isinstance(stat_date, pd.Timestamp) and not pd.isna(stat_date):
                return stat_date.strftime("%G-W%V")
            return "未知週次"

        dept_df["week_display"] = dept_df.apply(_make_week_display, axis=1)

        def _make_week_key(row: pd.Series) -> str:
            iso_tuple = row.get("iso_tuple")
            if isinstance(iso_tuple, tuple):
                year, week = iso_tuple
                return f"{year:04d}-W{week:02d}"
            display = row.get("week_display")
            if isinstance(display, str) and display.strip():
                return display
            stat_date = row.get("stat_date")
            if isinstance(stat_date, pd.Timestamp) and not pd.isna(stat_date):
                iso = stat_date.isocalendar()
                return f"{int(iso.year):04d}-W{int(iso.week):02d}"
            return f"week-{row.name}"

        dept_df["week_key"] = dept_df.apply(_make_week_key, axis=1)
        dept_df["week_sort"] = dept_df["iso_tuple"].apply(
            lambda iso_val: iso_val[0] * 100 + iso_val[1] if isinstance(iso_val, tuple) else float("nan")
        )
        if "stat_date" in dept_df.columns:
            missing_week_sort_mask = dept_df["week_sort"].isna()
            if missing_week_sort_mask.any():
                ordinal_values = pd.to_numeric(
                    dept_df.loc[missing_week_sort_mask, "stat_date"].map(
                        lambda d: d.toordinal()
                        if isinstance(d, pd.Timestamp) and not pd.isna(d)
                        else float("nan")
                    ),
                    errors="coerce",
                )
                dept_df.loc[missing_week_sort_mask, "week_sort"] = ordinal_values

        week_options_df = (
            dept_df[["week_key", "week_display", "week_sort"]]
            .drop_duplicates()
            .sort_values(by=["week_sort", "week_display"], ascending=[False, True], na_position="last")
        )
        week_records = week_options_df.to_dict("records")
        week_labels = {rec["week_key"]: rec.get("week_display") or rec["week_key"] for rec in week_records}

        with cols[1]:
            st.markdown(
                info_badge("各部門週使用率", CHART_TOOLTIPS.get("department_usage"), font_size="18px"),
                unsafe_allow_html=True,
            )

            if not week_records:
                st.info("部門資料缺少週次資訊，無法顯示週別使用狀況。")
            else:
                default_index = 0
                selected_week = st.selectbox(
                    "選擇週次",
                    options=[rec["week_key"] for rec in week_records],
                    index=default_index,
                    key="department_usage_week",
                    format_func=lambda key: week_labels.get(key, key),
                )

                week_df = dept_df.loc[dept_df["week_key"] == selected_week].copy()
                if week_df.empty:
                    st.info("所選週次沒有部門使用率資料。")
                else:
                    chart_type = st.radio(
                        "圖表類型",
                        ("圓餅圖", "長條圖"),
                        horizontal=True,
                        key="department_usage_chart_type",
                    )

                    chart_df = week_df.dropna(subset=["usage_rate"]).copy()
                    chart_df["usage_rate_pct"] = chart_df["usage_rate"] * 100
                    chart_df["usage_rate_label"] = chart_df["usage_rate_pct"].map(
                        lambda v: f"{v:.2f}%" if pd.notna(v) else "無資料"
                    )

                    if chart_df.empty:
                        st.info("所選週次缺少啟用率資料，無法繪製圖表。")
                    else:
                        chart_labels = {
                            "unit_label": "單位",
                            "usage_rate_pct": "啟用率 (%)",
                            "usage_rate_label": "啟用率",
                            "active_users": "使用人數",
                            "total_users": "總人數",
                        }

                        hover_data = {
                            key: True
                            for key in ["usage_rate_label", "active_users", "total_users"]
                            if key in chart_df.columns
                        }

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
                                yaxis_title="啟用率 (%)",
                                xaxis_tickangle=-30,
                            )

                        st.plotly_chart(
                            fig,
                            use_container_width=True,
                            config={"modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"], "displaylogo": False},
                        )

                    st.caption(f"週次：{week_labels.get(selected_week, selected_week)}")

                    table_df = week_df.copy()
                    if "usage_rate" in table_df.columns:
                        table_df["usage_rate_pct"] = table_df["usage_rate"] * 100
                        table_df["usage_rate_label"] = table_df["usage_rate_pct"].map(
                            lambda v: f"{v:.2f}%" if pd.notna(v) else "無資料"
                        )
                    for col in ["active_users", "total_users"]:
                        if col in table_df.columns:
                            table_df[col] = pd.to_numeric(table_df[col], errors="coerce").astype("Int64")
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
                        rename_map["usage_rate_label"] = "啟用率百分比"

                    if display_cols:
                        table_df = table_df.sort_values("usage_rate", ascending=False, na_position="last")
                        st.dataframe(
                            table_df[display_cols].rename(columns=rename_map),
                            use_container_width=True,
                            hide_index=True,
                        )

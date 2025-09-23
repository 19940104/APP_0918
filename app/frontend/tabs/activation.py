"""人員啟用率與留存率（Activation/Retention 分頁）"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from common import CHART_TOOLTIPS, fetch, info_badge

KEY_PREFIX = "activation_tab__"


# ============================================================================
# 工具：安全建立 DataFrame 與共通清理
# ============================================================================
def _safe_df(records) -> pd.DataFrame:
    if isinstance(records, list) and records:
        return pd.DataFrame(records)
    return pd.DataFrame()


def _prep_month_df(df: pd.DataFrame, value_col: str, count_col: str | None = None) -> pd.DataFrame:
    """整理月資料：時間欄位、比率欄位型別、部門欄位。"""
    if df.empty:
        return df
    out = df.copy()
    if "stat_month" in out.columns:
        out["stat_month"] = pd.to_datetime(out["stat_month"], errors="coerce")
        out = out.dropna(subset=["stat_month"]).sort_values("stat_month")
    if value_col in out.columns:
        out[value_col] = pd.to_numeric(out[value_col], errors="coerce")
    if count_col and count_col in out.columns:
        out[count_col] = pd.to_numeric(out[count_col], errors="coerce")
    # 欄位補齊
    if "unit_id" not in out.columns:
        out["unit_id"] = None
    if "unit_name" not in out.columns:
        out["unit_name"] = None
    # 月/季欄位
    out["month_label"] = out["stat_month"].dt.to_period("M").astype(str)
    out["quarter"] = out["stat_month"].dt.to_period("Q")
    out["quarter_label"] = out["quarter"].astype(str)
    return out


def _aggregate_quarter(df: pd.DataFrame, value_col: str, count_col: str | None, scope: str) -> pd.DataFrame:
    """把月資料彙總成季資料。
    比率欄位的季值以「加權平均」(若有分母可加權；否則使用簡單平均）處理。"""
    if df.empty:
        return df

    if scope == "全公司":
        # 只留 company 列（unit_id 為 None 或 unit_name == 全公司）
        base = df[(df["unit_id"].isna()) | (df["unit_name"] == "全公司")].copy()
    else:
        # 各部門：去除公司列
        base = df[~df["unit_id"].isna()].copy()

    if base.empty:
        return base

    if count_col and count_col in base.columns:
        # 有分母，用加權平均
        grp = (
            base.groupby(["quarter", "unit_id", "unit_name"], as_index=False)
            .apply(lambda g: pd.Series({
                value_col: (g[value_col] * g[count_col]).sum() / g[count_col].replace({0: pd.NA}).sum(),
                count_col: g[count_col].sum(),
                "months": g["stat_month"].nunique(),
            }))
            .reset_index(drop=True)
        )
    else:
        # 無分母，採簡單平均
        grp = (
            base.groupby(["quarter", "unit_id", "unit_name"], as_index=False)
            .agg(**{
                value_col: (value_col, "mean"),
                "months": ("stat_month", "nunique"),
            })
        )
    grp = grp.dropna(subset=[value_col])
    grp["stat_month"] = grp["quarter"].dt.to_timestamp()
    grp["quarter_label"] = grp["quarter"].astype(str)
    return grp


def _filter_scope(df: pd.DataFrame, scope: str) -> pd.DataFrame:
    if df.empty:
        return df
    if scope == "全公司":
        return df[(df["unit_id"].isna()) | (df["unit_name"] == "全公司")].copy()
    return df[~df["unit_id"].isna()].copy()


def _chart(df: pd.DataFrame, x: str, y: str, kind: str, *, y_as_percent: bool = True, title_x: str = "", title_y: str = ""):
    """簡化：折線/長條切換。"""
    if kind == "長條圖":
        fig = px.bar(df, x=x, y=y)
        fig.update_traces(texttemplate="%{y:.1%}" if y_as_percent else None, textposition="outside")
    else:
        fig = px.line(df, x=x, y=y, markers=True)
    fig.update_layout(title=None, xaxis_title=title_x or x, yaxis_title=title_y or y)
    if y_as_percent:
        fig.update_yaxes(tickformat=".0%")
    return fig


def _right_table(df: pd.DataFrame, cols_map: dict[str, str]) -> None:
    """右側表格渲染：欄位改名 + 比率格式化。"""
    if df.empty:
        st.info("沒有資料可供列出。")
        return
    table = df[list(cols_map.keys())].rename(columns=cols_map).copy()
    # 自動把「率」結尾欄位轉為百分比字串
    for c in list(cols_map.values()):
        if c.endswith("率") or c.endswith("比"):
            if c in table.columns:
                table[c] = table[c].map(lambda v: f"{v:.2%}" if pd.notna(v) else "—")
    st.dataframe(table, use_container_width=True, hide_index=True)


# ============================================================================
# 主畫面：啟用率 + 留存率（左右並排；各自支援 月/季 + 折線/長條 + 下拉）
# ============================================================================
def render_activation() -> None:
    """主入口：渲染「當月啟用率 / 當月留存率」"""
    try:
        data = fetch("activation")
    except Exception as exc:  # pragma: no cover
        st.error(f"取得啟用/留存資料失敗：{exc}")
        return

    act_raw = _safe_df(data.get("activation"))
    ret_raw = _safe_df(data.get("retention"))

    # 整理欄位
    act_df = _prep_month_df(act_raw, value_col="activation_rate", count_col="total_employees")
    ret_df = _prep_month_df(ret_raw, value_col="retention_rate", count_col=None)

    if act_df.empty and ret_df.empty:
        st.info("目前沒有啟用與留存資料。")
        return

    cols = st.columns(2, gap="large")

    # ==========================
    # 左：當月啟用率
    # ==========================
    with cols[0]:
        st.markdown(info_badge("當月啟用率", CHART_TOOLTIPS.get("activation"), font_size="18px"),
                    unsafe_allow_html=True)

        scope = st.radio("範圍", ("全公司", "各部門"), horizontal=True, key=f"{KEY_PREFIX}scope_act")
        period = st.radio("查看", ("月查看", "季查看"), horizontal=True, key=f"{KEY_PREFIX}period_act")
        chart_type = st.radio("圖表類型", ("折線圖", "長條圖"), horizontal=True, key=f"{KEY_PREFIX}chart_act")

        if period == "月查看":
            view = _filter_scope(act_df, scope).dropna(subset=["activation_rate"]).copy()
            if scope == "各部門" and not view.empty:
                # 月份下拉
                month_opts = view["month_label"].unique().tolist()
                sel = st.selectbox("選擇月份", ["全部"] + month_opts[::-1], key=f"{KEY_PREFIX}month_act")
                if sel != "全部":
                    view = view[view["month_label"] == sel]
            x_col = "stat_month"
            fig = _chart(
                view,
                x=x_col,
                y="activation_rate",
                kind=chart_type,
                y_as_percent=True,
                title_x="統計月份",
                title_y="啟用率 (%)",
            )
            chart_col, table_col = st.columns((2, 1), gap="large")
            with chart_col:
                st.plotly_chart(fig, use_container_width=True,
                                config={"modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"], "displaylogo": False})
            with table_col:
                if scope == "全公司":
                    tbl = view[(view["unit_id"].isna()) | (view["unit_name"] == "全公司")].copy()
                    _right_table(tbl.sort_values("stat_month", ascending=False),
                                 {"month_label": "月份", "activation_rate": "啟用率",
                                  "activated_users": "啟用人數", "total_employees": "總人數"})
                else:
                    tbl = view[~view["unit_id"].isna()].copy()
                    _right_table(tbl.sort_values(["stat_month", "unit_id"], ascending=[False, True]),
                                 {"month_label": "月份", "unit_id": "處級代碼", "unit_name": "處級名稱",
                                  "activated_users": "啟用人數", "total_employees": "總人數",
                                  "activation_rate": "啟用率"})

        else:  # 季查看
            qdf = _aggregate_quarter(act_df, "activation_rate", "total_employees", scope).dropna(subset=["activation_rate"])
            if scope == "全公司":
                # 只留公司列
                qdf = qdf[(qdf["unit_id"].isna()) | (qdf["unit_name"] == "全公司")]
            else:
                qdf = qdf[~qdf["unit_id"].isna()]
                # 季度下拉
                q_opts = qdf["quarter_label"].unique().tolist()
                sel_q = st.selectbox("選擇季度", ["全部"] + q_opts[::-1], key=f"{KEY_PREFIX}quarter_act")
                if sel_q != "全部":
                    qdf = qdf[qdf["quarter_label"] == sel_q]

            fig = _chart(
                qdf,
                x="stat_month",
                y="activation_rate",
                kind=chart_type,
                y_as_percent=True,
                title_x="統計季度",
                title_y="啟用率 (%)",
            )
            chart_col, table_col = st.columns((2, 1), gap="large")
            with chart_col:
                st.plotly_chart(fig, use_container_width=True,
                                config={"modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"], "displaylogo": False})
            with table_col:
                if scope == "全公司":
                    _right_table(qdf.sort_values("stat_month", ascending=False),
                                 {"quarter_label": "季度", "activation_rate": "啟用率",
                                  "months": "統計月份數", "total_employees": "加權分母(總人數)" if "total_employees" in qdf.columns else "統計月份數"})
                else:
                    _right_table(qdf.sort_values(["stat_month", "unit_id"], ascending=[False, True]),
                                 {"quarter_label": "季度", "unit_id": "處級代碼", "unit_name": "處級名稱",
                                  "months": "統計月份數", "activation_rate": "啟用率"})

    # ==========================
    # 右：當月留存率
    # ==========================
    with cols[1]:
        st.markdown(info_badge("當月留存率", CHART_TOOLTIPS.get("retention"), font_size="18px"),
                    unsafe_allow_html=True)

        scope2 = st.radio("範圍", ("全公司", "各部門"), horizontal=True, key=f"{KEY_PREFIX}scope_ret")
        period2 = st.radio("查看", ("月查看", "季查看"), horizontal=True, key=f"{KEY_PREFIX}period_ret")
        chart_type2 = st.radio("圖表類型", ("折線圖", "長條圖"), horizontal=True, key=f"{KEY_PREFIX}chart_ret")

        if period2 == "月查看":
            view2 = _filter_scope(ret_df, scope2).dropna(subset=["retention_rate"]).copy()
            if scope2 == "各部門" and not view2.empty:
                month_opts2 = view2["month_label"].unique().tolist()
                sel2 = st.selectbox("選擇月份", ["全部"] + month_opts2[::-1], key=f"{KEY_PREFIX}month_ret")
                if sel2 != "全部":
                    view2 = view2[view2["month_label"] == sel2]

            fig2 = _chart(
                view2,
                x="stat_month",
                y="retention_rate",
                kind=chart_type2,
                y_as_percent=True,
                title_x="統計月份",
                title_y="留存率 (%)",
            )
            chart_col2, table_col2 = st.columns((2, 1), gap="large")
            with chart_col2:
                st.plotly_chart(fig2, use_container_width=True,
                                config={"modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"], "displaylogo": False})
            with table_col2:
                if scope2 == "全公司":
                    tbl2 = view2[(view2["unit_id"].isna()) | (view2["unit_name"] == "全公司")].copy()
                    _right_table(tbl2.sort_values("stat_month", ascending=False),
                                 {"month_label": "月份", "retention_rate": "留存率",
                                  "retained_users": "留存人數"})
                else:
                    tbl2 = view2[~view2["unit_id"].isna()].copy()
                    _right_table(tbl2.sort_values(["stat_month", "unit_id"], ascending=[False, True]),
                                 {"month_label": "月份", "unit_id": "處級代碼", "unit_name": "處級名稱",
                                  "retained_users": "留存人數", "retention_rate": "留存率"})

        else:
            qdf2 = _aggregate_quarter(ret_df, "retention_rate", None, scope2).dropna(subset=["retention_rate"])
            if scope2 == "全公司":
                qdf2 = qdf2[(qdf2["unit_id"].isna()) | (qdf2["unit_name"] == "全公司")]
            else:
                qdf2 = qdf2[~qdf2["unit_id"].isna()]
                q_opts2 = qdf2["quarter_label"].unique().tolist()
                sel_q2 = st.selectbox("選擇季度", ["全部"] + q_opts2[::-1], key=f"{KEY_PREFIX}quarter_ret")
                if sel_q2 != "全部":
                    qdf2 = qdf2[qdf2["quarter_label"] == sel_q2]

            fig2 = _chart(
                qdf2,
                x="stat_month",
                y="retention_rate",
                kind=chart_type2,
                y_as_percent=True,
                title_x="統計季度",
                title_y="留存率 (%)",
            )
            chart_col2, table_col2 = st.columns((2, 1), gap="large")
            with chart_col2:
                st.plotly_chart(fig2, use_container_width=True,
                                config={"modeBarButtonsToKeep": ["toImage", "pan2d", "toggleFullscreen"], "displaylogo": False})
            with table_col2:
                if scope2 == "全公司":
                    _right_table(qdf2.sort_values("stat_month", ascending=False),
                                 {"quarter_label": "季度", "retention_rate": "留存率",
                                  "months": "統計月份數"})
                else:
                    _right_table(qdf2.sort_values(["stat_month", "unit_id"], ascending=[False, True]),
                                 {"quarter_label": "季度", "unit_id": "處級代碼", "unit_name": "處級名稱",
                                  "months": "統計月份數", "retention_rate": "留存率"})

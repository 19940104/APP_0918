from __future__ import annotations

from datetime import datetime

import streamlit as st

from app.frontend.dashboard_shared import setup_page
from app.frontend.views.overview import render_overview

setup_page()

st.title("APP 使用分析儀表板")
st.caption("資料來源：DuckDB 彙總表")

render_overview()

st.info("請透過左側的頁面清單切換至各項分析。")

st.caption(f"最後更新：{datetime.now():%Y-%m-%d %H:%M:%S}")

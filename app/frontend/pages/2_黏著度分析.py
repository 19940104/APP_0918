from __future__ import annotations

import streamlit as st

from app.frontend.dashboard_shared import setup_page
from app.frontend.views.engagement import render_engagement

setup_page("APP 使用分析儀表板 | 黏著度分析")

st.title("黏著度分析")

render_engagement()

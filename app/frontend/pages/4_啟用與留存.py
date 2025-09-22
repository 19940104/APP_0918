from __future__ import annotations

import streamlit as st

from app.frontend.dashboard_shared import setup_page
from app.frontend.views.activation import render_activation

setup_page("APP 使用分析儀表板 | 啟用與留存")

st.title("啟用與留存")

render_activation()

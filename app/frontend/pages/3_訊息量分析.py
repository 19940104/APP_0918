from __future__ import annotations

import streamlit as st

from app.frontend.dashboard_shared import setup_page
from app.frontend.views.messages import render_messages

setup_page("APP 使用分析儀表板 | 訊息量分析")

st.title("訊息量分析")

render_messages()

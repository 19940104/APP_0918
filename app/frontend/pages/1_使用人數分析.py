from __future__ import annotations

from app.frontend.dashboard_shared import setup_page
from app.frontend.views.usage import render_usage

setup_page("APP 使用分析儀表板 | 使用人數分析")

render_usage()

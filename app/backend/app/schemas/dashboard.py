"""儀表板 API 回應模型定義（新版對齊）。"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel


class DailyActiveKPI(BaseModel):
    """日活躍 KPI。"""
    stat_date: date
    active_users: int
    total_users: int
    active_rate: Optional[float] = None


class WeeklyUsageKPI(BaseModel):
    """週使用率 KPI。"""
    stat_date: date
    active_users: int
    total_users: int
    usage_rate: Optional[float] = None


class ActivationKPI(BaseModel):
    """啟用與留存 KPI。"""
    stat_month: date
    activated_users: Optional[int] = None
    retained_users: Optional[int] = None
    total_employees: Optional[int] = None
    activation_rate: Optional[float] = None
    retention_rate: Optional[float] = None


class MessageKPI(BaseModel):
    """訊息相關 KPI。"""
    stat_date: date
    total_messages: int
    active_users: int
    avg_messages_per_user: Optional[float] = None
    total_employees: Optional[int] = None


class OverviewResponse(BaseModel):
    """首頁 KPI 回應整體模型。"""
    daily_active: Optional[DailyActiveKPI]
    weekly_usage: Optional[WeeklyUsageKPI]
    activation: Optional[ActivationKPI]
    message: Optional[MessageKPI]


class UsageTrendItem(BaseModel):
    """使用率趨勢資料項目。"""
    stat_date: date
    iso_year: Optional[int] = None
    iso_week: Optional[int] = None
    week_label: Optional[str] = None
    active_users: int
    total_users: int
    usage_rate: Optional[float] = None
    # 兼容舊欄位
    scope_id: Optional[str] = None
    # 新版部門趨勢會帶出 unit_id / unit_name
    unit_id: Optional[str] = None
    unit_name: Optional[str] = None


class UsageTrendResponse(BaseModel):
    """使用率趨勢回應。"""
    company: List[UsageTrendItem]
    departments: List[UsageTrendItem]


class ActiveSeriesItem(BaseModel):
    """日活躍時間序列項目。"""
    stat_date: date
    active_users: int
    total_users: int
    active_rate: Optional[float] = None


class EngagementResponse(BaseModel):
    """黏著度分析回應。"""
    daily: List[ActiveSeriesItem]
    weekly: List[UsageTrendItem]


class MessageTrendItem(BaseModel):
    """訊息走勢資料。"""
    stat_date: date
    total_messages: int
    active_users: int
    avg_messages_per_user: Optional[float] = None
    total_employees: Optional[int] = None


class MessageDistributionItem(BaseModel):
    """20/60/20 分布資料。"""
    stat_date: date
    segment: str
    user_share: Optional[float] = None   # 新版目前以 NULL 回傳
    message_share: float
    user_count: Optional[int] = None     # 新版目前以 NULL 回傳


class MessageLeaderboardItem(BaseModel):
    """訊息排行榜資料。"""
    rank: int
    emp_no: str
    unit_id: Optional[str] = None
    unit_name: Optional[str] = None
    total_messages: int


class MessageInsightResponse(BaseModel):
    """訊息相關分析回應。"""
    trend: List[MessageTrendItem]
    distribution: List[MessageDistributionItem]
    leaderboard: List[MessageLeaderboardItem]


class ActivationItem(BaseModel):
    """部門啟用/留存資料。"""
    stat_month: date
    unit_id: Optional[str] = None
    unit_name: Optional[str] = None
    activated_users: Optional[int] = None
    retained_users: Optional[int] = None
    activation_rate: Optional[float] = None
    retention_rate: Optional[float] = None


class ActivationInsightResponse(BaseModel):
    """啟用留存分析回應。"""
    activation: List[ActivationItem]
    retention: List[ActivationItem]

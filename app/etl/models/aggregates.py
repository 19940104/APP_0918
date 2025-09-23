"""ETL 聚合資料模型定義（對齊新版 UsageStatsPipeline 與 DuckDB Schema）。"""

from __future__ import annotations

from datetime import date
from typing import Optional
from pydantic import BaseModel


# =========================
# 覆蓋率（週）
# =========================

class CoverageCompanyWeekly(BaseModel):
    """全公司覆蓋率（週）。來源表：coverage_company_weekly"""
    iso_year: int
    iso_week: int
    baseline_date: date
    covered_users: int
    total_users: int
    coverage_rate: float  # 0.0~1.0


class CoverageUnitWeekly(BaseModel):
    """各部門覆蓋率（週）。來源表：coverage_unit_weekly"""
    iso_year: int
    iso_week: int
    baseline_date: Optional[date] = None  # 轉換時有填，允許 None 以保險
    root_org_id: Optional[str] = None
    root_org_name: Optional[str] = None
    used_users: int
    total_users: Optional[int] = 0
    coverage_rate: float  # 0.0~1.0


# =========================
# 工作日活躍（日）
# =========================

class ActiveRateWorkingdayDaily(BaseModel):
    """工作日活躍（日）。來源表：active_rate_workingday_daily"""
    date: date
    active_users: int
    total_users: int
    active_rate: float  # 0.0~1.0


# =========================
# 啟用與留存（公司）
# =========================

class ActivationNextMonthCompany(BaseModel):
    """當月啟用率（公司）。來源表：activation_next_month_company"""
    hire_month: date        # 入職月份（該月第一天）
    new_hires: int          # 新人數
    used_next_month: int    # 次月有使用人數
    activation_rate: float  # 0.0~1.0


class RetentionMonthlyCompany(BaseModel):
    """當月留存率（公司）。來源表：retention_monthly_company"""
    active_month: date       # 活躍月份（該月第一天）
    active_users: int        # 該月月活躍人數
    registered_total: int    # 自 2025-01-01 起曾經使用過的人數（固定分母）
    retention_rate: float    # 0.0~1.0


# =========================
# 訊息量（週）
# =========================

class MessagesWeeklyTotal(BaseModel):
    """每週工作日訊息數總計。來源表：messages_weekly_total"""
    iso_year: int
    iso_week: int
    messages: int


class MessagesWeeklyPerCapita(BaseModel):
    """每週工作日人均訊息數。來源表：messages_weekly_percapita"""
    iso_year: int
    iso_week: int
    messages: int
    total_users: int
    messages_per_user: float


class MessageDistributionWeekly(BaseModel):
    """訊息分布 20/60/20（週）。來源表：message_distribution_weekly_20_60_20"""
    iso_year: int
    iso_week: int
    segment: str            # '前20%' / '中間60%' / '後20%'
    message_sum: int
    share_percent: float    # 0.0~100.0（百分比）


# =========================
# （可選）相容性模型：若你的前端或 API 尚未改完，可先用這些模型對映舊結構
# =========================

class UsageAggregateCompat(BaseModel):
    """
    相容舊版「使用率聚合」的模型（對映舊表 usage_rate_weekly）。
    建議只用於過渡期；新介面請改用 CoverageCompanyWeekly / CoverageUnitWeekly。
    """
    stat_date: date
    scope: str                 # 固定 'company'（如果你只對應全公司）
    scope_id: Optional[str]    # 仍保留欄位，但對於公司層級為 None
    active_users: int          # 對映 covered_users
    total_users: int
    usage_rate: float          # 對映 coverage_rate（0.0~1.0）


class MessageAggregateCompat(BaseModel):
    """
    相容舊版「訊息量聚合（日）」的模型（舊表 message_aggregate_daily）。
    新版是週彙總；若仍有舊前端日粒度需求，可以自行用 DuckDB SQL 從週資料展開或維持舊管線。
    """
    stat_date: date
    total_messages: int
    active_users: int
    avg_messages_per_user: float


class ActivationAggregateCompat(BaseModel):
    """
    相容舊版「啟用與留存」的模型（舊表 activation_monthly）。
    新版將啟用與留存分開兩張表；此模型僅供過渡。
    """
    stat_month: date
    unit_id: Optional[str]
    activated_users: Optional[int] = None
    retained_users: Optional[int] = None
    total_new_hires: Optional[int] = None
    activation_rate: Optional[float] = None
    retention_rate: Optional[float] = None

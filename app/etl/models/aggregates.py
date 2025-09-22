"""ETL 聚合資料模型定義。"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class UsageAggregate(BaseModel):
    """使用率聚合資料模型。"""

    stat_date: date
    scope: str  # company / unit
    scope_id: str | None
    active_users: int
    total_users: int
    usage_rate: float


class MessageAggregate(BaseModel):
    """訊息量聚合資料模型。"""

    stat_date: date
    total_messages: int
    active_users: int
    avg_messages_per_user: float


class ActivationAggregate(BaseModel):
    """啟用與留存指標資料模型。"""

    stat_month: date
    unit_id: str | None
    activated_users: int
    retained_users: int
    total_new_hires: int
    activation_rate: float
    retention_rate: float



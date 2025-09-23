"""DuckDB Schema 初始化工具（對齊新版 UsageStatsPipeline）。"""

from __future__ import annotations
from typing import Iterable
from app.etl.storage.duckdb_client import DuckDBClient

# 新版 Pipeline 目標表（完全對齊 UsageStatsPipeline.load）
SCHEMA_STATEMENTS: Iterable[str] = (
    # 1) 全公司覆蓋率（週）
    """
    CREATE TABLE IF NOT EXISTS coverage_company_weekly (
        iso_year INTEGER,
        iso_week INTEGER,
        baseline_date DATE,
        covered_users INTEGER,
        total_users INTEGER,
        coverage_rate DOUBLE
    )
    """,
    # 2) 各部門覆蓋率（週）
    """
    CREATE TABLE IF NOT EXISTS coverage_unit_weekly (
        iso_year INTEGER,
        iso_week INTEGER,
        baseline_date DATE,
        root_org_id VARCHAR,
        root_org_name VARCHAR,
        used_users INTEGER,
        total_users INTEGER,
        coverage_rate DOUBLE
    )
    """,
    # 3) 工作日活躍（日）
    """
    CREATE TABLE IF NOT EXISTS active_rate_workingday_daily (
        date DATE,
        active_users INTEGER,
        total_users INTEGER,
        active_rate DOUBLE
    )
    """,
    # 4) 當月啟用率（公司）
    """
    CREATE TABLE IF NOT EXISTS activation_next_month_company (
        hire_month DATE,
        new_hires INTEGER,
        used_next_month INTEGER,
        activation_rate DOUBLE
    )
    """,
    # 5) 當月留存率（公司）
    """
    CREATE TABLE IF NOT EXISTS retention_monthly_company (
        active_month DATE,
        active_users INTEGER,
        registered_total INTEGER,
        retention_rate DOUBLE
    )
    """,
    # 6) 每週工作日訊息總計
    """
    CREATE TABLE IF NOT EXISTS messages_weekly_total (
        iso_year INTEGER,
        iso_week INTEGER,
        messages INTEGER
    )
    """,
    # 7) 每週工作日人均訊息數
    """
    CREATE TABLE IF NOT EXISTS messages_weekly_percapita (
        iso_year INTEGER,
        iso_week INTEGER,
        messages INTEGER,
        total_users INTEGER,
        messages_per_user DOUBLE
    )
    """,
    # 8) 訊息分布 20/60/20（週）
    """
    CREATE TABLE IF NOT EXISTS message_distribution_weekly_20_60_20 (
        iso_year INTEGER,
        iso_week INTEGER,
        segment VARCHAR,
        message_sum INTEGER,
        share_percent DOUBLE
    )
    """,
)

# （可選）提供相容性 VIEW：讓舊前端查詢舊表名也能運作
# 不需要可以把 COMPAT_VIEWS 清空或整段移除
COMPAT_VIEWS: Iterable[str] = (
    # 原 user_active_daily -> 對應 active_rate_workingday_daily
    """
    CREATE VIEW IF NOT EXISTS user_active_daily AS
    SELECT
        date AS stat_date,
        active_users,
        total_users,
        active_rate
    FROM active_rate_workingday_daily
    """,
    # 原 usage_rate_weekly -> 可對應「全公司覆蓋率」(company)；若要合併部門也可再做 UNION
    """
    CREATE VIEW IF NOT EXISTS usage_rate_weekly AS
    SELECT
        -- 舊結構只有 stat_date/scope/scope_id/active_users/total_users/usage_rate
        -- 這裡以 baseline_date 當 stat_date；scope 固定 'company'
        baseline_date AS stat_date,
        'company' AS scope,
        NULL::VARCHAR AS scope_id,
        covered_users AS active_users,
        total_users,
        coverage_rate AS usage_rate
    FROM coverage_company_weekly
    """,
    # 原 message_aggregate_daily -> 新版是週彙總，這裡不做對映（如需請改為以週轉日）
    # 原 message_distribution_20_60_20 (日) -> 新版為週，名稱不同，若要保留舊名可做週轉日或直接提供週資料：
    """
    CREATE VIEW IF NOT EXISTS message_distribution_20_60_20 AS
    SELECT
        -- 舊欄位: stat_date, segment, user_share, message_share, user_count
        -- 新版為週彙總，這裡以「週一日期」當作 stat_date，僅提供 message_share（以 share_percent/100 表示）
        -- user_share/user_count 在新版未產出，給 NULL
        (make_date(iso_year, 1, 4) - (EXTRACT(DOW FROM make_date(iso_year, 1, 4))::INT - 1))  -- 近似該年首週起算
        + ((iso_week - 1) * 7) AS stat_date,
        segment,
        NULL::DOUBLE AS user_share,
        share_percent / 100.0 AS message_share,
        NULL::INTEGER AS user_count
    FROM message_distribution_weekly_20_60_20
    """,
    # 原 message_leaderboard -> 新版 Pipeline 已不寫入排行榜，如需保留可建空殼 VIEW（避免舊程式炸掉）
    """
    CREATE VIEW IF NOT EXISTS message_leaderboard AS
    SELECT
        CAST(NULL AS INTEGER) AS rank,
        CAST(NULL AS VARCHAR) AS emp_no,
        CAST(NULL AS VARCHAR) AS unit_id,
        CAST(NULL AS INTEGER) AS total_messages
    WHERE FALSE
    """,
    # 原 activation_monthly -> 新版有兩種表；這裡以公司彙總的 retention/activation 分別提供兩個 VIEW 名稱
    """
    CREATE VIEW IF NOT EXISTS activation_monthly AS
    SELECT
        hire_month AS stat_month,
        NULL::VARCHAR AS unit_id,
        -- 舊表沒有 unit_name 欄位，這裡不提供
        new_hires AS activated_users,
        NULL::INTEGER AS retained_users,
        NULL::INTEGER AS total_employees,
        activation_rate,
        NULL::DOUBLE AS retention_rate
    FROM activation_next_month_company
    """,
)


def initialize_duckdb(client: DuckDBClient) -> None:
    """建立專案所需 DuckDB 表格與相容性 VIEW。"""
    for stmt in SCHEMA_STATEMENTS:
        client.execute(stmt)
    for v in COMPAT_VIEWS:
        client.execute(v)

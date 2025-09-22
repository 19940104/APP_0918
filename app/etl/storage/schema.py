"""DuckDB Schema 初始化工具。"""

from __future__ import annotations

from typing import Iterable

from app.etl.storage.duckdb_client import DuckDBClient

# 依需求建立 DuckDB 表格 Schema
SCHEMA_STATEMENTS: Iterable[str] = (
    """
    CREATE TABLE IF NOT EXISTS user_active_daily (
        stat_date DATE,
        active_users INTEGER,
        total_users INTEGER,
        active_rate DOUBLE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS usage_rate_weekly (
        stat_date DATE,
        scope VARCHAR,
        scope_id VARCHAR,
        active_users INTEGER,
        total_users INTEGER,
        usage_rate DOUBLE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS message_aggregate_daily (
        stat_date DATE,
        total_messages INTEGER,
        active_users INTEGER,
        avg_messages_per_user DOUBLE,
        total_employees INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS message_distribution_20_60_20 (
        stat_date DATE,
        segment VARCHAR,
        user_share DOUBLE,
        message_share DOUBLE,
        user_count INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS message_leaderboard (
        rank INTEGER,
        emp_no VARCHAR,
        unit_id VARCHAR,
        total_messages INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS activation_monthly (
        stat_month DATE,
        unit_id VARCHAR,
        activated_users INTEGER,
        retained_users INTEGER,
        total_employees INTEGER,
        activation_rate DOUBLE,
        retention_rate DOUBLE
    )
    """,
)


def initialize_duckdb(client: DuckDBClient) -> None:
    """建立專案所需 DuckDB 表格。"""

    for statement in SCHEMA_STATEMENTS:
        client.execute(statement)



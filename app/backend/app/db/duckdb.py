"""DuckDB FastAPI 依賴注入模組（每請求連線、預設唯讀）。"""

from __future__ import annotations

from typing import Generator

from fastapi import Depends
from app.config.settings import settings
from app.etl.storage.duckdb_client import DuckDBClient


def get_duckdb_client() -> Generator[DuckDBClient, None, None]:
    """
    提供「唯讀」 DuckDB 連線給 API（每個請求一條連線，用完關閉）。
    適用 Dashboard 查詢情境，避免多執行緒共享單一連線的風險。
    """
    client = DuckDBClient(db_path=settings.storage.duckdb_path, read_only=True)
    try:
        client.connect()  # 提前建立，若錯誤可及早拋出
        yield client
    finally:
        client.close()


def get_duckdb_rw_client() -> Generator[DuckDBClient, None, None]:
    """
    提供「可寫入」 DuckDB 連線（每請求一條連線，用完關閉）。
    僅在需要寫入或維運工具（例如手動回填、維修）時使用。
    """
    client = DuckDBClient(db_path=settings.storage.duckdb_path, read_only=False)
    try:
        client.connect()
        yield client
    finally:
        client.close()

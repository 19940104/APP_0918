"""DuckDB FastAPI 依賴注入模組。"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from app.etl.storage.duckdb_client import DuckDBClient

_duck_client = DuckDBClient()


@contextmanager
def duckdb_session() -> Generator[DuckDBClient, None, None]:
    """Context manager，於需要時提供 DuckDBClient。"""

    try:
        yield _duck_client
    finally:
        pass


def get_duckdb_client() -> DuckDBClient:
    """FastAPI 依賴函式。"""

    return _duck_client



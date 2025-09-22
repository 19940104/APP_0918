"""DuckDB 儲存層存取工具。"""

from __future__ import annotations

import duckdb
import pandas as pd
from duckdb import CatalogException

from app.config.settings import settings
from app.etl.utils.logging import get_logger

logger = get_logger(__name__)


class DuckDBClient:
    """封裝 DuckDB 讀寫操作，便於單元測試。"""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or settings.storage.duckdb_path
        self._conn: duckdb.DuckDBPyConnection | None = None

    def connect(self) -> duckdb.DuckDBPyConnection:
        """建立連線並回傳，若已存在則直接使用。"""

        if self._conn is None:
            logger.info("開啟 DuckDB 連線：%s", self.db_path)
            self._conn = duckdb.connect(self.db_path)
        return self._conn

    def close(self) -> None:
        """關閉資料庫連線。"""

        if self._conn is not None:
            logger.debug("關閉 DuckDB 連線")
            self._conn.close()
            self._conn = None

    def execute(self, sql: str, parameters: dict | None = None) -> None:
        """執行任意 SQL 指令。"""

        conn = self.connect()
        conn.execute(sql, parameters or {})

    def query_dataframe(self, sql: str, parameters: dict | None = None) -> pd.DataFrame:
        """查詢並回傳 DataFrame。"""

        conn = self.connect()
        return conn.execute(sql, parameters or {}).fetch_df()

    def write_dataframe(self, df: pd.DataFrame, table: str, mode: str = "append") -> None:
        """將 DataFrame 寫入指定資料表。"""

        if df.empty:
            logger.warning("無資料寫入 DuckDB：%s", table)
            return

        conn = self.connect()
        conn.register("tmp_df", df)
        try:
            if mode == "replace":
                logger.info("覆寫 DuckDB 資料表 %s，筆數=%s", table, len(df))
                conn.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM tmp_df")
            else:
                logger.info("追加寫入 DuckDB 資料表 %s，筆數=%s", table, len(df))
                conn.execute(f"INSERT INTO {table} SELECT * FROM tmp_df")
        except CatalogException:
            logger.info("資料表 %s 不存在，改為建立新表。", table)
            conn.execute(f"CREATE TABLE {table} AS SELECT * FROM tmp_df")
        finally:
            conn.unregister("tmp_df")

    def ensure_table(self, create_sql: str) -> None:
        """確保資料表存在，沒有就建立。"""

        conn = self.connect()
        logger.debug("確認 DuckDB 資料表：%s", create_sql)
        conn.execute(create_sql)

    def __enter__(self) -> "DuckDBClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()



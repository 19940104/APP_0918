"""DuckDB 儲存層存取工具（強化版）。"""

from __future__ import annotations

import re
import duckdb
import pandas as pd
from duckdb import CatalogException, DuckDBPyConnection

from app.config.settings import settings
from app.etl.utils.logging import get_logger

logger = get_logger(__name__)

_VALID_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _quote_ident(name: str) -> str:
    """簡單的識別字元檢查＆引用，避免表名/欄位名造成 SQL 錯誤。"""
    if name is None:
        raise ValueError("Identifier cannot be None")
    name = str(name)
    if _VALID_IDENT_RE.match(name):
        return name
    # 用雙引號包起來，並 escape 內部的雙引號
    return '"' + name.replace('"', '""') + '"'


class DuckDBClient:
    """封裝 DuckDB 讀寫操作，便於單元測試。"""

    def __init__(self, db_path: str | None = None, read_only: bool = False, threads: int | None = None) -> None:
        self.db_path = db_path or settings.storage.duckdb_path
        self.read_only = read_only
        self.threads = threads
        self._conn: DuckDBPyConnection | None = None

    # ------------------------------
    # 連線管理
    # ------------------------------
    def connect(self) -> DuckDBPyConnection:
        """建立連線並回傳，若已存在則直接使用。"""
        if self._conn is None:
            logger.info("開啟 DuckDB 連線：%s (read_only=%s)", self.db_path, self.read_only)
            self._conn = duckdb.connect(self.db_path, read_only=self.read_only)
            if self.threads and isinstance(self.threads, int) and self.threads > 0:
                self._conn.execute(f"PRAGMA threads={int(self.threads)}")
        return self._conn

    def close(self) -> None:
        """關閉資料庫連線。"""
        if self._conn is not None:
            logger.debug("關閉 DuckDB 連線")
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "DuckDBClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # ------------------------------
    # 基礎操作
    # ------------------------------
    def execute(self, sql: str, parameters: dict | None = None) -> None:
        """執行任意 SQL 指令。"""
        conn = self.connect()
        conn.execute(sql, parameters or {})

    def query_dataframe(self, sql: str, parameters: dict | None = None) -> pd.DataFrame:
        """查詢並回傳 DataFrame。"""
        conn = self.connect()
        return conn.execute(sql, parameters or {}).fetch_df()

    def ensure_schema(self, schema: str) -> None:
        """確保 Schema 存在。"""
        schema_quoted = _quote_ident(schema)
        self.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_quoted}")

    def ensure_table(self, create_sql: str) -> None:
        """確保資料表存在，沒有就建立。"""
        conn = self.connect()
        logger.debug("確認/建立資料表：%s", create_sql)
        conn.execute(create_sql)

    # ------------------------------
    # DataFrame 註冊工具
    # ------------------------------
    def _register_temp_df(self, name: str, df: pd.DataFrame) -> str:
        """將 DataFrame 註冊為 DuckDB 暫存檢視，回傳實際註冊名。"""
        conn = self.connect()
        reg_name = f"tmp_{name}"
        conn.register(reg_name, df)
        return reg_name

    def _unregister_temp(self, name: str) -> None:
        try:
            self.connect().unregister(name)
        except Exception:
            pass

    # ------------------------------
    # 寫入操作（append / replace / upsert）
    # ------------------------------
    def write_dataframe(
        self,
        df: pd.DataFrame,
        table: str,
        mode: str = "append",
        schema: str | None = None,
        keys: list[str] | None = None,  # upsert 主鍵欄位
        transaction: bool = True,
        coerce_schema: bool = True,     # 將欄位順序與現有表對齊
    ) -> None:
        """
        將 DataFrame 寫入指定資料表。

        mode:
          - "append"  : INSERT
          - "replace" : CREATE OR REPLACE TABLE AS SELECT
          - "upsert"  : 以 MERGE 實作，需要提供 keys（主鍵或唯一鍵）

        keys:
          - 僅在 mode="upsert" 有用，例如 ["emp_id"] 或 ["iso_year", "iso_week", "root_org_id"]
        """
        if df is None or df.empty:
            logger.warning("無資料寫入 DuckDB：%s", table)
            return

        conn = self.connect()
        schema_prefix = f"{_quote_ident(schema)}." if schema else ""
        table_ident = f"{schema_prefix}{_quote_ident(table)}"

        tmp_name = self._register_temp_df("df", df)
        try:
            if mode == "replace":
                if transaction:
                    conn.execute("BEGIN")
                logger.info("覆寫 DuckDB 資料表 %s，筆數=%s", table_ident, len(df))
                conn.execute(f"CREATE OR REPLACE TABLE {table_ident} AS SELECT * FROM {tmp_name}")
                if transaction:
                    conn.execute("COMMIT")
                return

            # 其餘模式需要確保表存在
            try:
                # 先試著讀欄位結構
                cols = conn.execute(f"PRAGMA table_info({table_ident})").fetch_df()
                table_exists = not cols.empty
            except CatalogException:
                table_exists = False

            if not table_exists:
                logger.info("資料表不存在，自動建立：%s（以 DataFrame 結構）", table_ident)
                if transaction:
                    conn.execute("BEGIN")
                conn.execute(f"CREATE TABLE {table_ident} AS SELECT * FROM {tmp_name}")
                if transaction:
                    conn.execute("COMMIT")
                return

            # 表已存在 → 欄位對齊（可選）
            if coerce_schema:
                existing_cols = [
                    r[1] for r in conn.execute(f"PRAGMA table_info({table_ident})").fetchall()
                ]  # (cid, name, type, ...)
                missing_cols = [c for c in existing_cols if c not in df.columns]
                extra_cols = [c for c in df.columns if c not in existing_cols]
                if extra_cols:
                    logger.warning("寫入欄位在目標表不存在：%s；將只寫入交集欄位。", extra_cols)
                # 只保留交集，並依現有表的欄位順序寫入
                df2 = df[[c for c in existing_cols if c in df.columns]].copy()
                self._unregister_temp(tmp_name)
                tmp_name = self._register_temp_df("df", df2)

            if mode == "append":
                if transaction:
                    conn.execute("BEGIN")
                logger.info("追加寫入 %s，筆數=%s", table_ident, len(df))
                conn.execute(f"INSERT INTO {table_ident} SELECT * FROM {tmp_name}")
                if transaction:
                    conn.execute("COMMIT")
                return

            if mode == "upsert":
                if not keys:
                    raise ValueError("mode='upsert' 需要提供 keys（主鍵欄位清單）")
                # 取得表欄位
                cols_df = conn.execute(f"PRAGMA table_info({table_ident})").fetch_df()
                cols = [c for c in cols_df["name"].tolist()]
                non_keys = [c for c in cols if c not in keys]

                if not non_keys:
                    # 全欄位都是 key → 插入時若衝突就忽略（DuckDB 尚未支援 IGNORE，改用條件式）
                    # 這種情況極少見，給出提示
                    logger.warning("UPsert 無可更新欄位（所有欄位皆為 keys），將改為僅補缺資料。")

                on_clause = " AND ".join([f"T.{_quote_ident(k)} = S.{_quote_ident(k)}" for k in keys])
                update_clause = ", ".join([f"{_quote_ident(c)} = S.{_quote_ident(c)}" for c in non_keys]) or ""
                all_cols = ", ".join([_quote_ident(c) for c in cols])

                if transaction:
                    conn.execute("BEGIN")
                logger.info("UPSERT 寫入 %s，筆數=%s（keys=%s）", table_ident, len(df), keys)
                if non_keys:
                    conn.execute(
                        f"""
                        MERGE INTO {table_ident} AS T
                        USING {tmp_name} AS S
                        ON {on_clause}
                        WHEN MATCHED THEN UPDATE SET {update_clause}
                        WHEN NOT MATCHED THEN INSERT ({all_cols}) VALUES ({', '.join(['S.' + _quote_ident(c) for c in cols])})
                        """
                    )
                else:
                    # 無非鍵欄位：只在不存在時插入
                    conn.execute(
                        f"""
                        INSERT INTO {table_ident}
                        SELECT {all_cols}
                        FROM {tmp_name} S
                        WHERE NOT EXISTS (
                            SELECT 1 FROM {table_ident} T WHERE {on_clause}
                        )
                        """
                    )
                if transaction:
                    conn.execute("COMMIT")
                return

            raise ValueError(f"不支援的寫入模式：{mode}")

        except Exception:
            # 發生錯誤時嘗試回滾
            try:
                self.connect().execute("ROLLBACK")
            except Exception:
                pass
            raise
        finally:
            self._unregister_temp(tmp_name)

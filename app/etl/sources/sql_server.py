"""負責與 SQL Server 溝通的資料來源模組（強化版）。"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional
import logging
import time
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError, OperationalError

from app.config.settings import settings
from app.etl.utils.logging import get_logger

logger = get_logger(__name__)
# 將 SQL 內容降為 debug 等級，避免在 info 等級露出 (可視情況調整)
SQL_LOG_LEVEL = logging.DEBUG


class SQLServerSource:
    """封裝 SQL Server 連線與查詢邏輯。"""

    def __init__(
        self,
        host: Optional[str] = None,
        database: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        driver: Optional[str] = None,
        encrypt: Optional[str] = None,                # "yes"/"no"
        trust_cert: Optional[str] = None,             # "yes"/"no"
        mars: Optional[str] = None,                   # "yes"/"no"
        timeout: Optional[int] = None,                # login timeout (sec)
        appname: Optional[str] = "usage-etl",
        query_timeout: Optional[int] = 60,            # per-query timeout (sec)
        connect_retries: int = 2,
        connect_retry_wait: float = 1.0,
    ) -> None:
        src = settings.source_db
        self.host = host or src.host
        self.database = database or src.database
        self.username = username or src.username
        self.password = password or src.password
        self.driver = driver or src.driver or "ODBC Driver 17 for SQL Server"

        # 連線選項預設
        self.encrypt = (encrypt or getattr(src, "encrypt", "no")).lower()
        self.trust_cert = (trust_cert or getattr(src, "trust_cert", "yes")).lower()
        self.mars = (mars or getattr(src, "mars", "yes")).lower()
        self.timeout = timeout or getattr(src, "timeout", 5)
        self.appname = appname or getattr(src, "appname", "usage-etl")
        self.query_timeout = query_timeout
        self.connect_retries = connect_retries
        self.connect_retry_wait = connect_retry_wait

        self._engine: Optional[Engine] = None

    @property
    def engine(self) -> Engine:
        """建立或回傳 SQLAlchemy Engine。"""
        if self._engine is not None:
            return self._engine

        if not all([self.host, self.database, self.username, self.password]):
            raise ValueError("SQL Server 連線資訊不完整，請檢查 .env 或設定檔。")

        # URL encode 驅動/帳密
        driver_enc = quote_plus(self.driver)
        user_enc = quote_plus(self.username)
        pwd_enc = quote_plus(self.password)

        # 常見且實用的 ODBC 參數
        extras = {
            "Encrypt": "yes" if self.encrypt in ("1", "true", "yes") else "no",
            "TrustServerCertificate": "yes" if self.trust_cert in ("1", "true", "yes") else "no",
            "MARS_Connection": "yes" if self.mars in ("1", "true", "yes") else "no",
            "LoginTimeout": str(int(self.timeout)),
            "ApplicationIntent": "ReadOnly",
            "APP": self.appname or "usage-etl",
        }
        # 組成 query string
        extra_qs = "&".join(f"{k}={quote_plus(v)}" for k, v in extras.items())

        conn_str = (
            f"mssql+pyodbc://{user_enc}:{pwd_enc}"
            f"@{self.host}/{self.database}"
            f"?driver={driver_enc}&{extra_qs}"
        )

        last_err = None
        for attempt in range(self.connect_retries + 1):
            try:
                self._engine = create_engine(
                    conn_str,
                    fast_executemany=True,
                    pool_pre_ping=True,        # 失效連線自檢
                    pool_recycle=1800,         # 連線回收時間（秒）
                )
                # 簡易健康檢查
                with self._engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                logger.info("成功建立 SQL Server 連線引擎")
                return self._engine
            except OperationalError as e:
                last_err = e
                logger.warning("建立連線失敗(%s/%s)：%s", attempt + 1, self.connect_retries + 1, e)
                time.sleep(self.connect_retry_wait)
            except SQLAlchemyError as e:
                last_err = e
                logger.error("建立連線時發生 SQLAlchemy 錯誤：%s", e)
                break

        # 若到這裡仍失敗
        raise RuntimeError(f"無法建立 SQL Server 連線：{last_err}") from last_err

    def fetch_dataframe(self, query: str, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """執行查詢並回傳 DataFrame。"""
        logger.log(SQL_LOG_LEVEL, "執行 SQL（fetch_dataframe）; params=%s", params)
        # 使用 pandas 內建的 read_sql_query 讓型別推斷與 params 綁定更穩定
        with self.engine.connect() as connection:
            # 設定每查詢的超時（pyodbc: SET QUERY_GOVERNOR_COST_LIMIT/SET LOCK_TIMEOUT 不同語義；這裡用 ODBC timeout）
            if self.query_timeout:
                connection.exec_driver_sql(f"SET LOCK_TIMEOUT {int(self.query_timeout)*1000}")  # 毫秒
            df = pd.read_sql_query(sql=text(query), con=connection, params=params or {})
        logger.info("取得 %s 筆資料", len(df))
        return df

    def fetch_iterable(
        self, query: str, params: Optional[Dict[str, Any]] = None, chunk_size: int = 5000
    ) -> Iterable[pd.DataFrame]:
        """採分批方式取得資料，用於大表處理。"""
        logger.log(SQL_LOG_LEVEL, "執行 SQL（fetch_iterable）; chunk_size=%s; params=%s", chunk_size, params)
        with self.engine.connect() as connection:
            if self.query_timeout:
                connection.exec_driver_sql(f"SET LOCK_TIMEOUT {int(self.query_timeout)*1000}")
            result = connection.execution_options(stream_results=True).execute(text(query), params or {})
            while True:
                chunk = result.fetchmany(chunk_size)
                if not chunk:
                    break
                yield pd.DataFrame(chunk, columns=result.keys())

    # 方便需要時呼叫（例如檢查連線或做簡單的 scalar 值）
    def fetch_scalar(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
        logger.log(SQL_LOG_LEVEL, "執行 SQL（fetch_scalar）; params=%s", params)
        with self.engine.connect() as connection:
            row = connection.execute(text(query), params or {}).fetchone()
            return None if row is None else row[0]

"""負責與 SQL Server 溝通的資料來源模組。"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.config.settings import settings
from app.etl.utils.logging import get_logger

logger = get_logger(__name__)


class SQLServerSource:
    """封裝 SQL Server 連線與查詢邏輯。"""

    def __init__(
        self,
        host: Optional[str] = None,
        database: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        driver: Optional[str] = None,
    ) -> None:
        src = settings.source_db
        self.host = host or src.host
        self.database = database or src.database
        self.username = username or src.username
        self.password = password or src.password
        self.driver = driver or src.driver
        self._engine: Optional[Engine] = None

    @property
    def engine(self) -> Engine:
        """建立或回傳 SQLAlchemy Engine。"""

        if self._engine is None:
            if not all([self.host, self.database, self.username, self.password]):
                raise ValueError("SQL Server 連線資訊不完整，請檢查 .env 或設定檔。")

            conn_str = (
                f"mssql+pyodbc://{self.username}:{self.password}"
                f"@{self.host}/{self.database}?driver={self.driver}"
            )
            self._engine = create_engine(conn_str, fast_executemany=True)
            logger.info("成功建立 SQL Server 連線引擎")
        return self._engine

    def fetch_dataframe(self, query: str, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """執行查詢並回傳 DataFrame。"""

        logger.debug("執行 SQL 查詢: %s", query)
        with self.engine.connect() as connection:
            result = connection.execute(text(query), params or {})
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
        logger.info("取得 %s 筆資料", len(df))
        return df

    def fetch_iterable(
        self, query: str, params: Optional[Dict[str, Any]] = None, chunk_size: int = 5000
    ) -> Iterable[pd.DataFrame]:
        """採分批方式取得資料，用於大表處理。"""

        logger.debug("以 chunk_size=%s 取得資料", chunk_size)
        with self.engine.connect() as connection:
            result = connection.execution_options(stream_results=True).execute(text(query), params or {})
            while True:
                chunk = result.fetchmany(chunk_size)
                if not chunk:
                    break
                yield pd.DataFrame(chunk, columns=result.keys())



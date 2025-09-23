"""ETL Pipeline 抽象基底類別（強型別＋錯誤保護版）。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Generic, Mapping, TypeVar
import time
import traceback

from app.etl.utils.logging import get_logger

logger = get_logger(__name__)

RawT = TypeVar("RawT", bound=Mapping[str, object])
OutT = TypeVar("OutT", bound=Mapping[str, object])


class BasePipeline(ABC, Generic[RawT, OutT]):
    """所有 Pipeline 的共同介面。"""

    name: str = "base-pipeline"

    @abstractmethod
    def extract(self) -> RawT:
        """實作資料抽取邏輯。"""

    @abstractmethod
    def transform(self, raw_items: RawT) -> OutT:
        """實作資料轉換邏輯。"""

    @abstractmethod
    def load(self, processed_items: OutT) -> None:
        """實作資料載入邏輯。"""

    def run(self) -> None:
        """執行 Pipeline 全流程（含計時與錯誤保護）。"""
        start_ts = time.time()
        logger.info("開始執行 Pipeline：%s", self.name)
        try:
            raw_items = self.extract()
            logger.info("[%s] 抽取完成（%.2fs）", self.name, time.time() - start_ts)

            t0 = time.time()
            processed_items = self.transform(raw_items)
            logger.info("[%s] 轉換完成（%.2fs）", self.name, time.time() - t0)

            t1 = time.time()
            self.load(processed_items)
            logger.info("[%s] 載入完成（%.2fs）", self.name, time.time() - t1)

            logger.info("Pipeline 完成：%s（總耗時 %.2fs）", self.name, time.time() - start_ts)
        except Exception as e:
            logger.error("Pipeline 失敗：%s | %s", self.name, e)
            logger.debug("Traceback:\n%s", traceback.format_exc())
            # 視需求決定是否往外拋出
            raise

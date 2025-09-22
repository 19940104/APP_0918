"""ETL Pipeline 抽象基底類別。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from app.etl.utils.logging import get_logger

logger = get_logger(__name__)


class BasePipeline(ABC):
    """所有 Pipeline 的共同介面。"""

    name: str = "base-pipeline"

    @abstractmethod
    def extract(self) -> Iterable[object]:
        """實作資料抽取邏輯。"""

    @abstractmethod
    def transform(self, raw_items: Iterable[object]) -> Iterable[object]:
        """實作資料轉換邏輯。"""

    @abstractmethod
    def load(self, processed_items: Iterable[object]) -> None:
        """實作資料載入邏輯。"""

    def run(self) -> None:
        """執行 Pipeline 全流程。"""

        logger.info("開始執行 Pipeline：%s", self.name)
        raw_items = self.extract()
        processed_items = self.transform(raw_items)
        self.load(processed_items)
        logger.info("Pipeline 完成：%s", self.name)



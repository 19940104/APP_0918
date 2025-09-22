"""ETL 專用紀錄器設定。"""

from __future__ import annotations

import logging
from logging import Logger

from app.config.settings import settings


def get_logger(name: str) -> Logger:
    """建立帶有預設格式的紀錄器。"""

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(settings.logging.level)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger



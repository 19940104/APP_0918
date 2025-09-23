"""ETL 專用紀錄器設定（強化版，介面相容）。"""

from __future__ import annotations

import json
import logging
import os
import time
from logging import Logger
from logging.handlers import RotatingFileHandler
from typing import Any, Dict

from app.config.settings import settings


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # 常見額外欄位
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            payload.update(record.extra)  # 可傳 dict 當 extra
        return json.dumps(payload, ensure_ascii=False)


def _build_stream_formatter() -> logging.Formatter:
    if getattr(settings.logging, "json", False):
        fmt = _JsonFormatter()
        fmt.converter = time.localtime if getattr(settings.logging, "use_localtime", False) else time.gmtime
        return fmt
    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # UTC or localtime
    fmt.converter = time.localtime if getattr(settings.logging, "use_localtime", False) else time.gmtime
    return fmt


def _maybe_file_handler() -> logging.Handler | None:
    if not getattr(settings.logging, "file_enabled", False):
        return None
    log_path = getattr(settings.logging, "file_path", "logs/etl.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    max_bytes = int(getattr(settings.logging, "max_bytes", 10 * 1024 * 1024))  # 10MB
    backup_count = int(getattr(settings.logging, "backup_count", 5))
    fh = RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
    fh.setLevel(getattr(settings.logging, "file_level", settings.logging.level))
    fh.setFormatter(_build_stream_formatter())
    return fh


def get_logger(name: str) -> Logger:
    """建立帶有預設格式的紀錄器。"""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    # level
    level = getattr(settings.logging, "level", "INFO")
    logger.setLevel(level)

    # console
    ch = logging.StreamHandler()
    ch.setLevel(getattr(settings.logging, "console_level", level))
    ch.setFormatter(_build_stream_formatter())
    logger.addHandler(ch)

    # optional file
    fh = _maybe_file_handler()
    if fh:
        logger.addHandler(fh)

    # 不向 root 傳遞，避免重複列印
    logger.propagate = False
    return logger

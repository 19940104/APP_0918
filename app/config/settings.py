"""設定讀取模組，負責整合 YAML 與環境變數。"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import yaml
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = BASE_DIR / "config" / "settings.yaml"


class APISettings(BaseModel):
    """API 相關設定模型。"""

    prefix: str = "/api"
    docs_url: str = "/docs"
    openapi_url: str = "/openapi.json"


class AppSettings(BaseModel):
    """應用程式層級設定。"""

    name: str = "APP 使用分析儀表板"
    environment: str = "development"
    timezone: str = "Asia/Taipei"
    default_locale: str = "zh-TW"


class SourceDBSettings(BaseModel):
    """上游 SQL 資料庫連線設定。"""

    host: str = ""
    database: str = ""
    username: str = ""
    password: str = ""
    driver: str = "ODBC Driver 17 for SQL Server"


class StorageSettings(BaseModel):
    """儲存層設定，含 DuckDB 位置。"""

    duckdb_path: str = "./data/duck_cache.duckdb"
    duckdb_lib_path: str | None = None
    message_table: str = "message_aggregate_daily"
    user_daily_table: str = "user_active_daily"


class ETLTimetable(BaseModel):
    """ETL 執行時間設定。"""

    daily: str = "02:00"
    weekly: str = "03:00"
    monthly: str = "04:00"


class ETLSettings(BaseModel):
    """整體 ETL 設定容器。"""

    batch_times: ETLTimetable = ETLTimetable()


class LoggingSettings(BaseModel):
    """紀錄設定。"""

    level: str = "INFO"


class Settings(BaseModel):
    """總設定模型，提供給應用程式其他模組使用。"""

    app: AppSettings = AppSettings()
    api: APISettings = APISettings()
    source_db: SourceDBSettings = SourceDBSettings()
    etl: ETLSettings = ETLSettings()
    storage: StorageSettings = StorageSettings()
    logging: LoggingSettings = LoggingSettings()

    class Config:
        frozen = True


def _load_yaml_config(path: Path) -> Dict[str, Any]:
    """載入 YAML 設定檔，若不存在則回傳空字典。"""

    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def _apply_env_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
    """以環境變數覆蓋設定值。"""

    storage = config.setdefault("storage", {})
    storage["duckdb_path"] = os.getenv("DUCKDB_PATH", storage.get("duckdb_path"))

    api = config.setdefault("api", {})
    api["prefix"] = os.getenv("API_PREFIX", api.get("prefix", "/api"))

    app_cfg = config.setdefault("app", {})
    app_cfg["environment"] = os.getenv("APP_ENV", app_cfg.get("environment", "development"))

    src_cfg = config.setdefault("source_db", {})
    src_cfg["host"] = os.getenv("APP_HOST", src_cfg.get("host", ""))
    src_cfg["database"] = os.getenv("APP_DB", src_cfg.get("database", ""))
    src_cfg["username"] = os.getenv("APP_USER", src_cfg.get("username", ""))
    src_cfg["password"] = os.getenv("APP_PASSWORD", src_cfg.get("password", ""))
    src_cfg["driver"] = os.getenv("APP_DRIVER", src_cfg.get("driver", "ODBC Driver 17 for SQL Server"))
    return config


@lru_cache
def get_settings() -> Settings:
    """取得設定，使用快取避免重複 IO。"""

    data = _load_yaml_config(CONFIG_PATH)
    merged = _apply_env_overrides(data)
    return Settings.model_validate(merged)


settings = get_settings()



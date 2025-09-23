"""設定讀取模組（新版；對齊強化後的管線與連線/記錄設定）。"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = BASE_DIR / "config" / "settings.yaml"


# =========================
# 設定模型
# =========================
class APISettings(BaseModel):
    prefix: str = "/api"
    docs_url: str = "/docs"
    openapi_url: str = "/openapi.json"


class AppSettings(BaseModel):
    name: str = "APP 使用分析儀表板"
    environment: str = "development"
    timezone: str = "Asia/Taipei"
    default_locale: str = "zh-TW"


class SourceDBSettings(BaseModel):
    """SQL Server 連線設定（對齊強化版 SQLServerSource）。"""
    host: str = ""
    database: str = ""
    username: str = ""
    password: str = ""
    driver: str = "ODBC Driver 17 for SQL Server"

    # 進階選項
    encrypt: str = "no"         # "yes"/"no"
    trust_cert: str = "yes"     # "yes"/"no"
    mars: str = "yes"           # "yes"/"no"
    timeout: int = 5            # login timeout (秒)
    appname: str = "usage-etl"
    query_timeout: int = 60     # 單次查詢逾時 (秒)


class StorageSettings(BaseModel):
    """儲存層設定（DuckDB）。"""
    duckdb_path: str = "./data/duck_cache.duckdb"
    duckdb_lib_path: Optional[str] = None


class ETLTimetable(BaseModel):
    daily: str = "02:00"
    weekly: str = "03:00"
    monthly: str = "04:00"


class ETLSettings(BaseModel):
    batch_times: ETLTimetable = ETLTimetable()
    lookback_days_default: int = 90


class LoggingSettings(BaseModel):
    level: str = "INFO"
    json: bool = False
    use_localtime: bool = False
    file_enabled: bool = False
    file_path: str = "logs/etl.log"
    file_level: Optional[str] = None
    max_bytes: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    console_level: Optional[str] = None


class Settings(BaseModel):
    app: AppSettings = AppSettings()
    api: APISettings = APISettings()
    source_db: SourceDBSettings = SourceDBSettings()
    etl: ETLSettings = ETLSettings()
    storage: StorageSettings = StorageSettings()
    logging: LoggingSettings = LoggingSettings()

    class Config:
        frozen = True


# =========================
# 載入與環境覆寫
# =========================
def _load_yaml_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
        return data if isinstance(data, dict) else {}


def _env(key: str, default: Any) -> Any:
    val = os.getenv(key)
    return default if val is None or val == "" else val


def _apply_env_overrides(cfg: Dict[str, Any]) -> Dict[str, Any]:
    # storage
    storage = cfg.setdefault("storage", {})
    storage_defaults = StorageSettings()
    storage.setdefault("duckdb_path", storage_defaults.duckdb_path)
    storage.setdefault("duckdb_lib_path", storage_defaults.duckdb_lib_path)
    storage["duckdb_path"] = _env("DUCKDB_PATH", storage["duckdb_path"])
    storage["duckdb_lib_path"] = _env("DUCKDB_LIB_PATH", storage.get("duckdb_lib_path"))

    # api
    api = cfg.setdefault("api", {})
    api["prefix"] = _env("API_PREFIX", api.get("prefix", "/api"))
    api["docs_url"] = _env("API_DOCS_URL", api.get("docs_url", "/docs"))
    api["openapi_url"] = _env("API_OPENAPI_URL", api.get("openapi_url", "/openapi.json"))

    # app
    app = cfg.setdefault("app", {})
    app["environment"] = _env("APP_ENV", app.get("environment", "development"))
    app["timezone"] = _env("APP_TIMEZONE", app.get("timezone", "Asia/Taipei"))
    app["default_locale"] = _env("APP_LOCALE", app.get("default_locale", "zh-TW"))

    # source_db（只保留新版環境變數）
    src = cfg.setdefault("source_db", {})
    src["host"] = _env("SOURCE_DB_HOST", src.get("host", ""))
    src["database"] = _env("SOURCE_DB_NAME", src.get("database", ""))
    src["username"] = _env("SOURCE_DB_USER", src.get("username", ""))
    src["password"] = _env("SOURCE_DB_PASSWORD", src.get("password", ""))
    src["driver"] = _env("SOURCE_DB_DRIVER", src.get("driver", "ODBC Driver 17 for SQL Server"))
    src["encrypt"] = _env("SOURCE_DB_ENCRYPT", src.get("encrypt", "no"))
    src["trust_cert"] = _env("SOURCE_DB_TRUST_CERT", src.get("trust_cert", "yes"))
    src["mars"] = _env("SOURCE_DB_MARS", src.get("mars", "yes"))
    src["timeout"] = int(_env("SOURCE_DB_TIMEOUT", src.get("timeout", 5)))
    src["appname"] = _env("SOURCE_DB_APPNAME", src.get("appname", "usage-etl"))
    src["query_timeout"] = int(_env("SOURCE_DB_QUERY_TIMEOUT", src.get("query_timeout", 60)))

    # etl
    etl = cfg.setdefault("etl", {})
    etl.setdefault("batch_times", {})
    bt = etl["batch_times"]
    bt["daily"] = _env("ETL_DAILY_TIME", bt.get("daily", "02:00"))
    bt["weekly"] = _env("ETL_WEEKLY_TIME", bt.get("weekly", "03:00"))
    bt["monthly"] = _env("ETL_MONTHLY_TIME", bt.get("monthly", "04:00"))
    etl["lookback_days_default"] = int(_env("ETL_LOOKBACK_DAYS", etl.get("lookback_days_default", 90)))

    # logging
    log = cfg.setdefault("logging", {})
    log["level"] = _env("LOG_LEVEL", log.get("level", "INFO"))
    log["json"] = str(_env("LOG_JSON", log.get("json", False))).lower() in ("1", "true", "yes")
    log["use_localtime"] = str(_env("LOG_LOCALTIME", log.get("use_localtime", False))).lower() in ("1", "true", "yes")
    log["file_enabled"] = str(_env("LOG_FILE_ENABLED", log.get("file_enabled", False))).lower() in ("1", "true", "yes")
    log["file_path"] = _env("LOG_FILE_PATH", log.get("file_path", "logs/etl.log"))
    log["file_level"] = _env("LOG_FILE_LEVEL", log.get("file_level", log.get("level", "INFO")))
    log["max_bytes"] = int(_env("LOG_MAX_BYTES", log.get("max_bytes", 10 * 1024 * 1024)))
    log["backup_count"] = int(_env("LOG_BACKUP_COUNT", log.get("backup_count", 5)))
    log["console_level"] = _env("LOG_CONSOLE_LEVEL", log.get("console_level", log.get("level", "INFO")))

    return cfg


@lru_cache
def get_settings() -> Settings:
    """取得設定，使用快取避免重複 IO。"""
    data = _load_yaml_config(CONFIG_PATH)
    merged = _apply_env_overrides(data)
    return Settings.model_validate(merged)


settings = get_settings()

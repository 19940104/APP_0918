"""ETL 執行指令列介面。"""

from __future__ import annotations

from datetime import date
from typing import Optional

import typer

from app.etl.pipelines.usage_pipeline import UsageStatsPipeline
from app.etl.storage.duckdb_client import DuckDBClient
from app.etl.storage.schema import initialize_duckdb

app = typer.Typer(help="ETL 工具，提供每日/每週/每月彙整任務。")


def _parse_target_date(raw: Optional[str]) -> Optional[date]:
    """解析使用者輸入的日期字串。"""

    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise typer.BadParameter("日期格式需為 YYYY-MM-DD，例如 2025-09-18") from exc


@app.command("run-usage")
def run_usage(
    target_date: Optional[str] = typer.Option(None, help="指定統計日期 (YYYY-MM-DD)，預設為前一日"),
    full_refresh: bool = typer.Option(False, help="全量重算，忽略僅擷取最近 N 天的限制"),
    lookback_days: int = typer.Option(90, min=1, help="近 N 天資料 (full-refresh 為 True 時忽略)"),
) -> None:
    """執行使用率與訊息量的主 Pipeline。"""

    parsed_date = _parse_target_date(target_date)
    pipeline = UsageStatsPipeline(
        target_date=parsed_date,
        full_refresh=full_refresh,
        lookback_days=lookback_days,
    )
    pipeline.run()


@app.command("run-usage-full")
def run_usage_full(
    target_date: Optional[str] = typer.Option(None, help="指定統計截止日期 (YYYY-MM-DD)，預設為前一日"),
) -> None:
    """全量重算所有歷史資料。"""

    parsed_date = _parse_target_date(target_date)
    pipeline = UsageStatsPipeline(target_date=parsed_date, full_refresh=True)
    pipeline.run()


@app.command("init-duckdb")
def init_duckdb(path: Optional[str] = typer.Option(None, help="自訂 DuckDB 檔案路徑")) -> None:
    """建立 DuckDB Schema。"""

    client = DuckDBClient(db_path=path)
    initialize_duckdb(client)
    client.close()


if __name__ == "__main__":
    app()

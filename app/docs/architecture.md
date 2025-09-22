# 架構設計說明

## 整體流程

1. **ETL 抽取**：`UsageStatsPipeline` 透過 `SQLServerSource` 擷取員工、啟用、訊息資料。
2. **轉換彙總**：使用 pandas 計算週使用率、日活躍、訊息 20/60/20 分布、Top10 排行與啟用/留存。
3. **寫入快取**：結果存入 DuckDB 表格（`user_active_daily`、`message_aggregate_daily` 等），供後端高效率查詢。
4. **API 提供**：FastAPI 後端使用 `DashboardRepository` 查詢 DuckDB，經 `DashboardService`&`DashboardController` 封裝為 API。
5. **前端呈現**：Streamlit 前端透過 REST API 取得資料並轉為互動圖表。

## 模組分層

- **ETL Pipeline**：支援 `lookback_days` 與 `full_refresh` 參數，既可執行每日增量，也能一鍵全量重算，`run-usage-full` 指令即為封裝全量模式。
- **config**：負責設定檔載入與環境變數覆寫。
- **etl**：包含資料來源 (`sources`)、儲存層 (`storage`)、管線 (`pipelines`) 與工具 (`utils`)。
- **backend**：遵循 MVC。`repositories` -> `services` -> `controllers` -> `routes`。
- **frontend**：以 Streamlit 原型展示資料，未來可替換為 React、Dash 等。

## 資料庫設計

DuckDB 表格皆為寬表，方便前端直接取用：

| 表名 | 內容 |
| ---- | ---- |
| `user_active_daily` | 日活躍、總員工數與活躍率 (`active_rate`) |
| `usage_rate_weekly` | 全公司與部門週使用率 |
| `message_aggregate_daily` | 訊息量、活躍發送者與人均訊息 |
| `message_distribution_20_60_20` | 20/60/20 分布資料 |
| `message_leaderboard` | Top 10 使用者排行 |
| `activation_monthly` | 啟用/留存與對應比率 |

`app/etl/storage/schema.py` 集中維護建表語法，可透過 `python -m app.etl.cli init-duckdb` 重新建立。

## 排程建議

- 日批：每日 02:00 執行 `run-usage`，更新日活躍與訊息趨勢。
- 週批：延伸 pipeline 於週一更新週使用率報表。
- 月批：月初重算啟用與留存，並備份舊資料。

## 監控與維護

- 加入 `rich` 或 `loguru` 強化紀錄，可匯出至 ELK。
- DuckDB 檔案建議定期備援，並監控檔案大小。
- 若資料量升高，可考慮以分區表或 Iceberg/Delta Lake 儲存歷史資料。

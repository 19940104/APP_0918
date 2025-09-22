# APP 使用分析儀表板

此專案提供 App/Web 推廣成效追蹤所需的 ETL 管線、FastAPI 後端與 Streamlit 前端原型。資料彙整後儲存於 DuckDB 1.2.0，並以模組化架構方便維護與擴充。

## 快速開始

1. **建立虛擬環境與安裝套件**

   ```powershell
   # Windows PowerShell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

   或使用腳本：`powershell app/scripts/setup_env.ps1`

2. **設定環境變數**

   - 複製 `.env.example` 為 `.env`。
   - 依序填入 APP 資料庫連線資訊：`APP_HOST`、`APP_DB`、`APP_USER`、`APP_PASSWORD`、`APP_DRIVER`。
   - 若需自訂 DuckDB 檔案路徑，更新 `DUCKDB_PATH`。

3. **初始化 DuckDB Schema**

   ```powershell
   python -m app.etl.cli init-duckdb
   # 或指定自訂路徑
   python -m app.etl.cli init-duckdb --path .\data\custom.duckdb
   ```

4. **執行 ETL 管線**

   ```powershell
   # 預設抓取「昨日為止、近 90 天」資料
   python -m app.etl.cli run-usage

   # 指定統計截止日期
   python -m app.etl.cli run-usage --target-date 2025-09-18

   # 全量重算所有歷史資料（首次建檔或需要重建時）
   python -m app.etl.cli run-usage-full
   ```

   `run-usage` 也提供 `--full-refresh` 與 `--lookback-days` 參數，可依需求微調範圍。

5. **啟動後端 API**

   ```powershell
   uvicorn app.backend.app.main:app --reload
   ```

6. **啟動前端儀表板**

   ```powershell
   $env:DASHBOARD_API = "http://127.0.0.1:8000/api/dashboard"
   streamlit run app/frontend/streamlit_app.py
   ```

## 每日排程（Windows 範例）

若希望每日 00:00 自動匯入最新資料，可建立排程工作：

```powershell
schtasks /Create `
  /TN "APP Usage ETL" `
  /TR 'cmd /c "cd /d D:\My Documents\rene-lin\桌面\APP_0918 && .venv\Scripts\python.exe -m app.etl.cli run-usage"' `
  /SC DAILY /ST 00:00
```

- 若路徑含空白，請確保使用單引號或以 `"` 包起完整指令。
- Task Scheduler 會在排程時間啟動 `run-usage`，預設抓取前一日的資料。

## 專案架構

```
APP_0918/
├── app/
│   ├── backend/          # FastAPI MVC 模組
│   ├── config/           # 設定檔與讀取工具
│   ├── docs/             # 文件
│   ├── etl/              # ETL 管線、來源與儲存層
│   ├── frontend/         # Streamlit 原型
│   ├── scripts/          # 自動化腳本
│   └── tests/            # Pytest 測試
├── data/                 # DuckDB 檔案存放位置
├── requirements.txt      # 依賴套件 (含 DuckDB 1.2.0)
├── pyproject.toml        # 格式化工具設定
└── README.md
```

## 模組重點

- **ETL (`app/etl`)**：`UsageStatsPipeline` 會從 APP SQL 資料庫取出原始資料，計算使用率、訊息量、20/60/20 分布與啟用留存，再寫入 DuckDB。
- **後端 (`app/backend/app`)**：採 MVC 分層，`repositories` 封裝資料庫查詢，`services` 處理商業邏輯，`controllers` 將資料轉換成 `schemas`，`routes` 提供 REST API。
- **前端 (`app/frontend`)**：`streamlit_app.py` 呼叫後端 API，展示 KPI、趨勢圖與排行榜，可作為實際前端開發的雛型。

## 測試

```powershell
python -m pytest
```

單元測試涵蓋 ETL 轉換邏輯與 API 路由回應結構。可依需求再擴充整合測試。

## 後續建議

- 依資料量調整 SQL 查詢索引與 DuckDB 分區策略。
- 新增 Airflow / Prefect 等排程工具整合。
- 串接 AD/SSO 作為 API 權限控管。
- 若訊息量龐大，可規劃歷史資料切分至獨立 DuckDB 檔案或物件儲存。

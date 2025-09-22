# Frontend 指南

此資料夾提供以 Streamlit 為基礎的儀表板原型。未來若改用 React / Vue，可沿用 API 介面。

## 目前檔案

- `streamlit_app.py`：示範如何呼叫 FastAPI，並以 Plotly 圖表呈現 KPI、使用趨勢、訊息分析與啟用留存。

## 執行方式

```powershell
streamlit run app/frontend/streamlit_app.py
```

可透過環境變數 `DASHBOARD_API` 指定後端 API 位置，預設為 `http://localhost:8000/api/dashboard`。

## 視覺化建議

- KPI 卡片可替換為自訂元件，標示資料更新頻率。
- 週使用率與部門比較可加入篩選器（部門、多選時間區間）。
- 20/60/20 分布建議搭配累積曲線，凸顯集中度。
- Top 10 排行可連結至使用者明細頁。



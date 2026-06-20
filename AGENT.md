# InvestmentTool 接手筆記

## 協作規範

- 每次對話中只要有異動檔案，就將所有 Git local changes 一起進行 Git commit。

## 專案概覽

這是一個 Streamlit 投資儀表板。主畫面會讀取 watchlist，抓取 yfinance 即時價格與歷史資料，並用卡片或列表顯示標的、評分、標籤、持倉成本、損益和外部連結。

主要資料來源是 Supabase PostgreSQL。本地的 `watchlist.json` 和 `settings.json` 仍保留為開發與雲端暫時斷線時的備援，但不應提交到 Git。

## 重要檔案

- `app.py`：Streamlit 主程式，包含畫面、篩選、排序、設定、資料預抓和 yfinance 快取。
- `watchlist_manager.py`：watchlist 與 Supabase 存取層，也負責股票名稱 mapping。
- `sparkline.py`：產生 inline SVG sparkline。
- `tw_stock_map.json` / `us_stock_map.json`：新增標的搜尋用的代號對照表。
- `migrate_to_supabase.py`：把本地 JSON 匯入 Supabase 的一次性工具。
- `backup_supabase_local.py`：把 Supabase 的 `watchlist`、`settings` 拉回本機 SQLite 表格備份。
- `check_data.py`：快速測試 yfinance 是否能抓資料。
- `test_sort.py`：streamlit-sortables 的小型測試頁。
- `DEPLOYMENT_GUIDE.md`：部署與 Supabase 遷移筆記，但目前部分中文內容已出現 mojibake，修改時要小心編碼。

## 本地執行

1. 建立虛擬環境並安裝套件：

   ```powershell
   pip install -r requirements.txt
   ```

2. 準備 `.streamlit/secrets.toml`：

   ```toml
   [supabase]
   url = "https://your-project.supabase.co"
   key = "your-anon-public-key"
   ```

3. 啟動 Streamlit：

   ```powershell
   streamlit run app.py
   ```

## 資料與快取

- `wm.load_watchlist()` 使用 `st.cache_data(ttl=30)`，正常情況每 30 秒最多打一次 Supabase。
- yfinance 價格與歷史資料快取在 `app.py`，目前多數 TTL 是 60 秒。
- `wm.get_supabase()` 使用 `st.cache_resource` 快取 Supabase client。
- 寫入 watchlist 後會呼叫 `invalidate_watchlist_cache()` 清掉 watchlist cache。

## Supabase 連線故障處理

曾遇到 Streamlit Cloud app 閒置一段時間後，第一次開啟時在 `wm.load_watchlist()` 發生 `httpx.ConnectError`，導致整個頁面無法載入。現在資料層會：

- Supabase request 失敗時清掉 cached client。
- 用新的 client 重試數次。
- 如果讀取 watchlist 仍失敗，回退到本地 `watchlist.json`，讓頁面至少可以打開。
- 在 UI 顯示暫時使用本地備份的提示。
- 工具列刷新按鈕會同步清掉 yfinance cache、watchlist cache 和 Supabase client cache。

如果雲端仍持續出現連線錯誤，優先檢查 Streamlit Cloud secrets、Supabase 專案狀態、Supabase API URL/anon key，以及 Streamlit Cloud logs 裡的實際例外。

## 本地 SQLite 備份

可以從 Supabase 拉資料到本機 SQLite：

```powershell
python backup_supabase_local.py
```

Windows 一鍵備份可以直接雙擊：

```powershell
backup_local.bat
```

預設會建立 `local_backups/investmenttool_backup.sqlite`，包含：

- `watchlist`：目前雲端 watchlist 的完整快照。
- `settings`：目前雲端 settings 的完整快照。
- `backup_runs`：每次備份時間、來源 URL 和筆數紀錄。

備份檔與 `local_backups/` 已加入 `.gitignore`，不要提交。當 Supabase 讀取失敗時，app 的 watchlist 備援順序是 SQLite 備份優先，其次才是舊的 `watchlist.json`。

## 開發注意事項

- 不要提交 `.streamlit/secrets.toml`、`watchlist.json`、`settings.json`。
- `app.py` 目前有使用者新增的工具列刷新按鈕，修改 toolbar 時要保留。
- `watchlist_manager.py` 原先有一些既有註解是 mojibake；這次已把資料層註解改成可讀版本。
- 若要調整資料表 schema，需同步更新 `migrate_to_supabase.py` 和部署文件。

## 快速驗證

```powershell
python -m py_compile app.py watchlist_manager.py sparkline.py check_data.py test_sort.py
streamlit run app.py
```

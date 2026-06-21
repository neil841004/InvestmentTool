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

## 投資週報生成規範

- 使用者要求「生成週報」、「生成彙報」、「生成匯報」、「生成報告」時，優先使用 `.agents/skills/generate_report/SKILL.md`。
- 週報不是新聞摘要，必須以長期價值投資為核心：每個重點標的要說清楚事件、短期影響、3 年以上 thesis、風險、追蹤指標與本期結論。
- 讀取 `watchlist.json` 時要排除加密貨幣與現金代號；報告不得包含加密貨幣消息。
- 每次生成前都要參考 `reports/` 最新兩份報告，避免配置或觀點無理由大幅跳動。
- 資訊來源要附連結，且優先使用公司公告、IR、交易所、ETF 發行商與具編輯責任的財經媒體；論壇只能作為市場情緒輔助。
- 關注標的覆蓋不能過窄：持有中標的、評分 3 以上標的、近一個月有重大催化或風險的 watchlist 標的都要納入；其餘以觀察池摘要交代。
- 「接下來可關注標的」不限制產業，不能只集中於既有 watchlist 產業。至少提出 20 檔候選，分成核心型、衛星型、早期觀察型，並覆蓋至少 8 個產業面向，例如 AI/半導體、電網電力、資安、醫療醫材、航太國防、水資源環境、金融基礎設施、工業自動化、消費防守、台股特殊機會。
- 對潛力股要說明它是高品質複利股、成長轉折股，還是早期選擇權股；不得只列熱門名稱。
- 週報需加入估值與進場紀律、情境分析、催化日曆、投資組合重疊度，避免只有新聞摘要與主觀推薦。
- 「100% 新資金配置」要做風險分散，原則上不得讓單一個股超過 50%，單一產業主題不宜超過 45%，並保留 5-15% 現金或等待資金，除非估值安全邊際極高。
- 週報檔案存為 `reports/report_YYYY-MM-DD.md`；若同日期檔案已存在且使用者未要求覆蓋，必須另存為 `reports/report_YYYY-MM-DD_主題.md`。使用繁體中文 Markdown，讓 App 的「投資週報」頁面可直接讀取。

## 快速驗證

```powershell
python -m py_compile app.py watchlist_manager.py sparkline.py check_data.py test_sort.py
streamlit run app.py
```

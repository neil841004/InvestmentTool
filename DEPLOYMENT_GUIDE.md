# 投資工具 (Investment Dashboard) 雲端部署指南

> 日期：2026-02-23 | 適用版本：目前 Streamlit 專案

---

## 重要前提：Streamlit 的部署限制

在比較平台之前，必須先了解一個關鍵事實：

**這個專案是 Streamlit Python 應用，不是靜態網頁。**

Streamlit 需要一個**長期運行的 Python 伺服器**（WebSocket 連線），這與 Cloudflare Pages 和 Vercel 的主要設計目標不同——它們是為靜態網站和短暫的 Serverless Function 設計的。

---

## 平台比較

### 方案一：Vercel

| 項目 | 說明 |
|------|------|
| **Streamlit 支援** | ⚠️ 不原生支援。需要將 Streamlit 包裝成 ASGI/WSGI，且有 10 秒執行時間限制，**實際上不可行** |
| **Python 支援** | 支援 Python Serverless Function，但不適合長連線應用 |
| **免費方案** | 有，但有請求次數和執行時間限制 |
| **資料庫整合** | 支援 Vercel Postgres、Supabase、MongoDB |
| **難度** | 高（需要大量改寫）|
| **適合此專案** | ❌ 不建議 |

**結論：** Vercel 部署 Streamlit 需要複雜的 Hack，且 WebSocket 支援極差，不適合本專案。

---

### 方案二：Cloudflare Pages

| 項目 | 說明 |
|------|------|
| **Streamlit 支援** | ❌ 完全不支援。Pages 只支援靜態網站 + Cloudflare Workers（JavaScript/WASM） |
| **Python 支援** | Workers 開始支援 Python，但非常有限，不支援 Streamlit |
| **免費方案** | 有，靜態資源無限制 |
| **資料庫整合** | Cloudflare D1 (SQLite)、KV Store、R2 (S3-like) |
| **難度** | 極高（幾乎需要整個專案重寫）|
| **適合此專案** | ❌ 完全不建議 |

**結論：** Cloudflare Pages 根本無法直接部署 Streamlit，除非把整個前端和後端全部重寫。

---

### 方案三（推薦）：Streamlit Community Cloud

| 項目 | 說明 |
|------|------|
| **Streamlit 支援** | ✅ 100% 原生支援，專為 Streamlit 設計 |
| **Python 支援** | ✅ 完整支援所有 Python 套件 |
| **免費方案** | ✅ **個人使用完全免費**，無時間限制 |
| **部署方式** | 連接 GitHub 倉庫，一鍵部署 |
| **自動更新** | Push 到 GitHub 自動重新部署 |
| **難度** | 極低（約 10 分鐘可完成）|
| **適合此專案** | ✅ **最佳選擇** |

**唯一限制：** App 長時間無人使用會進入休眠（訪問時需等待幾秒重新啟動）。個人使用幾乎沒有影響。

---

### 方案四（備選）：Railway

| 項目 | 說明 |
|------|------|
| **Streamlit 支援** | ✅ 支援（容器化部署）|
| **免費方案** | 每月 $5 免費額度（個人使用通常夠用）|
| **部署方式** | GitHub 連接，自動部署 |
| **不會休眠** | ✅ 24/7 運行 |
| **難度** | 低 |
| **適合此專案** | ✅ 如果不想 App 休眠，選這個 |

---

## 雲端資料庫比較

目前專案的資料存在 `watchlist.json` 和 `settings.json`，部署到雲端後需要遷移到雲端資料庫（因為雲端平台的檔案系統是暫時性的）。

### 資料庫方案比較

| 資料庫 | 類型 | 免費限制 | 適合度 | 難度 |
|--------|------|----------|--------|------|
| **Supabase** | PostgreSQL | 500MB，無限請求 | ⭐⭐⭐⭐⭐ | 低 |
| **Firebase Firestore** | NoSQL (JSON-like) | 1GB，50K 讀/天 | ⭐⭐⭐⭐ | 低 |
| **MongoDB Atlas** | NoSQL (JSON-like) | 512MB | ⭐⭐⭐⭐ | 中 |
| **PlanetScale** | MySQL | 已關閉免費方案 | ❌ | - |
| **Neon** | PostgreSQL (Serverless) | 免費，3GB | ⭐⭐⭐ | 中 |

---

## 最終推薦方案

```
部署平台：Streamlit Community Cloud（免費）
雲端資料庫：Supabase（免費）
```

**選擇理由：**
1. **完全免費**，個人使用不需要花費任何費用
2. **設定最簡單**，不需要修改大量程式碼
3. **Supabase** 有優秀的 Python SDK，且資料結構（JSON 陣列）可以直接對應到 PostgreSQL 表格
4. 兩者都有良好的 GitHub 整合

---

## 實際操作步驟

---

### 第一步：準備 GitHub 倉庫

確保你的 `watchlist.json`、`settings.json` 不在 `.gitignore` 中（但之後資料移到資料庫後就不需要了）。

---

### 第二步：設定 Supabase 資料庫

#### 2.1 建立 Supabase 帳號和專案

1. 前往 [supabase.com](https://supabase.com)
2. 點擊 **Start your project**，用 GitHub 登入
3. 點擊 **New Project**
4. 填寫：
   - **Project name**：`InvestmentTool`
   - **Database Password**：設定一個強密碼（記下來）
   - **Region**：選 `Northeast Asia (Tokyo)` 距離台灣最近
5. 等待約 2 分鐘建立完成

#### 2.2 建立資料表

在 Supabase 後台，點擊左側 **SQL Editor**，貼上以下 SQL 並執行：

```sql
-- 建立 watchlist 資料表
CREATE TABLE watchlist (
    id SERIAL PRIMARY KEY,
    ticker TEXT NOT NULL UNIQUE,
    custom_name TEXT DEFAULT '',
    note TEXT DEFAULT '',
    rating INTEGER DEFAULT 0,
    holding BOOLEAN DEFAULT false,
    yahoo_url TEXT DEFAULT '',
    tradingview_url TEXT DEFAULT '',
    avg_cost FLOAT DEFAULT 0.0,
    shares FLOAT DEFAULT 0.0,
    tags JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 建立 settings 資料表
CREATE TABLE settings (
    id INTEGER PRIMARY KEY DEFAULT 1,
    refresh_interval INTEGER DEFAULT 60,
    tag_colors JSONB DEFAULT '{}'::jsonb
);

-- 插入預設 settings（確保只有一筆）
INSERT INTO settings (id, refresh_interval, tag_colors)
VALUES (1, 60, '{}'::jsonb)
ON CONFLICT (id) DO NOTHING;
```

#### 2.3 取得連線資訊

1. 點擊左側 **Settings** → **API**
2. 複製以下資訊（等一下要用）：
   - **Project URL**：`https://xxxxxxxxxxxx.supabase.co`
   - **anon public key**：`eyJ...` 很長的字串

---

### 第三步：修改程式碼以使用 Supabase

#### 3.1 安裝 Supabase Python SDK

在本地終端執行：
```bash
pip install supabase
```

#### 3.2 建立 secrets 設定檔

在專案根目錄建立 `.streamlit/secrets.toml`（**這個檔案不能上傳到 GitHub！**）：

```toml
[supabase]
url = "https://xxxxxxxxxxxx.supabase.co"
key = "eyJ你的anon-public-key"
```

確認 `.gitignore` 包含：
```
.streamlit/secrets.toml
```

#### 3.3 修改 `watchlist_manager.py`

找到目前讀取/寫入 JSON 的函式，替換為 Supabase 版本。

主要改動原理：
- `load_watchlist()` → 從 Supabase 的 `watchlist` 表讀取
- `save_watchlist()` → 寫入 Supabase
- `add_ticker_to_watchlist()` → INSERT
- `remove_ticker_from_watchlist()` → DELETE
- `update_ticker_data()` → UPDATE

範例程式碼（`watchlist_manager.py` 改寫版）：

```python
import streamlit as st
from supabase import create_client, Client

def get_supabase() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

def load_watchlist():
    sb = get_supabase()
    response = sb.table("watchlist").select("*").order("id").execute()
    return response.data or []

def save_watchlist(data):
    # 批次更新，使用 upsert
    sb = get_supabase()
    sb.table("watchlist").upsert(data).execute()

def add_ticker_to_watchlist(ticker):
    sb = get_supabase()
    # 檢查是否已存在
    existing = sb.table("watchlist").select("ticker").eq("ticker", ticker).execute()
    if existing.data:
        return False, f"{ticker} already in watchlist"
    sb.table("watchlist").insert({"ticker": ticker}).execute()
    return True, f"Added {ticker}"

def remove_ticker_from_watchlist(ticker):
    sb = get_supabase()
    sb.table("watchlist").delete().eq("ticker", ticker).execute()

def update_ticker_data(ticker, note, rating, yahoo_url, tradingview_url, avg_cost, shares, tags, custom_name):
    sb = get_supabase()
    sb.table("watchlist").update({
        "note": note,
        "rating": rating,
        "yahoo_url": yahoo_url,
        "tradingview_url": tradingview_url,
        "avg_cost": avg_cost,
        "shares": shares,
        "tags": tags,
        "custom_name": custom_name,
        "holding": avg_cost > 0 and shares > 0
    }).eq("ticker", ticker).execute()
```

#### 3.4 修改 `app.py` 的 settings 部分

將 `load_settings()` 和 `save_settings()` 改為使用 Supabase：

```python
def load_settings():
    if 'settings' in st.session_state:
        return st.session_state.settings
    sb = get_supabase()  # 從 watchlist_manager import
    response = sb.table("settings").select("*").eq("id", 1).execute()
    if response.data:
        s = response.data[0]
        st.session_state.settings = s
        return s
    st.session_state.settings = {"refresh_interval": 60, "tag_colors": {}}
    return st.session_state.settings

def save_settings(settings):
    st.session_state.settings = settings
    sb = get_supabase()
    sb.table("settings").update(settings).eq("id", 1).execute()
```

#### 3.5 遷移現有資料

在本地執行以下 Python 腳本，把現有的 watchlist.json 資料匯入 Supabase：

```python
# migrate_to_supabase.py
import json
from supabase import create_client

SUPABASE_URL = "https://xxxxxxxxxxxx.supabase.co"
SUPABASE_KEY = "eyJ你的key"

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# 匯入 watchlist
with open("watchlist.json", "r") as f:
    data = json.load(f)

for item in data:
    # 確保欄位存在
    item.setdefault("custom_name", "")
    item.setdefault("note", "")
    item.setdefault("tags", [])

    sb.table("watchlist").upsert(item).execute()
    print(f"Migrated: {item['ticker']}")

# 匯入 settings
with open("settings.json", "r") as f:
    settings = json.load(f)

sb.table("settings").update(settings).eq("id", 1).execute()
print("Settings migrated!")
print("Migration complete!")
```

執行：
```bash
python migrate_to_supabase.py
```

---

### 第四步：更新 requirements.txt

在專案根目錄建立或更新 `requirements.txt`：

```txt
streamlit>=1.40.0
yfinance>=0.2.48
pandas>=2.0.0
plotly>=5.18.0
supabase>=2.3.0
streamlit-sortables>=0.3.0
streamlit-tags>=1.2.8
```

執行以下指令確認版本（在本地終端）：
```bash
pip freeze | grep -E "streamlit|yfinance|pandas|plotly|supabase"
```

---

### 第五步：部署到 Streamlit Community Cloud

#### 5.1 確認 GitHub 倉庫

確認你的程式碼已經推送到 GitHub，且 `.gitignore` 正確設定：

```
# .gitignore 必須包含
.streamlit/secrets.toml
.venv/
__pycache__/
*.pyc
watchlist.json    # 資料已遷移到 Supabase，不再需要這個
settings.json     # 同上
```

#### 5.2 建立 Streamlit Cloud 帳號

1. 前往 [share.streamlit.io](https://share.streamlit.io)
2. 用 GitHub 帳號登入

#### 5.3 新建 App

1. 點擊 **New app**
2. 填寫：
   - **Repository**：選擇你的 GitHub 倉庫
   - **Branch**：`main`
   - **Main file path**：`app.py`
3. 點擊 **Advanced settings**
4. 在 **Secrets** 欄位貼上：
   ```toml
   [supabase]
   url = "https://xxxxxxxxxxxx.supabase.co"
   key = "eyJ你的anon-public-key"
   ```
5. 點擊 **Deploy!**

#### 5.4 等待部署完成

- 首次部署需要 2-5 分鐘安裝套件
- 部署完成後會提供一個 URL，例如：`https://你的名字-investmenttool-app-xxxx.streamlit.app`

---

## 安全性注意事項

由於只有你個人使用，以下設定足夠：

1. **Supabase Row Level Security (RLS)**：目前可以先不啟用（免費帳號預設關閉），因為 `anon key` 只有你知道
2. **Streamlit 存取控制**：在 Streamlit Cloud 設定中，可以將 App 設定為 **Private**（只有登入的你才能訪問）
   - 進入 App 設定 → **Sharing** → 選擇 **Only specific people can view this app** → 填入你的 email

---

## 費用總結

| 服務 | 費用 |
|------|------|
| Streamlit Community Cloud | **$0/月** |
| Supabase 免費方案 | **$0/月** |
| **總計** | **$0/月** |

---

## 快速參考：常見問題

**Q: App 打開很慢？**
A: Streamlit Cloud 免費版會讓 App 休眠，第一次訪問需等待 20-30 秒重新啟動。這是正常現象。

**Q: 資料會不會不見？**
A: 不會。資料存在 Supabase，Streamlit Cloud 只是運行程式碼，不儲存資料。

**Q: 怎麼更新程式碼？**
A: 直接 push 到 GitHub，Streamlit Cloud 會自動重新部署。

**Q: Supabase 資料需要備份嗎？**
A: 建議定期在 Supabase 後台 → **Table Editor** 手動匯出 CSV 備份。

---

*文件生成時間：2026-02-23*

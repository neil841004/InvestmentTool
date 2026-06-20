import streamlit as st
import yfinance as yf
import pandas as pd
import json
import time
import hashlib
import plotly.graph_objects as go
import watchlist_manager as wm
from sparkline import create_sparkline

# --- Settings Management ---

def load_settings():
    if 'settings' in st.session_state:
        return st.session_state.settings
    s = {"refresh_interval": 60, "tag_colors": {}, "default_period": "1M"}
    
    # 嘗試載入本機端 JSON 記錄的擴展設定 (主要為 default_period)
    try:
        import os, json
        if os.path.exists("settings.json"):
             with open("settings.json", "r", encoding="utf-8") as f:
                  local_s = json.load(f)
                  s.update(local_s)
    except Exception:
        pass

    # 嘗試載入 Supabase 上的主設定
    try:
        raise RuntimeError("Supabase storage disabled")
        response = sb.table("settings").select("*").eq("id", 1).execute()
        if response.data:
            row = response.data[0]
            if "refresh_interval" in row: s["refresh_interval"] = row["refresh_interval"]
            if "tag_colors" in row: s["tag_colors"] = row["tag_colors"]
            if "default_period" in row: s["default_period"] = row["default_period"]
    except Exception:
        pass
        
    st.session_state.settings = s
    return s

def save_settings(settings):
    st.session_state.settings = settings
    # 1. 存入本機 JSON 以防 Supabase schema 未開新欄位
    try:
        import json
        with open("settings.json", "w", encoding="utf-8") as f:
             json.dump(settings, f)
    except Exception:
        pass

    # 2. 寫回 Supabase
    try:
        raise RuntimeError("Supabase storage disabled")
        try:
            sb.table("settings").update({
                "refresh_interval": settings.get("refresh_interval", 60),
                "tag_colors": settings.get("tag_colors", {}),
                "default_period": settings.get("default_period", "1M"),
            }).eq("id", 1).execute()
        except:
            sb.table("settings").update({
                "refresh_interval": settings.get("refresh_interval", 60),
                "tag_colors": settings.get("tag_colors", {}),
            }).eq("id", 1).execute()
    except Exception:
        pass

# --- 設定頁面 ---
def load_settings():
    if 'settings' in st.session_state:
        return st.session_state.settings
    settings = wm.load_settings()
    st.session_state.settings = settings
    return settings


def save_settings(settings):
    st.session_state.settings = settings
    wm.save_settings(settings)


st.set_page_config(layout="wide", page_title="Investment Dashboard v2", initial_sidebar_state="expanded")

# --- 全域載入動畫 (Loading Spinner) ---
spinner_placeholder = st.empty()
spinner_placeholder.markdown(
    """
    <style>
    .global-loader-wrapper {
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        z-index: 99999;
        display: flex;
        justify-content: center;
        align-items: center;
        background-color: rgba(14, 17, 23, 0.3);
        pointer-events: none;
    }
    .global-loader {
        width: 70px;
        height: 70px;
        border: 7px solid #1E1E1E;
        border-top: 7px solid #00E676;
        border-radius: 50%;
        animation: global-spin 1s linear infinite;
        box-shadow: 0 0 20px rgba(0, 0, 0, 0.5);
    }
    @keyframes global-spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    </style>
    <div class="global-loader-wrapper">
        <div class="global-loader"></div>
    </div>
    """,
    unsafe_allow_html=True
)

# --- CSS 樣式 ---
st.markdown("""
<style>
    .stApp { background-color: #0E1117; }
    /* 隱藏原生 Streamlit 右側選單與部署按鈕，但保留左側 Sidebar 展開按鈕 (Header) */
    #MainMenu {visibility: hidden;}
    .stDeployButton {display:none !important;}
    .stAppDeployButton {display:none !important;}
    header[data-testid="stHeader"] {
        background: transparent !important;
    }
    
    /* 隱藏頁尾 */
    footer {visibility: hidden;}
    
    /* 弱化幣別字體 */
    .curr-sym { font-size: 0.6em; color: gray; margin-right: 2px; }
    
    /* 市場顏色定義 */
    .market-tw { border-left: 5px solid #00C853 !important; }
    .market-us { border-left: 5px solid #FF3D00 !important; }
    .market-crypto { border-left: 5px solid #FFD600 !important; }
    
    /* 卡片容器 */
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] {
        background-color: #1E1E1E;
        border-radius: 10px;
        padding: 5px;
    }

    /* RWD 對於卡片顯示區域 */
    div[data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
    }
    
    /* When inside card view, ensure columns have a minimum width to enable wrapping */
    div[data-testid="stElementContainer"]:has(.card-grid-marker) ~ div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
        min-width: 300px !important;
        flex: 1 1 300px !important;
        max-width: none !important; /* Override Streamlit's fixed 20% max-width */
    }
    
    /* 隱藏 Popover 按鈕自帶的向下箭頭 (包含 SVG 與 Material Symbols) */
    div[data-testid="stPopover"] button svg,
    div[data-testid="stPopover"] button span.material-symbols-rounded {
        display: none !important;
    }
    
    /* 放大 Popover 彈窗的範圍 */
    div[data-testid="stPopoverBody"] {
        min-width: 450px !important;
    }
    
    /* 隱藏圖片預設的全螢幕放大按鈕 (雙重保險 Selector) */
    button[title="View fullscreen"], [data-testid="StyledFullScreenButton"] {
        display: none !important;
    }
    
    /* 讓緊接在 anchor 後面的按鈕容器變成相對定位，並往下覆蓋原本的位置 */
    div[data-testid="element-container"]:has(.zoom-btn-anchor) {
        display: none !important; /* 隱藏 anchor 本身佔據的空間 */
    }
    
    div[data-testid="element-container"]:has(.zoom-btn-anchor) + div[data-testid="element-container"] {
        margin-bottom: -32px !important;
        position: relative;
        z-index: 10;
        display: flex;
        justify-content: flex-end; /* 右對齊 */
        pointer-events: none;
    }
    
    div[data-testid="element-container"]:has(.zoom-btn-anchor) + div[data-testid="element-container"] button {
        pointer-events: auto;
        padding: 0px !important;
        min-height: 24px !important;
        height: 24px !important;
        width: 32px !important;
        background-color: rgba(30, 30, 30, 0.7) !important;
        border: 1px solid #444 !important;
        color: white !important;
        font-size: 0.9rem !important;
        border-radius: 4px;
        margin-right: 5px;
        margin-top: 5px;
    }
    
    div[data-testid="element-container"]:has(.zoom-btn-anchor) + div[data-testid="element-container"] button:hover {
        background-color: rgba(60, 60, 60, 0.9) !important;
        border-color: #666 !important;
    }
    .price-text { font-size: 1.4rem; font-weight: bold; color: white; }
    .change-pos { color: #FF3D00; font-weight: bold; }
    .change-neg { color: #00C853; font-weight: bold; }
    
    .star-filled { color: gold; font-size: 1.2rem; margin-right: 2px; }
    .star-empty { color: grey; font-size: 1.2rem; margin-right: 2px; }
    
    a.crypto-link { color: #4da6ff; text-decoration: none; font-size: 0.9rem; margin-right: 15px; }
    a.crypto-link:hover { text-decoration: underline; }
    
    .holding-profit {
        font-size: 1.0rem;
        font-weight: bold;
        margin-top: 10px;
        margin-bottom: 5px;
        background-color: rgba(255, 255, 255, 0.05);
        padding: 8px 12px;
        border-radius: 6px;
    }
    
    .tag-badge {
        display: inline-block;
        padding: 2px 8px;
        margin-right: 5px;
        margin-top: 5px;
        border-radius: 12px;
        color: white;
        font-size: 0.8rem;
    }
    
    .sortable-handle {
        cursor: grab;
        font-size: 1.2rem;
        color: grey;
        padding: 0 10px;
    }
    .sortable-handle:active {
        cursor: grabbing;
    }
    
    /* ===== 固定頂部工具列 ===== */
    /* 隱藏 toolbar-marker 本身不佔空間 */
    div[data-testid="stElementContainer"]:has(.toolbar-marker) {
        display: none !important;
    }
    /* 工具列 = toolbar-marker 後面的第一個 stHorizontalBlock */
    div[data-testid="stElementContainer"]:has(.toolbar-marker) + div[data-testid="stHorizontalBlock"] {
        position: sticky !important;
        top: 0px !important;
        z-index: 100 !important;
        background-color: #161b22 !important;
        border-bottom: 1px solid #30363d !important;
        padding: 6px 12px !important;
        margin-left: -1rem !important;
        margin-right: -1rem !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.5) !important;
    }
    
    /* ===== Filter 按鈕左右對齊 ===== */
    /* 讓 sidebar 所有 filter 按鈕（tag, holding, rating）style 正確 */
    div[data-testid="stElementContainer"]:has(.tag-marker) + div[data-testid="stElementContainer"] button {
        width: 100% !important;
        padding-left: 14px !important;
        padding-right: 14px !important;
    }
    /* button 內部 span/div 全部滿寬 */
    div[data-testid="stElementContainer"]:has(.tag-marker) + div[data-testid="stElementContainer"] button > * {
        width: 100% !important;
        display: flex !important;
        align-items: center !important;
    }
    div[data-testid="stElementContainer"]:has(.tag-marker) + div[data-testid="stElementContainer"] button span,
    div[data-testid="stElementContainer"]:has(.tag-marker) + div[data-testid="stElementContainer"] button div[data-testid="stMarkdownContainer"] {
        width: 100% !important;
        display: flex !important;
        align-items: center !important;
    }
    div[data-testid="stElementContainer"]:has(.tag-marker) + div[data-testid="stElementContainer"] button p {
        display: flex !important;
        width: 100% !important;
        align-items: center !important;
        margin: 0 !important;
        gap: 4px !important;
    }
    div[data-testid="stElementContainer"]:has(.tag-marker) + div[data-testid="stElementContainer"] button p code {
        margin-left: auto !important;
        background: transparent !important;
        border: none !important;
        color: inherit !important;
        font-size: 0.9em !important;
        font-weight: bold !important;
        padding: 0 !important;
        opacity: 0.85 !important;
        white-space: nowrap !important;
    }
    
    /* ===== 固定左下角 Clear Filters 按鈕 ===== */
    div[data-testid="stElementContainer"]:has(.clear-filter-marker) {
        display: none !important;
    }
    div[data-testid="stElementContainer"]:has(.clear-filter-marker) + div[data-testid="stElementContainer"] {
        position: fixed !important;
        bottom: 20px !important;
        left: 20px !important;
        z-index: 1000 !important;
        width: calc(20vw - 40px) !important; /* Approximation for sidebar width minus padding */
        min-width: 200px !important;
        max-width: 300px !important;
    }
    div[data-testid="stElementContainer"]:has(.clear-filter-marker) + div[data-testid="stElementContainer"] button {
        box-shadow: 0 4px 12px rgba(0,0,0,0.5) !important;
        border: 1px solid #555 !important;
        background-color: #222 !important;
    }
    div[data-testid="stElementContainer"]:has(.clear-filter-marker) + div[data-testid="stElementContainer"] button:hover {
        background-color: #333 !important;
        border-color: #777 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 輔助函式 ---
def get_market_type(ticker):
    if ".TW" in ticker: return "tw"
    if "-" in ticker: return "crypto"
    return "us"

def get_market_color(mtype):
    if mtype == "tw": return "#00C853"
    if mtype == "us": return "#FF3D00"
    return "#FFD600"

YAHOO_SYMBOL_OVERRIDES = {
    "3184.TW": "3184.TWO",
    "3293.TW": "3293.TWO",
    "3491.TW": "3491.TWO",
}

def get_yahoo_symbol(ticker):
    return YAHOO_SYMBOL_OVERRIDES.get(ticker, ticker)

def get_default_urls(ticker):
    y_url = f"https://tw.stock.yahoo.com/quote/{ticker}"
    if ".TW" in ticker:
        y_url = f"https://tw.stock.yahoo.com/quote/{ticker.replace('.TW', '')}"
        
    tv_sym = ticker
    if ".TW" in ticker:
        tv_sym = f"TWSE-{ticker.replace('.TW', '')}"
    elif "-" in ticker:
        tv_sym = ticker.replace("-", "")
    tv_url = f"https://tw.tradingview.com/symbols/{tv_sym}/"
    return y_url, tv_url

@st.cache_data(ttl=60)
def get_hist_data(ticker, period):
    intervals = {'1D': '5m', '7D': '1h', '1M': '1d', '1Y': '1wk', 'ALL': '1mo'}
    yf_period = {'1D': '1d', '7D': '5d', '1M': '1mo', '1Y': '1y', 'ALL': 'max'}[period]
    
    def fetch_hist(t_sym):
        try:
            return yf.Ticker(t_sym).history(period=yf_period, interval=intervals[period])
        except:
            return pd.DataFrame()
            
    yahoo_symbol = get_yahoo_symbol(ticker)
    df = fetch_hist(yahoo_symbol)
    if df.empty and ticker.endswith(".TW") and yahoo_symbol == ticker:
        # Fallback to .TWO
        df = fetch_hist(ticker.replace(".TW", ".TWO"))
        
    return df

def _normalize_hist_frame(df):
    if df is None or df.empty:
        return pd.DataFrame()

    if isinstance(df.columns, pd.MultiIndex):
        df = df.droplevel(0, axis=1)

    if "Close" not in df.columns and "Adj Close" in df.columns:
        df = df.copy()
        df["Close"] = df["Adj Close"]

    if "Close" not in df.columns:
        return pd.DataFrame()

    return df.dropna(subset=["Close"])

@st.cache_data(ttl=60, show_spinner=False)
def get_hist_data_batch(tickers, period):
    tickers = tuple(dict.fromkeys(str(t).strip() for t in tickers if str(t).strip()))
    if not tickers:
        return {}

    intervals = {'1D': '5m', '7D': '1h', '1M': '1d', '1Y': '1wk', 'ALL': '1mo'}
    yf_period = {'1D': '1d', '7D': '5d', '1M': '1mo', '1Y': '1y', 'ALL': 'max'}[period]

    results = {ticker: pd.DataFrame() for ticker in tickers}
    download_map = {ticker: get_yahoo_symbol(ticker) for ticker in tickers}
    download_symbols = tuple(dict.fromkeys(download_map.values()))
    try:
        raw = yf.download(
            list(download_symbols),
            period=yf_period,
            interval=intervals[period],
            group_by="ticker",
            threads=True,
            progress=False,
            auto_adjust=False,
        )
    except Exception:
        raw = pd.DataFrame()

    if not raw.empty:
        if len(download_symbols) == 1:
            results[tickers[0]] = _normalize_hist_frame(raw)
        elif isinstance(raw.columns, pd.MultiIndex):
            level0 = set(raw.columns.get_level_values(0))
            level1 = set(raw.columns.get_level_values(1))
            for ticker in tickers:
                yahoo_symbol = download_map[ticker]
                try:
                    if yahoo_symbol in level0:
                        results[ticker] = _normalize_hist_frame(raw[yahoo_symbol])
                    elif yahoo_symbol in level1:
                        results[ticker] = _normalize_hist_frame(raw.xs(yahoo_symbol, axis=1, level=1))
                except Exception:
                    results[ticker] = pd.DataFrame()

    fallback_map = {
        ticker: ticker.replace(".TW", ".TWO")
        for ticker in tickers
        if ticker.endswith(".TW") and results[ticker].empty and download_map[ticker] == ticker
    }
    if fallback_map:
        try:
            fallback_raw = yf.download(
                list(fallback_map.values()),
                period=yf_period,
                interval=intervals[period],
                group_by="ticker",
                threads=True,
                progress=False,
                auto_adjust=False,
            )
        except Exception:
            fallback_raw = pd.DataFrame()

        if not fallback_raw.empty:
            if len(fallback_map) == 1:
                original = next(iter(fallback_map))
                results[original] = _normalize_hist_frame(fallback_raw)
            elif isinstance(fallback_raw.columns, pd.MultiIndex):
                level0 = set(fallback_raw.columns.get_level_values(0))
                level1 = set(fallback_raw.columns.get_level_values(1))
                for original, fallback in fallback_map.items():
                    try:
                        if fallback in level0:
                            results[original] = _normalize_hist_frame(fallback_raw[fallback])
                        elif fallback in level1:
                            results[original] = _normalize_hist_frame(fallback_raw.xs(fallback, axis=1, level=1))
                    except Exception:
                        results[original] = pd.DataFrame()

    return results

@st.cache_data(ttl=60)
def get_live_price(ticker):
    def fetch_price(t_sym):
        try:
            t = yf.Ticker(t_sym)
            return t.fast_info.get('lastPrice', None) or t.fast_info.get('currentPrice', None)
        except:
            return None
            
    yahoo_symbol = get_yahoo_symbol(ticker)
    price = fetch_price(yahoo_symbol)
    if price is None and ticker.endswith(".TW") and yahoo_symbol == ticker:
        # Fallback to .TWO
        price = fetch_price(ticker.replace(".TW", ".TWO"))
        
    return price

@st.cache_data(ttl=3600)
def get_usdtwd_rate():
    try:
        t = yf.Ticker("USDTWD=X")
        return t.fast_info.get('lastPrice', 32.0) or 32.0
    except:
        return 32.0

_run_hist_cache = {}
_run_price_cache = {}
_run_usdtwd_rate = None
CARD_PAGE_SIZE = 15

def _latest_close(df):
    if df is None or df.empty or "Close" not in df.columns:
        return None
    close = df["Close"].dropna()
    if close.empty:
        return None
    try:
        return float(close.iloc[-1])
    except Exception:
        return None

def _dedupe_tickers(tickers):
    return tuple(sorted({str(t).strip() for t in tickers if str(t).strip()}))

def prime_hist_data(tickers, period):
    tickers = _dedupe_tickers(tickers)
    missing = [ticker for ticker in tickers if (ticker, period) not in _run_hist_cache]
    if not missing:
        return

    for ticker, df in get_hist_data_batch(tuple(missing), period).items():
        _run_hist_cache[(ticker, period)] = df
        price = _latest_close(df)
        if price is not None:
            _run_price_cache.setdefault(ticker, price)

def get_cached_hist_data(ticker, period):
    key = (ticker, period)
    if key not in _run_hist_cache:
        _run_hist_cache[key] = get_hist_data(ticker, period)
    return _run_hist_cache[key]

def get_cached_live_price(ticker, preferred_period=None):
    if ticker in _run_price_cache:
        return _run_price_cache[ticker]

    periods = [preferred_period, "1D", "7D", "1M", "1Y", "ALL"]
    for period in dict.fromkeys(period for period in periods if period):
        price = _latest_close(_run_hist_cache.get((ticker, period)))
        if price is not None:
            _run_price_cache[ticker] = price
            return price

    price = get_live_price(ticker)
    _run_price_cache[ticker] = price
    return price

def get_cached_usdtwd_rate():
    global _run_usdtwd_rate
    if _run_usdtwd_rate is None:
        _run_usdtwd_rate = get_usdtwd_rate()
    return _run_usdtwd_rate

def calculate_holding_profit(item, live_price):
    avg_cost = item.get('avg_cost', 0.0)
    shares = item.get('shares', 0.0)
    if avg_cost > 0 and shares > 0 and live_price is not None:
        total_cost = avg_cost * shares
        current_val = live_price * shares
        profit = current_val - total_cost
        pct = (profit / total_cost) * 100
        return current_val, pct # Return total value and profit percentage
    return None, None

def render_stars(rating):
    filled = rating
    empty = 5 - rating
    html = ""
    for _ in range(filled): html += "<span class='star-filled'>★</span>"
    for _ in range(empty): html += "<span class='star-empty'>☆</span>"
    return html

def get_tag_color(tag_name):
    settings = st.session_state.get('settings', {})
    custom_colors = settings.get("tag_colors", {})
    if tag_name in custom_colors:
        return custom_colors[tag_name]
    
    # Hash the tag name to a consistent dark color
    hash_object = hashlib.md5(tag_name.encode())
    hue = int(hash_object.hexdigest(), 16) % 360
    # Use HSL for a dark background (saturation 50-70%, lightness 20-30%)
    return f"hsl({hue}, 60%, 25%)"

def render_tags_html(tags):
    tags_html = ""
    for tag in tags:
        color = get_tag_color(tag)
        tags_html += f"<span class='tag-badge' style='background-color: {color};'>{tag}</span>"
    return tags_html

def render_links(item):
    du_y, du_tv = get_default_urls(item['ticker'])
    y_url = item.get('yahoo_url') or du_y
    tv_url = item.get('tradingview_url') or du_tv
    return f"""
        <a href="{y_url}" target="_blank" class="crypto-link">🟣 Yahoo Y!</a>
        <a href="{tv_url}" target="_blank" class="crypto-link">☁️ TradingView TV</a>
    """

# --- Fragment: 及時資料顯示區塊 ---
@st.fragment
def render_live_data(item, period):
    ticker = item['ticker']
    hist = get_cached_hist_data(ticker, period)
    live_p = get_cached_live_price(ticker, preferred_period=period)
    curr_sym = "<span class='curr-sym'>NT$</span>" if get_market_type(ticker) == "tw" else "<span class='curr-sym'>US$</span>"
    
    price_html = "<div style='color:grey'>No Data</div>"
    chart_img = None
    
    if live_p is not None and not hist.empty:
        # Find previous close or start of period for change calculation
        # For 1D, we compare to the first data point of the day
        if len(hist) > 0:
            prev = hist['Close'].iloc[0]
            change = live_p - prev
            pct = (change / prev) * 100 if prev > 0 else 0
            
            color_class = "change-pos" if change >= 0 else "change-neg"
            price_html = f"<div><span class='price-text'>{curr_sym}{live_p:.2f}</span><span class='{color_class}' style='margin-left:8px;'>{change:+.2f} ({pct:+.2f}%)</span></div>"
            
            # chart
            history_list = hist['Close'].dropna().tolist()
            if len(history_list) > 1:
                line_color = '#FF3D00' if change >= 0 else '#00C853'
                chart_img = create_sparkline(history_list, color=line_color)
                
    # Build all HTML in one pass to minimize st.markdown calls
    combined_html = price_html

    if chart_img:
        combined_html += '<span class="zoom-btn-anchor"></span>'

    val, p_pct = calculate_holding_profit(item, live_p)
    holding_html = ""
    if val is not None:
        p_color = "change-pos" if p_pct >= 0 else "change-neg"
        holding_html = f"<div class='holding-profit'>Total Value: <span class='{p_color}'>{curr_sym}{val:,.2f} ({p_pct:+.2f}%)</span></div>"

    if chart_img:
        st.markdown(combined_html, unsafe_allow_html=True)
        if st.button("🔍", key=f"zoom_{ticker}"):
             show_chart_dialog(ticker, period)
        st.markdown(chart_img + holding_html, unsafe_allow_html=True)
    else:
        st.markdown(combined_html + holding_html, unsafe_allow_html=True)
        
@st.dialog("Chart Explorer", width="large")
def show_chart_dialog(ticker, period):
    st.subheader(f"{ticker} - Chart")
    
    current_p = st.session_state.get(f"period_{ticker}_dialog", period)
    df = get_cached_hist_data(ticker, current_p)
    if not df.empty:
        fig = go.Figure(data=go.Scatter(x=df.index, y=df['Close'], mode='lines', line=dict(color='#4da6ff')))
        fig.update_layout(
            margin=dict(l=0, r=0, t=10, b=0),
            yaxis=dict(side='right', autorange=True, fixedrange=False, rangemode='normal'),
            xaxis=dict(autorange=True),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            dragmode='pan'
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    else:
        st.warning("No data available for this period.")
        
    # Ensure the widget key exists in session state before rendering to prevent warnings
    if f"dialog_period_{ticker}_seg" not in st.session_state:
        st.session_state[f"dialog_period_{ticker}_seg"] = current_p
        
    st.markdown("---")
    new_period = st.segmented_control("Chart Period", ["1D", "7D", "1M", "1Y", "ALL"], selection_mode="single", key=f"dialog_period_{ticker}_seg")
    if new_period and new_period != current_p:
        st.session_state[f"period_{ticker}_dialog"] = new_period
        st.session_state[f"period_{ticker}"] = new_period
        st.session_state[f"period_{ticker}_seg"] = new_period
        st.rerun()

# --- Common UI Renderers ---
def find_item_by_ticker(ticker):
    return next((item for item in data if item.get("ticker") == ticker), None)

def collect_tag_options(current_tags=None):
    tags = set(current_tags or [])
    for other_item in data:
        tags.update(other_item.get("tags", []))
    return sorted(t for t in tags if t)

@st.dialog("Edit Ticker")
def show_edit_dialog(ticker):
    item = find_item_by_ticker(ticker)
    if not item:
        st.warning("Ticker is no longer in the watchlist.")
        return

    st.markdown(f"### Edit {ticker}")
    with st.form(key=f"edit_dialog_form_{ticker}"):
        n_custom = st.text_input("Custom Company Name", value=item.get("custom_name", ""))
        n_rating = st.slider("Rating", 0, 5, item.get("rating", 0))

        c_avg, c_sh = st.columns(2)
        with c_avg:
            n_avg = st.number_input("Avg Cost", value=float(item.get("avg_cost", 0.0)), step=0.1)
        with c_sh:
            n_sh = st.number_input("Shares/Qty", value=float(item.get("shares", 0.0)), step=0.00001, format="%.5f")

        current_tags = item.get("tags", [])
        c_m, c_new = st.columns([0.7, 0.3])
        with c_m:
            selected_tags = st.multiselect(
                label="Select Tags",
                options=collect_tag_options(current_tags),
                default=current_tags,
                key=f"edit_dialog_tags_{ticker}",
            )
        with c_new:
            new_tag = st.text_input("Add New Tag", placeholder="Type & Save", key=f"edit_dialog_new_tag_{ticker}")

        n_tags = list(selected_tags)
        if new_tag and new_tag not in n_tags:
            n_tags.append(new_tag)

        n_yurl = st.text_input("Yahoo URL (Optional)", value=item.get("yahoo_url", ""))
        n_tvurl = st.text_input("TradingView URL (Optional)", value=item.get("tradingview_url", ""))

        c_save, c_del = st.columns([0.7, 0.3])
        with c_save:
            submitted = st.form_submit_button("Save", type="primary", use_container_width=True)
        with c_del:
            deleted = st.form_submit_button("Delete", use_container_width=True)

    if submitted:
        wm.update_ticker_data(
            ticker, item.get("note", ""), n_rating,
            n_yurl, n_tvurl, n_avg, n_sh, n_tags, n_custom
        )
        item.update({
            "custom_name": n_custom,
            "rating": n_rating,
            "avg_cost": n_avg,
            "shares": n_sh,
            "tags": n_tags,
            "yahoo_url": n_yurl,
            "tradingview_url": n_tvurl,
        })
        st.rerun()

    if deleted:
        wm.remove_ticker_from_watchlist(ticker)
        st.rerun()

@st.dialog("Ticker Note")
def show_note_dialog(ticker):
    item = find_item_by_ticker(ticker)
    if not item:
        st.warning("Ticker is no longer in the watchlist.")
        return

    note_text = item.get("note", "")
    with st.form(key=f"note_dialog_form_{ticker}"):
        new_note = st.text_area("Note", value=note_text, height=300, key=f"note_dialog_area_{ticker}")
        submitted = st.form_submit_button("Save", type="primary", use_container_width=True)

    if submitted:
        if new_note != note_text:
            wm.update_ticker_data(
                ticker, new_note, item.get("rating", 0),
                item.get("yahoo_url", ""), item.get("tradingview_url", ""),
                item.get("avg_cost", 0.0), item.get("shares", 0.0),
                item.get("tags", []), item.get("custom_name", "")
            )
            item["note"] = new_note
        st.rerun()

def render_edit_popover(item, key_prefix):
    ticker = item['ticker']
    if st.button("...", key=f"edit_btn_{key_prefix}_{ticker}", help=f"Edit {ticker}", use_container_width=True):
        show_edit_dialog(ticker)
    return
    with st.popover("⋮"):
        st.markdown(f"### Edit {ticker}")
        with st.form(key=f"form_{key_prefix}_{ticker}"):
            n_custom = st.text_input("Custom Company Name", value=item.get('custom_name',''))
            n_rating = st.slider("Rating", 0, 5, item.get('rating',0))
            
            c_avg, c_sh = st.columns(2)
            with c_avg:
                n_avg = st.number_input("Avg Cost", value=float(item.get('avg_cost',0.0)), step=0.1)
            with c_sh:
                n_sh = st.number_input("Shares/Qty", value=float(item.get('shares',0.0)), step=0.00001, format="%.5f")
            # Collect all existing tags from cached data for suggestions
            all_existing_tags = set()
            for other_item in data:
                for t in other_item.get('tags', []):
                    all_existing_tags.add(t)
            
            # Ensure currently selected tags are always in the options list
            current_tags = item.get('tags', [])
            for t in current_tags:
                all_existing_tags.add(t)
                
            all_existing_tags = sorted(list(all_existing_tags))
            
            # Use columns to put multiselect and a text input side-by-side
            c_m, c_new = st.columns([0.7, 0.3])
            with c_m:
                selected_tags = st.multiselect(
                    label="Select Tags",
                    options=all_existing_tags,
                    default=current_tags,
                    key=f"ms_{key_prefix}_{ticker}"
                )
            with c_new:
                new_tag = st.text_input("Add New Tag", placeholder="Type & Save", key=f"nt_{key_prefix}_{ticker}")
                
            n_tags = selected_tags
            if new_tag and new_tag not in n_tags:
                n_tags.append(new_tag)
            
            n_yurl = st.text_input("Yahoo URL (Optional)", value=item.get('yahoo_url',''))
            n_tvurl = st.text_input("TradingView URL (Optional)", value=item.get('tradingview_url',''))
            
            c_save, c_del = st.columns([0.7, 0.3])
            with c_save:
                submitted = st.form_submit_button("Save", type="primary", use_container_width=True)
            with c_del:
                deleted = st.form_submit_button("Delete", use_container_width=True)
                
            if submitted:
                wm.update_ticker_data(
                    ticker, item.get('note',''), n_rating,
                    n_yurl, n_tvurl, n_avg, n_sh, n_tags, n_custom
                )
                item.update({
                    'custom_name': n_custom, 'rating': n_rating,
                    'avg_cost': n_avg, 'shares': n_sh, 'tags': n_tags,
                    'yahoo_url': n_yurl, 'tradingview_url': n_tvurl
                })
                st.rerun(scope="fragment")
                
            if deleted:
                wm.remove_ticker_from_watchlist(ticker)
                st.rerun()

def render_note_popover(item, key_prefix):
    ticker = item['ticker']
    note_text = item.get('note', '')
    label = "N*" if note_text.strip() else "N"
    if st.button(label, key=f"note_btn_{key_prefix}_{ticker}", help=note_text if note_text else "Add note", use_container_width=True):
        show_note_dialog(ticker)
    return
    note_text = item.get('note', '')
    icon = "📝" if note_text.strip() else "🖊️"
    
    with st.popover(icon, help=note_text if note_text else "Add note"):
        new_note = st.text_area("Note", value=note_text, height=300, key=f"note_area_{key_prefix}_{ticker}")
        if new_note != note_text:
            wm.update_ticker_data(
                ticker, new_note, item.get('rating',0),
                item.get('yahoo_url',''), item.get('tradingview_url',''),
                item.get('avg_cost',0.0), item.get('shares',0.0),
                item.get('tags',[]), item.get('custom_name','')
            )
            item['note'] = new_note
            st.rerun(scope="fragment")

@st.fragment
def render_card(item, i, j):
    ticker = item['ticker']
    mtype = get_market_type(ticker)
    mcolor = get_market_color(mtype)
    
    # Period selection setup
    if f"period_{ticker}" not in st.session_state:
         default_p = st.session_state.settings.get("default_period", "1M") if "settings" in st.session_state else "1M"
         st.session_state[f"period_{ticker}"] = default_p
    period = st.session_state[f"period_{ticker}"]
    
    with st.container(border=True):
        # Title row
        c1, c2, c3 = st.columns([0.7, 0.15, 0.15])
        with c1:
            display_name = wm.get_display_name(ticker, item_data=item)
            stars_html = render_stars(item.get('rating', 0))
            tags_html = render_tags_html(item.get('tags', []))
            st.markdown(
                f"<div style='border-left: 4px solid {mcolor}; padding-left: 8px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>"
                f"<span style='font-weight:bold; font-size:1.6rem; color:white;'>{display_name}</span> "
                f"<span style='font-size:0.9rem;color:grey;'>{ticker}</span></div>"
                f"{stars_html}{tags_html}",
                unsafe_allow_html=True
            )
        with c2:
            render_note_popover(item, f"card_{i}_{j}")
        with c3:
            render_edit_popover(item, f"card_{i}_{j}")
                
        # Live Data
        render_live_data(item, period)
        
        # Chart Controls and Links
        if f"period_{ticker}_seg" not in st.session_state:
            st.session_state[f"period_{ticker}_seg"] = period
            
        new_period = st.segmented_control("Chart Period", ["1D", "7D", "1M", "1Y", "ALL"], key=f"period_{ticker}_seg", selection_mode="single", label_visibility="collapsed")
        if new_period and new_period != period:
             st.session_state[f"period_{ticker}"] = new_period
             st.rerun(scope="fragment")
             
        st.markdown(render_links(item), unsafe_allow_html=True)

@st.fragment
def render_list_item(item):
    ticker = item['ticker']
    name = wm.get_display_name(ticker, item_data=item)
    hist = get_cached_hist_data(ticker, "1D")
    live_p = get_cached_live_price(ticker, preferred_period="1D")
    curr_sym = "<span class='curr-sym'>NT$</span>" if get_market_type(ticker) == "tw" else "<span class='curr-sym'>US$</span>"
    
    # Formats
    price_str = f"{curr_sym}{live_p:.2f}" if live_p else "N/A"
    change_html = "-"
    if live_p is not None and not hist.empty and len(hist)>0:
        prev = hist['Close'].iloc[0]
        chg = live_p - prev
        pct = (chg/prev)*100 if prev>0 else 0
        color = "#FF3D00" if chg >= 0 else "#00C853"
        sign = "+" if chg >= 0 else ""
        change_html = f"<span style='color:{color}; font-weight:bold;'>{sign}{chg:.2f} ({sign}{pct:.2f}%)</span>"
        
    val, p_pct = calculate_holding_profit(item, live_p)
    profit_html = "-"
    if val is not None:
        color = "#FF3D00" if p_pct >= 0 else "#00C853"
        sign = "+" if p_pct >= 0 else ""
        profit_html = f"<span style='color:{color}; font-weight:bold;'>{curr_sym}{val:,.2f} ({sign}{p_pct:.2f}%)</span>"
        
    tags_html = render_tags_html(item.get('tags', []))
    rating_str = render_stars(item.get('rating',0))
    
    y_url, tv_url = get_default_urls(ticker)
    y_url = item.get('yahoo_url') or y_url
    tv_url = item.get('tradingview_url') or tv_url
    links_html = f"<div style='display:flex; gap:10px;'><a href='{y_url}' target='_blank' style='text-decoration:none;'>🟣 Y!</a><a href='{tv_url}' target='_blank' style='text-decoration:none;'>☁️ TV</a></div>"
    
    market_col = get_market_color(get_market_type(ticker))
    
    cc = st.columns([0.15, 0.12, 0.12, 0.12, 0.1, 0.1, 0.08, 0.1, 0.11])
    cc[0].markdown(f"<div style='border-left: 4px solid {market_col}; padding-left: 8px;'><b style='font-size:1.1rem;'>{ticker}</b><br><span style='color:#888; font-size:0.85rem;'>{name}</span></div>", unsafe_allow_html=True)
    cc[1].markdown(f"<span style='font-size:1.1rem;'>{price_str}</span>", unsafe_allow_html=True)
    cc[2].markdown(change_html, unsafe_allow_html=True)
    cc[3].markdown(profit_html, unsafe_allow_html=True)
    cc[4].markdown(f"<div style='margin-top:5px;'>{rating_str}</div>", unsafe_allow_html=True)
    cc[5].markdown(f"<div style='margin-top:4px;'>{tags_html}</div>", unsafe_allow_html=True)
    with cc[6]:
        c_p1, c_p2 = st.columns(2)
        with c_p1:
            render_note_popover(item, f"list_{ticker}")
        with c_p2:
            render_edit_popover(item, f"list_{ticker}")
    cc[7].markdown(links_html, unsafe_allow_html=True)
    st.markdown("<hr style='margin: 0.5em 0; border-color: #333;'>", unsafe_allow_html=True)


@st.dialog("Search & Add Ticker")
def add_ticker_dialog():
    tw_map = wm.load_stock_map()
    with open("us_stock_map.json", "r") as f: us_map = json.load(f)
    search_options = ["Type to search..."] + [f"{t} | {n}" for t, n in us_map.items()] + [f"{t} | {n}" for t, n in tw_map.items()]
    
    selected_option = st.selectbox("Find Ticker", options=search_options, index=0)
    custom_ticker = st.text_input("Custom Ticker", placeholder="e.g. MSFT, 2330.TW")
    st.info("💡 Hint: Add market suffixes for non-US stocks. e.g., '2330.TW' (Taiwan), '6324.T' (Tokyo), '0700.HK' (Hong Kong).")

    if st.button("Add to Watchlist"):
        target_ticker = custom_ticker.upper() if custom_ticker else (selected_option.split(" | ")[0] if selected_option != "Type to search..." else None)
        if target_ticker:
            success, msg = wm.add_ticker_to_watchlist(target_ticker)
            if success: st.success(msg); time.sleep(0.5); st.rerun()
            else: st.warning(msg)

# 移除 Reorder 對話框，改用下拉選單排序 (見主程式區)

# --- 主程式狀態寫入 ---
force_remote_watchlist = st.session_state.pop("force_remote_watchlist", False)
data = wm.load_watchlist(force_remote=force_remote_watchlist)
connection_warning = wm.get_connection_warning()
if connection_warning:
    st.warning(connection_warning)

# After loading check if migration happened
if isinstance(data, dict):
    # This shouldn't happen unless app started before migration fully finished in background, fallback
    st.rerun()

if 'display_mode' not in st.session_state:
    st.session_state.display_mode = "Card View"

if 'active_tag_filter' not in st.session_state or not isinstance(st.session_state.active_tag_filter, list):
    st.session_state.active_tag_filter = []

if 'active_holding_filter' not in st.session_state or not isinstance(st.session_state.active_holding_filter, list):
    st.session_state.active_holding_filter = []

if 'active_rating_filter' not in st.session_state or not isinstance(st.session_state.active_rating_filter, list):
    st.session_state.active_rating_filter = []

# 確保 settings 已經載入
_ = load_settings()

# Sidebar: Group Management & Search
summary_tickers = [
    item["ticker"]
    for item in data
    if item.get("avg_cost", 0.0) > 0 and item.get("shares", 0.0) > 0
]
prime_hist_data(summary_tickers, "1D")

with st.sidebar:
    st.header(" Portfolio Summary")
    
    total_cost = 0.0
    total_value = 0.0
    usdtwd = get_cached_usdtwd_rate()
    
    for item in data:
        live_p = get_cached_live_price(item['ticker'], preferred_period="1D")
        avg_cost = item.get('avg_cost', 0.0)
        shares = item.get('shares', 0.0)
        if avg_cost > 0 and shares > 0 and live_p is not None:
            item_cost = avg_cost * shares
            item_value = live_p * shares
            
            # Convert to TWD (if it's US or Crypto)
            if get_market_type(item['ticker']) in ["us", "crypto"]:
                item_cost *= usdtwd
                item_value *= usdtwd
                
            total_cost += item_cost
            total_value += item_value
                
    total_profit = total_value - total_cost
    total_pct = (total_profit / total_cost * 100) if total_cost > 0 else 0
    
    p_color_val = "#FF3D00" if total_profit >= 0 else "#00C853"
    sign_val = "+" if total_profit >= 0 else ""
    
    st.markdown(f"""
    <div style='background-color:#1E1E1E; padding:15px; border-radius:10px; border-left:4px solid {p_color_val};'>
        <div style='color:grey; font-size:0.9rem;'>Total Value (NTD)</div>
        <div style='font-size:1.8rem; font-weight:bold; color:white;'>NT${total_value:,.0f}</div>
        <div style='color:grey; font-size:0.9rem; margin-top:10px;'>Total Profit</div>
        <div style='font-size:1.2rem; font-weight:bold; color:{p_color_val};'>{sign_val}NT${total_profit:,.0f} ({sign_val}{total_pct:.2f}%)</div>
        <div style='color:grey; font-size:0.8rem; margin-top:5px;'>Cost: NT${total_cost:,.0f}</div>
    </div>
    """, unsafe_allow_html=True)
    
    
    st.markdown("---")
    
    tag_counts = {}
    no_tag_count = 0
    for item in data:
        tags = item.get('tags', [])
        if not tags:
            no_tag_count += 1
        else:
            for t in tags:
                tag_counts[t] = tag_counts.get(t, 0) + 1
                
    # Sort tags by count descending
    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
    
    c_hdr, c_edit = st.columns([0.85, 0.15], vertical_alignment="bottom")
    with c_hdr:
        st.header("🏷️ Tags")
    with c_edit:
        with st.popover("🎨", help="自訂標籤顏色"):
            st.markdown("**編輯標籤顏色**")
            
            def update_tag_color(t_name):
                new_c = st.session_state[f"global_cp_{t_name}"]
                s = st.session_state.settings
                if "tag_colors" not in s: s["tag_colors"] = {}
                s["tag_colors"][t_name] = new_c
                save_settings(s)
                
            for tag_name, _ in sorted_tags:
                current_c = st.session_state.settings.get("tag_colors", {}).get(tag_name, get_tag_color(tag_name))
                if "hsl" in current_c:
                    current_c = "#888888" # Fallback
                st.color_picker(tag_name, value=current_c, key=f"global_cp_{tag_name}", on_change=update_tag_color, args=(tag_name,))
    
    # 預先收集所有用到的顏色的 CSS，注入一次即可
    tag_styles = """
    /* 隱藏所有的 marker 元件，不佔據任何空間避免產生錯誤的排版間距 */
    div[data-testid="stElementContainer"]:has(.tag-marker) {
        display: none !important;
    }
    
    
    /* 讓被選取的 Tag 有明顯的發光亮框 */
    div[data-testid="stElementContainer"]:has(.tag-active) + div[data-testid="stElementContainer"] button {
        border: 2px solid white !important;
        font-weight: bold !important;
        box-shadow: 0 0 8px rgba(255,255,255,0.4);
    }
    """
    
    for tag_name, _ in sorted_tags:
        bg_col = get_tag_color(tag_name)
        c_name = "tag-btn-" + hashlib.md5(tag_name.encode()).hexdigest()
        tag_styles += f"""
        div[data-testid="stElementContainer"]:has(.{c_name}) + div[data-testid="stElementContainer"] button {{
            background-color: {bg_col} !important;
            border-color: rgba(255,255,255,0.2) !important;
            color: white !important;
            display: flex !important;
            justify-content: space-between !important;
            padding-left: 15px !important;
            padding-right: 15px !important;
        }}
        div[data-testid="stElementContainer"]:has(.{c_name}) + div[data-testid="stElementContainer"] button:hover {{
            filter: brightness(1.2) !important;
            border-color: rgba(255,255,255,0.5) !important;
        }}
        """
    
    # 無標籤的樣式
    tag_styles += """
    div[data-testid="stElementContainer"]:has(.tag-btn-notag) + div[data-testid="stElementContainer"] button {
        background-color: #444444 !important;
        border-color: rgba(255,255,255,0.2) !important;
        color: white !important;
        display: flex !important;
        justify-content: space-between !important;
        padding-left: 15px !important;
        padding-right: 15px !important;
    }
    div[data-testid="stElementContainer"]:has(.tag-btn-notag) + div[data-testid="stElementContainer"] button:hover {
        filter: brightness(1.2) !important;
        border-color: rgba(255,255,255,0.5) !important;
    }

    /* Target the generic sidebar filter buttons (Holding and Rating) which use stElementContainer but don't have stHorizontalBlock */
    div[data-testid="stElementContainer"]:has(.tag-marker) + div[data-testid="stElementContainer"] button span,
    div[data-testid="stElementContainer"]:has(.tag-marker) + div[data-testid="stElementContainer"] button div[data-testid="stMarkdownContainer"] {{
        width: 100% !important;
    }}
    div[data-testid="stElementContainer"]:has(.tag-marker) + div[data-testid="stElementContainer"] button p {{
        display: flex !important;
        width: 100% !important;
        align-items: center !important;
        gap: 0 !important;
        margin: 0 !important;
    }}
    div[data-testid="stElementContainer"]:has(.tag-marker) + div[data-testid="stElementContainer"] button p code {{
        margin-left: auto !important;
        background: transparent !important;
        border: none !important;
        color: inherit !important;
        font-size: 0.9em !important;
        font-weight: bold !important;
        padding: 0 !important;
        opacity: 0.8 !important;
        white-space: nowrap !important;
    }}
    """
    
    st.markdown(f"<style>{tag_styles}</style>", unsafe_allow_html=True)
    
    def render_sidebar_tag(tag_name, count, is_no_tag=False):
        bg_col = get_tag_color(tag_name) if not is_no_tag else "#555555"
        is_active = tag_name in st.session_state.get('active_tag_filter', [])
        if is_no_tag and "NO_TAG" in st.session_state.get('active_tag_filter', []):
            is_active = True
            
        eye_icon = "👁️" if is_active else "👁‍🗨"
        css_class = "tag-btn-notag" if is_no_tag else "tag-btn-" + hashlib.md5(tag_name.encode()).hexdigest()
        if is_active:
            css_class += " tag-active"
            
        # 魔法錨點：用於讓 CSS 精準上色，且不佔據空間
        st.markdown(f'<div class="tag-marker {css_class}"></div>', unsafe_allow_html=True)
        
        btn_label = f"{eye_icon} {tag_name}  `{count}`" 
        if st.button(btn_label, key=f"filter_tag_{tag_name}", use_container_width=True):
            target = "NO_TAG" if is_no_tag else tag_name
            if target in st.session_state.active_tag_filter:
                st.session_state.active_tag_filter.remove(target)
            else:
                st.session_state.active_tag_filter.append(target)
            st.rerun()

    # 渲染「無標籤」
    if no_tag_count > 0:
        render_sidebar_tag("無標籤", no_tag_count, is_no_tag=True)
        
    for t_val, t_cnt in sorted_tags:
        render_sidebar_tag(t_val, t_cnt)
        
    # 個別 tag 的 Clear btn 移除，稍後統一處理

    st.markdown("---")
    
    # --- Holding Status Filter ---
    st.header("💼 狀態")
    held_count = 0
    not_held_count = 0
    for item in data:
        if item.get('avg_cost', 0.0) > 0 and item.get('shares', 0.0) > 0:
            held_count += 1
        else:
            not_held_count += 1

    def render_holding_filter(status, count, filter_key):
        is_active = filter_key in st.session_state.get('active_holding_filter', [])
        eye_icon = "👁️" if is_active else "👁‍🗨"
        css_class = "tag-btn-notag"
        if is_active:
            css_class += " tag-active"
        
        st.markdown(f'<div class="tag-marker {css_class}"></div>', unsafe_allow_html=True)
        
        btn_label = f"{eye_icon} {status}  `{count}`"
        if st.button(btn_label, key=f"filter_holding_{filter_key}", use_container_width=True):
            if filter_key in st.session_state.active_holding_filter:
                st.session_state.active_holding_filter.remove(filter_key)
            else:
                st.session_state.active_holding_filter.append(filter_key)
            st.rerun()

    if held_count > 0:
        render_holding_filter("持有中", held_count, "HELD")
    if not_held_count > 0:
        render_holding_filter("未買進", not_held_count, "NOT_HELD")

    # 個別 status 的 Clear btn 移除，稍後統一處理

    st.markdown("---")

    # --- Rating Filter ---
    st.header("⭐ 評分")
    rating_counts = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0, 0: 0}
    for item in data:
        rate = item.get('rating', 0)
        if rate in rating_counts:
            rating_counts[rate] += 1
        else:
            rating_counts[0] += 1
            
    def render_rating_filter(stars, count):
        is_active = stars in st.session_state.get('active_rating_filter', [])
        eye_icon = "👁️" if is_active else "👁‍🗨"
        css_class = "tag-btn-notag"
        if is_active:
            css_class += " tag-active"
        
        st.markdown(f'<div class="tag-marker {css_class}"></div>', unsafe_allow_html=True)
        
        label = f"{stars} 星" if stars > 0 else "未評分"
        btn_label = f"{eye_icon} {label}  `{count}`"
        if st.button(btn_label, key=f"filter_rating_{stars}", use_container_width=True):
            if stars in st.session_state.active_rating_filter:
                st.session_state.active_rating_filter.remove(stars)
            else:
                st.session_state.active_rating_filter.append(stars)
            st.rerun()

    for s in [5, 4, 3, 2, 1, 0]:
        val = rating_counts[s]
        if val > 0:
            render_rating_filter(s, val)

    # 個別 rating 的 Clear btn 移除，稍後統一處理
            
    # --- Consolidated Clear Filter Button ---
    if st.session_state.get('active_tag_filter') or \
       st.session_state.get('active_holding_filter') or \
       st.session_state.get('active_rating_filter'):
        st.markdown('<div class="clear-filter-marker"></div>', unsafe_allow_html=True)
        if st.button("✖️ Clear Status Filter", use_container_width=True):
            st.session_state.active_tag_filter = []
            st.session_state.active_holding_filter = []
            st.session_state.active_rating_filter = []
            st.rerun()
# --- 前置設定 ---
if 'refresh_interval' not in st.session_state:
    _sett = load_settings()
    st.session_state.refresh_interval = _sett.get("refresh_interval", 60)

# 為了避免阻塞主執行緒，我們不使用 sleep 阻塞，而是使用 st.empty 配合寫入一段 setTimeout JavaScript
if st.session_state.refresh_interval > 0:
    st.markdown(
        f"""
        <script>
            setTimeout(function() {{
                window.parent.postMessage({{type: 'streamlit:rerun'}}, '*');
            }}, {st.session_state.refresh_interval * 1000});
        </script>
        """,
        unsafe_allow_html=True
    )

def handle_global_period_change():
    gp = st.session_state.get("global_period_ui")
    if gp:
        for t in data:
            tick = t['ticker']
            st.session_state[f"period_{tick}"] = gp
            st.session_state[f"period_{tick}_seg"] = gp

# --- 主畫面佈局 ---
st.markdown('<div class="toolbar-marker"></div>', unsafe_allow_html=True)
c_period, c_spacer, c_sort, c_disp, c_add, c_refresh, c_set = st.columns([0.25, 0.30, 0.2, 0.1, 0.05, 0.05, 0.05], gap="small")

with c_period:
    if "global_period_ui" not in st.session_state:
        st.session_state["global_period_ui"] = st.session_state.settings.get("default_period", "1M") if "settings" in st.session_state else "1M"
        
    st.segmented_control("Global Chart Period", ["1D", "7D", "1M", "1Y", "ALL"], selection_mode="single", label_visibility="collapsed", key="global_period_ui", on_change=handle_global_period_change)

with c_spacer:
    st.empty()

with c_sort:
    sort_opts = [
        "Type (TW > US > Crypto)", 
        "1D Change (High > Low)", 
        "1D Change (Low > High)", 
        "30D Change (High > Low)", 
        "30D Change (Low > High)", 
        "Total Value (High > Low)", 
        "Rating (High > Low)"
    ]
    if "sort_pref" not in st.session_state or st.session_state.sort_pref not in sort_opts:
        st.session_state.sort_pref = sort_opts[0]
    st.selectbox("Sort", options=sort_opts, key="sort_pref", label_visibility="collapsed")

with c_disp:
    disp_opts = ["Card View", "List View"]
    disp_fmt = {"Card View": "▦", "List View": "☰"}

    def on_display_mode_change():
        new_mode = st.session_state.get("disp_mode_seg")
        if new_mode:
            st.session_state.display_mode = new_mode

    st.segmented_control(
        "Display Mode",
        disp_opts,
        format_func=lambda x: disp_fmt[x],
        selection_mode="single",
        default=st.session_state.display_mode,
        key="disp_mode_seg",
        label_visibility="collapsed",
        on_change=on_display_mode_change,
    )

with c_add:
    if st.button("➕", use_container_width=True, type="primary", help="Add Ticker"):
        add_ticker_dialog()

with c_refresh:
    if st.button("🔄", use_container_width=True, help="刷新所有標的價格與走勢"):
        st.session_state.force_remote_watchlist = True
        wm.reset_supabase_client()
        wm.invalidate_watchlist_cache()
        get_live_price.clear()
        get_hist_data.clear()
        get_hist_data_batch.clear()
        st.rerun()

with c_set:
    with st.popover("⚙️", use_container_width=True):
        st.markdown("**Settings**")
        new_interval_val = st.selectbox(
            "Auto Refresh",
            options=[0, 30, 60, 300],
            format_func=lambda x: "Off" if x == 0 else f"{x}s" if x < 60 else f"{x//60}m",
            index=[0, 30, 60, 300].index(st.session_state.get('refresh_interval', 60))
        )
        
        period_opts = ["1D", "7D", "1M", "1Y", "ALL"]
        current_default_p = st.session_state.settings.get("default_period", "1M") if "settings" in st.session_state else "1M"
        new_default_period = st.selectbox(
            "Default Chart Period",
            options=period_opts,
            index=period_opts.index(current_default_p) if current_default_p in period_opts else 2
        )
        
        settings_changed = False
        _s = load_settings()
        
        if new_interval_val != st.session_state.refresh_interval:
            st.session_state.refresh_interval = new_interval_val
            _s["refresh_interval"] = new_interval_val
            settings_changed = True
            
        if new_default_period != current_default_p:
            _s["default_period"] = new_default_period
            if "settings" in st.session_state:
                 st.session_state.settings["default_period"] = new_default_period
            settings_changed = True
            
        if settings_changed:
            save_settings(_s)
            st.rerun()
            
        st.caption("Press 'R' to refresh manually.")

# --- 排序邏輯 ---
def apply_sort(items, method):
    if method == "Type (TW > US > Crypto)":
        order_map = {"tw": 0, "us": 1, "crypto": 2}
        return sorted(items, key=lambda x: order_map.get(get_market_type(x['ticker']), 99))
    elif method == "Rating (High > Low)":
        return sorted(items, key=lambda x: x.get('rating', 0), reverse=True)
    elif "Change" in method:
        period = "1D" if "1D" in method else "1M"
        reverse = "High > Low" in method
        
        def get_chg(t):
            hd = get_cached_hist_data(t, period)
            hp = get_cached_live_price(t, preferred_period=period)
            if hp is not None and not hd.empty and len(hd) > 0:
                return (hp - hd['Close'].iloc[0]) / hd['Close'].iloc[0]
            return -9999 if reverse else 9999
            
        return sorted(items, key=lambda x: get_chg(x['ticker']), reverse=reverse)
    elif method == "Total Value (High > Low)":
        def get_val(item):
            lp = get_cached_live_price(item['ticker'], preferred_period="1D")
            if lp is not None and item.get('avg_cost',0)>0 and item.get('shares',0)>0:
                val = lp * item.get('shares',0)
                # Normalize to TWD for sorting
                if get_market_type(item['ticker']) in ["us", "crypto"]:
                    val *= get_cached_usdtwd_rate()
                return val
            return -1
        return sorted(items, key=get_val, reverse=True)
    return items

def apply_filters(items):
    filtered = list(items)

    if st.session_state.active_tag_filter:
        active_tags = st.session_state.active_tag_filter
        filtered = [
            item for item in filtered
            if ("NO_TAG" in active_tags and not item.get('tags', [])) or any(t in active_tags for t in item.get('tags', []))
        ]

    if st.session_state.active_holding_filter:
        active_holdings = st.session_state.active_holding_filter
        filtered = [
            item for item in filtered
            if ("HELD" in active_holdings and item.get('avg_cost', 0.0) > 0 and item.get('shares', 0.0) > 0) or
               ("NOT_HELD" in active_holdings and not (item.get('avg_cost', 0.0) > 0 and item.get('shares', 0.0) > 0))
        ]

    if st.session_state.active_rating_filter:
        active_ratings = st.session_state.active_rating_filter
        filtered = [item for item in filtered if item.get('rating', 0) in active_ratings]

    return filtered

def prime_market_data_for_sort(items, sort_method):
    tickers = [item["ticker"] for item in items]

    if "Change" in sort_method:
        sort_period = "1D" if "1D" in sort_method else "1M"
        prime_hist_data(tickers, sort_period)
    elif sort_method == "Total Value (High > Low)":
        prime_hist_data(tickers, "1D")

def prime_market_data_for_render(items, display_mode):
    tickers = [item["ticker"] for item in items]

    if display_mode == "List View":
        prime_hist_data(tickers, "1D")
    else:
        period_groups = {}
        default_p = st.session_state.settings.get("default_period", "1M") if "settings" in st.session_state else "1M"
        for item in items:
            ticker = item["ticker"]
            period = st.session_state.get(f"period_{ticker}", default_p)
            period_groups.setdefault(period, []).append(ticker)
        for period, period_tickers in period_groups.items():
            prime_hist_data(period_tickers, period)

def get_card_page_items(items):
    total_pages = max(1, (len(items) + CARD_PAGE_SIZE - 1) // CARD_PAGE_SIZE)
    page = int(st.session_state.get("card_page", 0))
    page = min(max(page, 0), total_pages - 1)
    st.session_state.card_page = page

    start = page * CARD_PAGE_SIZE
    end = min(start + CARD_PAGE_SIZE, len(items))
    return items[start:end], page, total_pages, start, end

sort_method = st.session_state.get('sort_pref', "Type (TW > US > Crypto)")
current_items = apply_filters(data)
prime_market_data_for_sort(current_items, sort_method)
current_items = apply_sort(current_items, sort_method)

card_items = current_items
card_page = 0
card_total_pages = 1
card_start = 0
card_end = len(current_items)
if st.session_state.display_mode == "Card View":
    card_items, card_page, card_total_pages, card_start, card_end = get_card_page_items(current_items)
    prime_market_data_for_render(card_items, "Card View")
else:
    prime_market_data_for_render(current_items, "List View")

if not current_items:
    st.info("Watchlist is empty in this group.")
else:
    main_container = st.empty()
    with main_container.container():
        if st.session_state.display_mode == "Card View":
            if card_total_pages > 1:
                p_prev, p_label, p_next = st.columns([0.12, 0.76, 0.12])
                with p_prev:
                    if st.button("Prev", disabled=card_page == 0, use_container_width=True):
                        st.session_state.card_page = max(0, card_page - 1)
                        st.rerun()
                with p_label:
                    st.markdown(
                        f"<div style='text-align:center; color:#aaa; padding-top:0.35rem;'>"
                        f"Cards {card_start + 1}-{card_end} of {len(current_items)} | Page {card_page + 1}/{card_total_pages}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                with p_next:
                    if st.button("Next", disabled=card_page >= card_total_pages - 1, use_container_width=True):
                        st.session_state.card_page = min(card_total_pages - 1, card_page + 1)
                        st.rerun()

            st.markdown('<div class="card-grid-marker"></div>', unsafe_allow_html=True)
            for i in range(0, len(card_items), 5):
                chunk = card_items[i:i+5]
                cols = st.columns(5)
                for j, item in enumerate(chunk):
                    with cols[j]:
                         render_card(item, i, j)

        else:
            # LIST VIEW
            st.markdown("### List View")
            
            # Build clean table header
            cols = st.columns([0.15, 0.12, 0.12, 0.12, 0.1, 0.1, 0.08, 0.1, 0.11])
            cols[0].markdown("**Symbol**")
            cols[1].markdown("**Price**")
            cols[2].markdown("**Change (1D)**")
            cols[3].markdown("**Total Value**")
            cols[4].markdown("**Rating**")
            cols[5].markdown("**Tags**")
            cols[6].markdown("**Edit**")
            cols[7].markdown("**Links**")
            st.markdown("<hr style='margin: 0.5em 0; border-color: #333;'>", unsafe_allow_html=True)
            
            for item in current_items:
                render_list_item(item)

# 腳本執行完畢，清除載入動畫
spinner_placeholder.empty()


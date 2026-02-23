import json
import os
import streamlit as st
from supabase import create_client, Client

MAP_FILE = "tw_stock_map.json"

@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

def load_stock_map():
    if os.path.exists(MAP_FILE):
        with open(MAP_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def get_display_name(ticker, item_data=None, yf_info=None):
    """
    Returns the display name.
    Priority:
    1. Custom Name defined by user
    2. TW Stock Mapping (if .TW)
    3. yfinance shortName/longName
    4. Ticker symbol itself
    """
    if item_data and item_data.get('custom_name'):
        return item_data['custom_name']

    if ".TW" in ticker:
        stock_map = load_stock_map()
        if ticker in stock_map:
            return stock_map[ticker]

    if yf_info:
        return yf_info.get('shortName') or yf_info.get('longName') or ticker

    return ticker

def get_default_item(ticker):
    return {
        "ticker": ticker,
        "custom_name": "",
        "note": "",
        "rating": 0,
        "holding": False,
        "yahoo_url": "",
        "tradingview_url": "",
        "avg_cost": 0.0,
        "shares": 0.0,
        "tags": []
    }

def load_watchlist():
    sb = get_supabase()
    response = sb.table("watchlist").select("*").order("display_order").order("id").execute()
    return response.data or []

def save_watchlist(data):
    """批次 upsert 整個清單，並更新排序。"""
    sb = get_supabase()
    for i, item in enumerate(data):
        item["display_order"] = i
        # 移除 Supabase 自動產生的欄位，避免衝突
        item.pop("created_at", None)
    sb.table("watchlist").upsert(data, on_conflict="ticker").execute()

def add_ticker_to_watchlist(ticker):
    # Check if .TW needs to fallback to .TWO
    if ticker.endswith(".TW"):
        import yfinance as yf
        try:
            t_orig = yf.Ticker(ticker)
            hist = t_orig.history(period="1d")
            if hist.empty:
                fallback_ticker = ticker.replace(".TW", ".TWO")
                t_fall = yf.Ticker(fallback_ticker)
                hist_fall = t_fall.history(period="1d")
                if not hist_fall.empty:
                    ticker = fallback_ticker
        except:
            pass

    sb = get_supabase()
    existing = sb.table("watchlist").select("ticker").eq("ticker", ticker).execute()
    if existing.data:
        return False, "Ticker already in watchlist."

    # 計算下一個排序值
    max_resp = sb.table("watchlist").select("display_order").order("display_order", desc=True).limit(1).execute()
    next_order = (max_resp.data[0]["display_order"] + 1) if max_resp.data else 0

    new_item = get_default_item(ticker)
    new_item["display_order"] = next_order
    sb.table("watchlist").insert(new_item).execute()
    return True, f"Added {ticker}"

def remove_ticker_from_watchlist(ticker):
    sb = get_supabase()
    sb.table("watchlist").delete().eq("ticker", ticker).execute()

def update_ticker_data(ticker, note, rating,
                       yahoo_url="", tradingview_url="", avg_cost=0.0, shares=0.0, tags=None, custom_name=""):
    if tags is None:
        tags = []
    sb = get_supabase()
    sb.table("watchlist").update({
        "note": note,
        "rating": rating,
        "custom_name": custom_name,
        "yahoo_url": yahoo_url,
        "tradingview_url": tradingview_url,
        "avg_cost": avg_cost,
        "shares": shares,
        "tags": tags,
        "holding": avg_cost > 0 and shares > 0,
    }).eq("ticker", ticker).execute()

def save_item_order(ordered_items):
    """更新每個 ticker 的 display_order。"""
    sb = get_supabase()
    for i, item in enumerate(ordered_items):
        sb.table("watchlist").update({"display_order": i}).eq("ticker", item["ticker"]).execute()

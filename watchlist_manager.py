import json
import os
import streamlit as st

WATCHLIST_FILE = "watchlist.json"
MAP_FILE = "tw_stock_map.json"

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

def migrate_item(item):
    """Migrates an old item dict to the new format."""
    default = get_default_item(item.get("ticker", ""))
    for k, v in item.items():
        if k in default:
            default[k] = v
    return default

def load_watchlist():
    if not os.path.exists(WATCHLIST_FILE):
        return []
    try:
        with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        return []
    
    migrated = False
    
    # 處理舊版字典結構 (分組) - 這裡做合併轉換
    if isinstance(data, dict):
        new_flat_list = []
        for g_name, g_items in data.items():
            if isinstance(g_items, list):
                for item in g_items:
                    # 如果有重複的代號，以先出現的為主 (簡單處理)
                    if not any(x['ticker'] == item.get('ticker') for x in new_flat_list):
                        new_item = migrate_item(item) if isinstance(item, dict) else get_default_item(str(item))
                        new_flat_list.append(new_item)
        data = new_flat_list
        migrated = True
        
    # 一般的 list 檢查是否需要 migrate 欄位
    elif isinstance(data, list):
        new_flat_list = []
        for item in data:
            if isinstance(item, str):
                new_flat_list.append(get_default_item(item))
                migrated = True
            elif isinstance(item, dict):
                new_item = migrate_item(item)
                if new_item != item:
                    migrated = True
                new_flat_list.append(new_item)
        data = new_flat_list
                
    if migrated:
        save_watchlist(data)
        st.toast("Watchlist data structure flattened successfully!")
        
    return data

def save_watchlist(data):
    with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def add_ticker_to_watchlist(ticker):
    data = load_watchlist()
        
    # Check if .TW needs to fallback to .TWO
    if ticker.endswith(".TW"):
        import yfinance as yf
        try:
            # Check if .TW has data
            t_orig = yf.Ticker(ticker)
            hist = t_orig.history(period="1d")
            if hist.empty:
                # Fallback to .TWO
                fallback_ticker = ticker.replace(".TW", ".TWO")
                t_fall = yf.Ticker(fallback_ticker)
                hist_fall = t_fall.history(period="1d")
                if not hist_fall.empty:
                    ticker = fallback_ticker
        except:
            pass

    for item in data:
        if item['ticker'] == ticker:
            return False, "Ticker already in watchlist."
            
    data.append(get_default_item(ticker))
    save_watchlist(data)
    return True, f"Added {ticker}"

def remove_ticker_from_watchlist(ticker):
    data = load_watchlist()
    original_len = len(data)
    data = [item for item in data if item['ticker'] != ticker]
    if len(data) < original_len:
        save_watchlist(data)

def update_ticker_data(ticker, note, rating,
                       yahoo_url="", tradingview_url="", avg_cost=0.0, shares=0.0, tags=None, custom_name=""):
    if tags is None:
        tags = []
    data = load_watchlist()
    
    updated = False
    for item in data:
        if item['ticker'] == ticker:
            item['note'] = note
            item['rating'] = rating
            item['custom_name'] = custom_name
            # holding is now implicit based on avg_cost and shares > 0
            item['yahoo_url'] = yahoo_url
            item['tradingview_url'] = tradingview_url
            item['avg_cost'] = avg_cost
            item['shares'] = shares
            item['tags'] = tags
            updated = True
            break
            
    if updated:
        save_watchlist(data)
        
def save_item_order(ordered_items):
    """Saves the exact ordered list of items."""
    save_watchlist(ordered_items)

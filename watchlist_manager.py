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
        return {"Default": []}
    try:
        with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        return {"Default": []}
    
    migrated = False
    
    # Migration 1: List[str] -> List[dict] -> Dict[str, List[dict]]
    if isinstance(data, list):
        new_default_group = []
        for item in data:
            if isinstance(item, str):
                new_default_group.append(get_default_item(item))
            elif isinstance(item, dict):
                new_default_group.append(migrate_item(item))
        data = {"Default": new_default_group}
        migrated = True
    elif isinstance(data, dict):
        for g_name, g_items in data.items():
            if isinstance(g_items, list):
                new_items = []
                for item in g_items:
                    if isinstance(item, str):
                        new_items.append(get_default_item(item))
                    elif isinstance(item, dict):
                        new_item = migrate_item(item)
                        if new_item != item:
                            migrated = True
                        new_items.append(new_item)
                data[g_name] = new_items
                
    if migrated:
        save_watchlist(data)
        st.toast("Watchlist data structure migrated to groups successfully!")
        
    return data

def save_watchlist(data):
    with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def add_group(group_name):
    data = load_watchlist()
    if group_name not in data:
        data[group_name] = []
        save_watchlist(data)
        return True, f"Group {group_name} added."
    return False, "Group already exists."

def rename_group(old_name, new_name):
    data = load_watchlist()
    if old_name in data and new_name not in data:
        data[new_name] = data.pop(old_name)
        save_watchlist(data)
        return True, "Group renamed."
    return False, "Cannot rename group."

def delete_group(group_name):
    data = load_watchlist()
    if group_name in data:
        del data[group_name]
        if not data:
            data = {"Default": []}
        save_watchlist(data)
        return True, "Group deleted."
    return False, "Group not found."

def add_ticker_to_watchlist(ticker, group_name="Default"):
    data = load_watchlist()
    if group_name not in data:
        data[group_name] = []
        
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

    group = data[group_name]
    for item in group:
        if item['ticker'] == ticker:
            return False, "Ticker already in watchlist group."
            
    group.append(get_default_item(ticker))
    save_watchlist(data)
    return True, f"Added {ticker} to {group_name}"

def remove_ticker_from_watchlist(ticker, group_name="Default"):
    data = load_watchlist()
    if group_name in data:
        data[group_name] = [item for item in data[group_name] if item['ticker'] != ticker]
        save_watchlist(data)

def update_ticker_data(ticker, note, rating, group_name="Default",
                       yahoo_url="", tradingview_url="", avg_cost=0.0, shares=0.0, tags=None, custom_name=""):
    if tags is None:
        tags = []
    data = load_watchlist()
    
    # Sync update across ALL groups for the same ticker
    updated = False
    for g_items in data.values():
        for item in g_items:
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
                
    if updated:
        save_watchlist(data)
        
def save_group_order(group_name, ordered_items):
    """Saves the exact ordered list of items for a specific group (for drag & drop sorting)."""
    data = load_watchlist()
    if group_name in data:
        data[group_name] = ordered_items
        save_watchlist(data)

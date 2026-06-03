import json
import os
import time

import streamlit as st
from supabase import Client, create_client

MAP_FILE = "tw_stock_map.json"
WATCHLIST_FILE = "watchlist.json"
SUPABASE_RETRIES = 2
SUPABASE_STATUS_KEY = "_supabase_connection_warning"


@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)


def reset_supabase_client():
    """Clear the cached Supabase client so the next request starts fresh."""
    try:
        get_supabase.clear()
    except Exception:
        pass


def _set_connection_warning(message):
    try:
        st.session_state[SUPABASE_STATUS_KEY] = message
    except Exception:
        pass


def clear_connection_warning():
    try:
        st.session_state.pop(SUPABASE_STATUS_KEY, None)
    except Exception:
        pass


def get_connection_warning():
    try:
        return st.session_state.get(SUPABASE_STATUS_KEY)
    except Exception:
        return None


def _execute_supabase(operation, label):
    last_error = None
    for attempt in range(SUPABASE_RETRIES + 1):
        try:
            result = operation(get_supabase())
            clear_connection_warning()
            return result
        except Exception as exc:
            last_error = exc
            reset_supabase_client()
            if attempt < SUPABASE_RETRIES:
                time.sleep(0.4 * (attempt + 1))

    print(f"{label} failed after retry: {type(last_error).__name__}: {last_error}")
    _set_connection_warning(
        "Supabase 暫時無法連線，現在顯示本地備份資料；資料庫恢復後可按刷新重新連線。"
    )
    raise last_error


def _load_local_watchlist():
    try:
        if os.path.exists(WATCHLIST_FILE):
            with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception as exc:
        print(f"local watchlist fallback failed: {type(exc).__name__}: {exc}")
    return []


@st.cache_data(ttl=3600)
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
    if item_data and item_data.get("custom_name"):
        return item_data["custom_name"]

    if ".TW" in ticker:
        stock_map = load_stock_map()
        if ticker in stock_map:
            return stock_map[ticker]

    if yf_info:
        return yf_info.get("shortName") or yf_info.get("longName") or ticker

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
        "tags": [],
    }


@st.cache_data(ttl=30)
def load_watchlist():
    try:
        response = _execute_supabase(
            lambda sb: sb.table("watchlist").select("*").order("display_order").order("id").execute(),
            "load_watchlist",
        )
        return response.data or []
    except Exception:
        return _load_local_watchlist()


def invalidate_watchlist_cache():
    """Call after any write operation to clear the watchlist cache."""
    load_watchlist.clear()


def save_watchlist(data):
    """Upsert the complete watchlist to Supabase."""
    try:
        for i, item in enumerate(data):
            item["display_order"] = i
            item.pop("created_at", None)
        _execute_supabase(
            lambda sb: sb.table("watchlist").upsert(data, on_conflict="ticker").execute(),
            "save_watchlist",
        )
        invalidate_watchlist_cache()
        return True
    except Exception:
        return False


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
        except Exception:
            pass

    try:
        existing = _execute_supabase(
            lambda sb: sb.table("watchlist").select("ticker").eq("ticker", ticker).execute(),
            "check_existing_ticker",
        )
        if existing.data:
            return False, "Ticker already in watchlist."

        max_resp = _execute_supabase(
            lambda sb: sb.table("watchlist")
            .select("display_order")
            .order("display_order", desc=True)
            .limit(1)
            .execute(),
            "get_next_display_order",
        )
        next_order = (max_resp.data[0]["display_order"] + 1) if max_resp.data else 0

        new_item = get_default_item(ticker)
        new_item["display_order"] = next_order
        _execute_supabase(
            lambda sb: sb.table("watchlist").insert(new_item).execute(),
            "add_ticker",
        )
        invalidate_watchlist_cache()
        return True, f"Added {ticker}"
    except Exception:
        return False, "Supabase 暫時無法寫入，請稍後重新整理後再試。"


def remove_ticker_from_watchlist(ticker):
    try:
        _execute_supabase(
            lambda sb: sb.table("watchlist").delete().eq("ticker", ticker).execute(),
            "remove_ticker",
        )
        invalidate_watchlist_cache()
        return True
    except Exception:
        return False


def update_ticker_data(
    ticker,
    note,
    rating,
    yahoo_url="",
    tradingview_url="",
    avg_cost=0.0,
    shares=0.0,
    tags=None,
    custom_name="",
):
    if tags is None:
        tags = []

    try:
        _execute_supabase(
            lambda sb: sb.table("watchlist")
            .update(
                {
                    "note": note,
                    "rating": rating,
                    "custom_name": custom_name,
                    "yahoo_url": yahoo_url,
                    "tradingview_url": tradingview_url,
                    "avg_cost": avg_cost,
                    "shares": shares,
                    "tags": tags,
                    "holding": avg_cost > 0 and shares > 0,
                }
            )
            .eq("ticker", ticker)
            .execute(),
            "update_ticker",
        )
        invalidate_watchlist_cache()
        return True
    except Exception:
        return False


def save_item_order(ordered_items):
    try:
        for i, item in enumerate(ordered_items):
            _execute_supabase(
                lambda sb, i=i, item=item: sb.table("watchlist")
                .update({"display_order": i})
                .eq("ticker", item["ticker"])
                .execute(),
                "save_item_order",
            )
        invalidate_watchlist_cache()
        return True
    except Exception:
        return False

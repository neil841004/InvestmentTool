import json
import os
import sqlite3
import time
import urllib.request

import streamlit as st

MAP_FILE = "tw_stock_map.json"
WATCHLIST_FILE = "watchlist.json"
LOCAL_BACKUP_DB = os.path.join("local_backups", "investmenttool_backup.sqlite")
SHEETS_RETRIES = 2
SHEETS_STATUS_KEY = "_sheets_connection_warning"


@st.cache_resource
def get_sheets_config():
    try:
        config = st.secrets.get("google_sheets", {})
    except Exception:
        config = {}

    web_app_url = os.getenv("GOOGLE_SHEETS_WEB_APP_URL") or config.get("web_app_url")
    token = os.getenv("GOOGLE_SHEETS_TOKEN") or config.get("token")
    if not web_app_url or not token:
        raise RuntimeError(
            "Missing Google Sheets storage config. Set [google_sheets].web_app_url and token in .streamlit/secrets.toml."
        )
    return {"web_app_url": web_app_url, "token": token}


def reset_sheets_client():
    try:
        get_sheets_config.clear()
    except Exception:
        pass


def reset_supabase_client():
    """Compatibility shim for older app.py refresh calls."""
    reset_sheets_client()


def _set_connection_warning(message):
    try:
        st.session_state[SHEETS_STATUS_KEY] = message
    except Exception:
        pass


def clear_connection_warning():
    try:
        st.session_state.pop(SHEETS_STATUS_KEY, None)
    except Exception:
        pass


def get_connection_warning():
    try:
        return st.session_state.get(SHEETS_STATUS_KEY)
    except Exception:
        return None


def _execute_sheets(action, payload=None):
    config = get_sheets_config()
    body = {"action": action, "token": config["token"]}
    if payload:
        body.update(payload)

    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    last_error = None

    for attempt in range(SHEETS_RETRIES + 1):
        try:
            request = urllib.request.Request(
                config["web_app_url"],
                data=data,
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read().decode("utf-8")
            result = json.loads(raw)
            if not result.get("ok"):
                raise RuntimeError(result.get("error") or raw)
            clear_connection_warning()
            return result
        except Exception as exc:
            last_error = exc
            reset_sheets_client()
            if attempt < SHEETS_RETRIES:
                time.sleep(0.5 * (attempt + 1))

    print(f"Google Sheets action '{action}' failed after retry: {type(last_error).__name__}: {last_error}")
    _set_connection_warning(
        "Google Sheets storage is temporarily unavailable. Showing the latest local backup when possible."
    )
    raise last_error


def _decode_json_field(value, fallback):
    if value in (None, ""):
        return fallback
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return fallback


def _coerce_float(value, default=0.0):
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def _coerce_int(value, default=0):
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except Exception:
        return default


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "持有", "持有中"}
    return False


def _normalize_tags(value):
    if isinstance(value, list):
        return [str(tag).strip() for tag in value if str(tag).strip()]
    decoded = _decode_json_field(value, None)
    if isinstance(decoded, list):
        return [str(tag).strip() for tag in decoded if str(tag).strip()]
    if isinstance(value, str):
        return [tag.strip() for tag in value.split(",") if tag.strip()]
    return []


def _normalize_item(item):
    avg_cost = _coerce_float(item.get("avg_cost"))
    shares = _coerce_float(item.get("shares"))
    holding = _coerce_bool(item.get("holding")) or (avg_cost > 0 and shares > 0)
    return {
        "ticker": str(item.get("ticker") or "").strip(),
        "custom_name": item.get("custom_name") or "",
        "note": item.get("note") or "",
        "rating": _coerce_int(item.get("rating")),
        "holding": holding,
        "yahoo_url": item.get("yahoo_url") or "",
        "tradingview_url": item.get("tradingview_url") or "",
        "avg_cost": avg_cost,
        "shares": shares,
        "tags": _normalize_tags(item.get("tags")),
        "display_order": _coerce_int(item.get("display_order")),
        "created_at": item.get("created_at") or "",
    }


def _load_local_watchlist():
    sqlite_data = _load_sqlite_watchlist()
    if sqlite_data:
        return sqlite_data

    try:
        if os.path.exists(WATCHLIST_FILE):
            with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return [_normalize_item(item) for item in data if item.get("ticker")]
    except Exception as exc:
        print(f"local watchlist fallback failed: {type(exc).__name__}: {exc}")
    return []


def _load_sqlite_watchlist():
    try:
        if not os.path.exists(LOCAL_BACKUP_DB):
            return []

        with sqlite3.connect(LOCAL_BACKUP_DB) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT *
                FROM watchlist
                ORDER BY display_order, id
                """
            ).fetchall()

        data = []
        for row in rows:
            item = dict(row)
            raw = _decode_json_field(item.pop("raw_json", None), {})
            item.pop("backed_up_at", None)
            if isinstance(raw, dict):
                raw.update(item)
                item = raw
            normalized = _normalize_item(item)
            if normalized["ticker"]:
                data.append(normalized)
        return data
    except Exception as exc:
        print(f"sqlite watchlist fallback failed: {type(exc).__name__}: {exc}")
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
        response = _execute_sheets("load_watchlist")
        items = response.get("items") or []
        return [_normalize_item(item) for item in items if item.get("ticker")]
    except Exception:
        return _load_local_watchlist()


def invalidate_watchlist_cache():
    """Call after any write operation to clear the watchlist cache."""
    load_watchlist.clear()


def save_watchlist(data):
    """Save the complete watchlist to Google Sheets."""
    try:
        normalized = []
        for i, item in enumerate(data):
            clean_item = _normalize_item(item)
            clean_item["display_order"] = i
            if clean_item["ticker"]:
                normalized.append(clean_item)
        _execute_sheets("save_watchlist", {"items": normalized})
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
        data = load_watchlist()
        if any(item.get("ticker") == ticker for item in data):
            return False, "Ticker already in watchlist."

        new_item = get_default_item(ticker)
        new_item["display_order"] = len(data)
        data.append(new_item)
        if save_watchlist(data):
            return True, f"Added {ticker}"
        return False, "Could not save ticker to Google Sheets."
    except Exception:
        return False, "Could not add ticker to Google Sheets."


def remove_ticker_from_watchlist(ticker):
    try:
        data = [item for item in load_watchlist() if item.get("ticker") != ticker]
        return save_watchlist(data)
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
        data = load_watchlist()
        updated = False
        for item in data:
            if item.get("ticker") == ticker:
                item.update(
                    {
                        "note": note,
                        "rating": rating,
                        "custom_name": custom_name,
                        "yahoo_url": yahoo_url,
                        "tradingview_url": tradingview_url,
                        "avg_cost": avg_cost,
                        "shares": shares,
                        "tags": tags,
                        "holding": _coerce_float(avg_cost) > 0 and _coerce_float(shares) > 0,
                    }
                )
                updated = True
                break
        if not updated:
            return False
        return save_watchlist(data)
    except Exception:
        return False


def save_item_order(ordered_items):
    try:
        order_by_ticker = {item["ticker"]: i for i, item in enumerate(ordered_items)}
        data = load_watchlist()
        for item in data:
            if item.get("ticker") in order_by_ticker:
                item["display_order"] = order_by_ticker[item["ticker"]]
        data.sort(key=lambda item: item.get("display_order", 0))
        return save_watchlist(data)
    except Exception:
        return False


def _default_settings():
    return {"refresh_interval": 60, "tag_colors": {}, "default_period": "1M"}


@st.cache_data(ttl=30)
def load_settings_from_storage():
    response = _execute_sheets("load_settings")
    settings = response.get("settings") or {}
    merged = _default_settings()
    merged.update(settings)
    merged["refresh_interval"] = _coerce_int(merged.get("refresh_interval"), 60)
    merged["tag_colors"] = _decode_json_field(merged.get("tag_colors"), {})
    if not isinstance(merged["tag_colors"], dict):
        merged["tag_colors"] = {}
    merged["default_period"] = merged.get("default_period") or "1M"
    return merged


def load_settings():
    try:
        return load_settings_from_storage()
    except Exception:
        try:
            if os.path.exists("settings.json"):
                with open("settings.json", "r", encoding="utf-8") as f:
                    local_settings = json.load(f)
                settings = _default_settings()
                settings.update(local_settings)
                return settings
        except Exception:
            pass
        return _default_settings()


def save_settings(settings):
    try:
        local_settings = _default_settings()
        local_settings.update(settings or {})
        with open("settings.json", "w", encoding="utf-8") as f:
            json.dump(local_settings, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    try:
        _execute_sheets("save_settings", {"settings": settings or {}})
        load_settings_from_storage.clear()
        return True
    except Exception:
        return False

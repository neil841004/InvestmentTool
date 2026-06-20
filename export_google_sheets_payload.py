import argparse
import json
import sqlite3
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_DB_PATH = Path("local_backups") / "investmenttool_backup.sqlite"
DEFAULT_OUT_PATH = Path("local_backups") / "google_sheets_payload.json"


def decode_json(value, fallback):
    if value in (None, ""):
        return fallback
    try:
        return json.loads(value)
    except Exception:
        return fallback


def load_payload(db_path):
    if not db_path.exists():
        raise FileNotFoundError(f"SQLite backup not found: {db_path}")

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        watchlist_rows = conn.execute(
            """
            SELECT *
            FROM watchlist
            ORDER BY display_order, id
            """
        ).fetchall()
        settings_rows = conn.execute(
            """
            SELECT *
            FROM settings
            ORDER BY id
            """
        ).fetchall()

    targets = []
    assets = []
    for row in watchlist_rows:
        item = dict(row)
        raw = decode_json(item.get("raw_json"), {})
        if isinstance(raw, dict):
            merged = {**raw, **item}
        else:
            merged = item

        tags = decode_json(merged.get("tags"), merged.get("tags") or [])
        if not isinstance(tags, list):
            tags = []

        ticker = str(merged.get("ticker") or "").strip()
        if not ticker:
            continue

        targets.append(
            {
                "ticker": ticker,
                "custom_name": merged.get("custom_name") or "",
                "note": merged.get("note") or "",
                "rating": int(merged.get("rating") or 0),
                "yahoo_url": merged.get("yahoo_url") or "",
                "tradingview_url": merged.get("tradingview_url") or "",
                "tags": ",".join(str(tag) for tag in tags),
                "display_order": int(merged.get("display_order") or 0),
                "created_at": merged.get("created_at") or "",
            }
        )
        assets.append(
            {
                "ticker": ticker,
                "avg_cost": float(merged.get("avg_cost") or 0),
                "shares": float(merged.get("shares") or 0),
                "holding": bool(merged.get("holding"))
                or (float(merged.get("avg_cost") or 0) > 0 and float(merged.get("shares") or 0) > 0),
            }
        )

    settings = []
    for row in settings_rows:
        item = dict(row)
        raw = decode_json(item.get("raw_json"), {})
        if isinstance(raw, dict):
            merged = {**raw, **item}
        else:
            merged = item
        settings.append(
            {
                "refresh_interval": int(merged.get("refresh_interval") or 60),
                "tag_colors": json.dumps(
                    decode_json(merged.get("tag_colors"), merged.get("tag_colors") or {}),
                    ensure_ascii=False,
                ),
                "default_period": merged.get("default_period") or "1M",
            }
        )

    if not settings:
        settings = [{"refresh_interval": 60, "tag_colors": "{}", "default_period": "1M"}]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "targets": targets,
        "assets": assets,
        "settings": settings[:1],
    }


def post_payload(web_app_url, token, payload, retries=2):
    body = dict(payload)
    body["token"] = token
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        web_app_url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    last_error = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read().decode("utf-8")
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Could not post payload: {last_error}") from last_error


def main():
    parser = argparse.ArgumentParser(
        description="Export the local Supabase backup as a Google Sheets migration payload."
    )
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help=f"Default: {DEFAULT_DB_PATH}")
    parser.add_argument("--out", default=str(DEFAULT_OUT_PATH), help=f"Default: {DEFAULT_OUT_PATH}")
    parser.add_argument("--web-app-url", help="Apps Script Web App URL. If set, the payload is posted.")
    parser.add_argument("--token", help="Migration token configured in Apps Script script properties.")
    args = parser.parse_args()

    payload = load_payload(Path(args.db))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Payload written: {out_path.resolve()}")
    print(f"Targets: {len(payload['targets'])}")
    print(f"Assets: {len(payload['assets'])}")
    print(f"Settings rows: {len(payload['settings'])}")

    if args.web_app_url or args.token:
        if not args.web_app_url or not args.token:
            raise SystemExit("--web-app-url and --token must be used together.")
        result = post_payload(args.web_app_url, args.token, payload)
        print(result)


if __name__ == "__main__":
    main()

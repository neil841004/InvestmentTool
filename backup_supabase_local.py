import argparse
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from supabase import create_client

DEFAULT_DB_PATH = Path("local_backups") / "investmenttool_backup.sqlite"
PAGE_SIZE = 1000
SUPABASE_RETRIES = 2


def load_supabase_credentials():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if url and key:
        return url, key

    secrets_path = Path(".streamlit") / "secrets.toml"
    if not secrets_path.exists():
        raise FileNotFoundError(
            "Missing Supabase credentials. Set SUPABASE_URL/SUPABASE_KEY or create .streamlit/secrets.toml."
        )

    try:
        import tomllib

        with secrets_path.open("rb") as f:
            data = tomllib.load(f)
    except ImportError:
        data = {}
        current_section = None
        with secrets_path.open("r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    current_section = line[1:-1]
                    data[current_section] = {}
                elif "=" in line and current_section:
                    key_name, _, value = line.partition("=")
                    data[current_section][key_name.strip()] = value.strip().strip('"')

    supabase = data.get("supabase", {})
    url = supabase.get("url")
    key = supabase.get("key")
    if not url or not key:
        raise ValueError("Missing supabase.url or supabase.key in .streamlit/secrets.toml.")
    return url, key


def fetch_table(sb, table_name, order_columns):
    rows = []
    start = 0
    while True:
        response = execute_fetch_page(sb, table_name, order_columns, start)
        batch = response.data or []
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            return rows
        start += PAGE_SIZE


def execute_fetch_page(sb, table_name, order_columns, start):
    last_error = None
    for attempt in range(SUPABASE_RETRIES + 1):
        try:
            query = sb.table(table_name).select("*")
            for column in order_columns:
                query = query.order(column)
            return query.range(start, start + PAGE_SIZE - 1).execute()
        except Exception as exc:
            last_error = exc
            if attempt < SUPABASE_RETRIES:
                time.sleep(0.5 * (attempt + 1))

    message = summarize_error(last_error)
    raise RuntimeError(f"Could not fetch Supabase table '{table_name}': {message}") from last_error


def summarize_error(error):
    message = str(error)
    if "522" in message or "Connection timed out" in message:
        return "Cloudflare 522 connection timed out while contacting Supabase."
    if "<!DOCTYPE html>" in message:
        return "Supabase returned an HTML error page instead of JSON."
    return message[:500]


def encode_json(value):
    return json.dumps(value if value is not None else None, ensure_ascii=False)


def prepare_database(conn):
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER,
            ticker TEXT PRIMARY KEY,
            custom_name TEXT DEFAULT '',
            note TEXT DEFAULT '',
            rating INTEGER DEFAULT 0,
            holding INTEGER DEFAULT 0,
            yahoo_url TEXT DEFAULT '',
            tradingview_url TEXT DEFAULT '',
            avg_cost REAL DEFAULT 0,
            shares REAL DEFAULT 0,
            tags TEXT DEFAULT '[]',
            display_order INTEGER DEFAULT 0,
            created_at TEXT,
            raw_json TEXT NOT NULL,
            backed_up_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY,
            refresh_interval INTEGER,
            tag_colors TEXT DEFAULT '{}',
            default_period TEXT,
            raw_json TEXT NOT NULL,
            backed_up_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS backup_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            backed_up_at TEXT NOT NULL,
            source_url TEXT NOT NULL,
            watchlist_count INTEGER NOT NULL,
            settings_count INTEGER NOT NULL,
            db_path TEXT NOT NULL
        )
        """
    )


def write_backup(conn, watchlist_rows, settings_rows, source_url, db_path):
    backed_up_at = datetime.now(timezone.utc).isoformat()

    with conn:
        prepare_database(conn)
        conn.execute("DELETE FROM watchlist")
        conn.execute("DELETE FROM settings")

        conn.executemany(
            """
            INSERT INTO watchlist (
                id, ticker, custom_name, note, rating, holding, yahoo_url,
                tradingview_url, avg_cost, shares, tags, display_order,
                created_at, raw_json, backed_up_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row.get("id"),
                    row.get("ticker"),
                    row.get("custom_name", ""),
                    row.get("note", ""),
                    row.get("rating", 0),
                    1 if row.get("holding") else 0,
                    row.get("yahoo_url", ""),
                    row.get("tradingview_url", ""),
                    row.get("avg_cost", 0.0),
                    row.get("shares", 0.0),
                    encode_json(row.get("tags", [])),
                    row.get("display_order", 0),
                    row.get("created_at"),
                    encode_json(row),
                    backed_up_at,
                )
                for row in watchlist_rows
                if row.get("ticker")
            ],
        )

        conn.executemany(
            """
            INSERT INTO settings (
                id, refresh_interval, tag_colors, default_period, raw_json, backed_up_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row.get("id", 1),
                    row.get("refresh_interval"),
                    encode_json(row.get("tag_colors", {})),
                    row.get("default_period"),
                    encode_json(row),
                    backed_up_at,
                )
                for row in settings_rows
            ],
        )

        conn.execute(
            """
            INSERT INTO backup_runs (
                backed_up_at, source_url, watchlist_count, settings_count, db_path
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (backed_up_at, source_url, len(watchlist_rows), len(settings_rows), str(db_path)),
        )

    return backed_up_at


def main():
    parser = argparse.ArgumentParser(
        description="Back up Supabase watchlist/settings tables to a local SQLite database."
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help=f"SQLite backup path. Default: {DEFAULT_DB_PATH}",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    supabase_url, supabase_key = load_supabase_credentials()
    sb = create_client(supabase_url, supabase_key)

    watchlist_rows = fetch_table(sb, "watchlist", ["display_order", "id"])
    settings_rows = fetch_table(sb, "settings", ["id"])

    with sqlite3.connect(db_path) as conn:
        backed_up_at = write_backup(conn, watchlist_rows, settings_rows, supabase_url, db_path)

    print(f"Backed up {len(watchlist_rows)} watchlist rows and {len(settings_rows)} settings rows.")
    print(f"SQLite backup: {db_path.resolve()}")
    print(f"Backup time: {backed_up_at}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        raise SystemExit(f"Backup failed: {summarize_error(exc)}")

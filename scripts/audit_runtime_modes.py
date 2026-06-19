from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path


APP_NAME = "TrashSorter"
LOG_PATTERNS = (
    "TEST OFF",
    "TEST ON",
    "dispatch evidence",
    "uart sort",
    "ACK",
    "manual reference corrected",
    "visual safety",
    "blocked",
)


@dataclass(frozen=True)
class TableInfo:
    database: str
    table: str
    columns: tuple[str, ...]
    row_count: int | None


def appdata_dir() -> Path:
    return Path(os.environ.get("APPDATA", "")) / APP_NAME


def read_runtime_model(config_path: Path) -> str | None:
    if not config_path.exists():
        return None
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    model = payload.get("model")
    if isinstance(model, dict):
        path = model.get("path")
        if isinstance(path, str):
            return path
    return None


def inspect_database(path: Path) -> list[TableInfo]:
    if not path.exists():
        return []
    out: list[TableInfo] = []
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=1)
    except sqlite3.Error as exc:
        print(f"  database_open_error={exc}")
        return []
    try:
        try:
            rows = con.execute(
                "select name from sqlite_master where type='table' order by name"
            ).fetchall()
        except sqlite3.Error as exc:
            print(f"  database_schema_error={exc}")
            return []
        for (table,) in rows:
            try:
                columns = tuple(
                    str(row[1])
                    for row in con.execute(f"pragma table_info({quote_ident(table)})")
                )
            except sqlite3.Error:
                columns = ()
            row_count: int | None = None
            try:
                row_count = int(
                    con.execute(f"select count(*) from {quote_ident(table)}").fetchone()[0]
                )
            except sqlite3.Error:
                row_count = None
            out.append(
                TableInfo(
                    database=path.name,
                    table=str(table),
                    columns=columns,
                    row_count=row_count,
                )
            )
    finally:
        con.close()
    return out


def quote_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def latest_rows(path: Path, table: str, limit: int) -> list[dict[str, object]]:
    if not path.exists():
        return []
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        columns = [row[1] for row in con.execute(f"pragma table_info({quote_ident(table)})")]
        if not columns:
            return []
        order_column = pick_order_column(columns)
        query = f"select * from {quote_ident(table)}"
        if order_column:
            query += f" order by {quote_ident(order_column)} desc"
        query += " limit ?"
        rows = con.execute(query, (limit,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        con.close()


def pick_order_column(columns: list[str]) -> str | None:
    for candidate in (
        "created_at",
        "timestamp",
        "ts",
        "time",
        "updated_at",
        "id",
    ):
        if candidate in columns:
            return candidate
    return None


def find_history_like_tables(tables: list[TableInfo]) -> list[TableInfo]:
    wanted_names = ("history", "classification", "event", "sort", "item")
    wanted_columns = ("class", "label", "route", "bin", "confidence", "owner", "result")
    out: list[TableInfo] = []
    for info in tables:
        table_l = info.table.lower()
        cols_l = " ".join(info.columns).lower()
        if any(name in table_l for name in wanted_names) or any(
            col in cols_l for col in wanted_columns
        ):
            out.append(info)
    return out


def read_recent_log_lines(log_path: Path, tail_bytes: int) -> tuple[dict[str, int], list[str]]:
    if not log_path.exists():
        return {}, []
    size = log_path.stat().st_size
    with log_path.open("rb") as fh:
        fh.seek(max(0, size - tail_bytes))
        data = fh.read()
    text = data.decode("utf-8", errors="replace")
    counts = {pattern: 0 for pattern in LOG_PATTERNS}
    lines: list[str] = []
    for raw in text.splitlines():
        matched = [pattern for pattern in LOG_PATTERNS if pattern in raw]
        if not matched:
            continue
        for pattern in matched:
            counts[pattern] += 1
        lines.append(summarize_log_line(raw))
    return counts, lines


def summarize_log_line(raw: str) -> str:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    record = payload.get("record")
    if isinstance(record, dict):
        time = record.get("time")
        time_repr = ""
        if isinstance(time, dict):
            time_repr = str(time.get("repr") or "")
        message = record.get("message")
        if isinstance(message, str):
            return f"{time_repr} | {message}"
    text = payload.get("text")
    if isinstance(text, str):
        return text.rstrip()
    return raw


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Read-only runtime mode audit.")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--log-lines", type=int, default=24)
    parser.add_argument("--tail-bytes", type=int, default=600_000)
    args = parser.parse_args()

    base = appdata_dir()
    print(f"APPDATA_DIR={base}")
    print(f"RUNTIME_MODEL={read_runtime_model(base / 'config.json')}")

    all_tables: list[TableInfo] = []
    for db_name in ("history.db", "operations.db", "dataset.db", "auth.db"):
        db_path = base / db_name
        print(f"\nDATABASE {db_name} exists={db_path.exists()} size={db_path.stat().st_size if db_path.exists() else 0}")
        tables = inspect_database(db_path)
        all_tables.extend(tables)
        for info in tables:
            print(
                f"  table={info.table} rows={info.row_count} cols={','.join(info.columns[:12])}"
            )

    print("\nHISTORY_LIKE_LATEST")
    for info in find_history_like_tables(all_tables):
        rows = latest_rows(base / info.database, info.table, args.limit)
        print(f"  {info.database}.{info.table}")
        for row in rows:
            preview = {key: row.get(key) for key in list(row)[:10]}
            print(f"    {json.dumps(preview, ensure_ascii=False, default=str)}")

    log_path = base / "logs" / "app-2026-06-19.log"
    print(f"\nRECENT_LOG_EVENTS {log_path}")
    counts, lines = read_recent_log_lines(log_path, args.tail_bytes)
    for key, value in counts.items():
        if value:
            print(f"  count[{key}]={value}")
    for line in lines[-args.log_lines :]:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

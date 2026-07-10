"""
export.py — 数据导出工具
支持将各表导出为 ndjson 或 csv，方便迁移到 PostgreSQL 或分析使用。

用法：
    python export.py                      # 导出全部表到 ./exports/
    python export.py --table hot_rank     # 只导出指定表
    python export.py --format csv         # 导出为 csv（默认 ndjson）
    python export.py --since 2026-07-01   # 只导出指定日期后的数据
"""
import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

from database import get_conn, init_db

TABLES = ["hot_rank", "news", "guba_posts", "hk_quote", "capital_flow"]
EXPORT_DIR = Path("exports")


def export_table(table: str, fmt: str = "ndjson", since: str = None) -> int:
    conn = get_conn()
    if since and table in ("hot_rank", "news", "guba_posts", "hk_quote", "capital_flow"):
        rows = conn.execute(
            f"SELECT * FROM {table} WHERE collected_at >= ?", (since,)
        ).fetchall()
    else:
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    conn.close()

    if not rows:
        print(f"[export] {table}: 0 条，跳过")
        return 0

    EXPORT_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = EXPORT_DIR / f"{table}_{ts}.{fmt}"

    if fmt == "ndjson":
        with out.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(dict(row), ensure_ascii=False) + "\n")
    elif fmt == "csv":
        with out.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows([dict(r) for r in rows])

    print(f"[export] {table}: {len(rows)} 条 → {out}")
    return len(rows)


def export_all(fmt: str = "ndjson", since: str = None):
    total = 0
    for table in TABLES:
        total += export_table(table, fmt=fmt, since=since)
    print(f"[export] 完成，共 {total} 条")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="导出数据库到 ndjson/csv")
    parser.add_argument("--table", choices=TABLES, help="指定导出的表，默认全部")
    parser.add_argument("--format", choices=["ndjson", "csv"], default="ndjson")
    parser.add_argument("--since", help="只导出 collected_at >= 此日期（YYYY-MM-DD）")
    args = parser.parse_args()

    init_db()
    if args.table:
        export_table(args.table, fmt=args.format, since=args.since)
    else:
        export_all(fmt=args.format, since=args.since)

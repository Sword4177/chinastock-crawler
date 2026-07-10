import sqlite3
from pathlib import Path
from config import DB_PATH

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """按文件名顺序执行 migrations/ 下所有 .sql 文件。"""
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()

    applied = {r[0] for r in conn.execute("SELECT filename FROM schema_migrations").fetchall()}

    for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if sql_file.name in applied:
            continue
        conn.executescript(sql_file.read_text(encoding="utf-8"))
        conn.execute("INSERT INTO schema_migrations (filename) VALUES (?)", (sql_file.name,))
        conn.commit()
        print(f"[migration] applied {sql_file.name}")

    conn.close()


if __name__ == "__main__":
    init_db()
    print("数据库初始化完成:", DB_PATH)

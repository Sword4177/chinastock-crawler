-- 股吧帖子表

CREATE TABLE IF NOT EXISTS guba_posts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id      TEXT UNIQUE,
    stock_code   TEXT NOT NULL,
    title        TEXT,
    content      TEXT,
    author       TEXT,
    read_count   INTEGER,
    reply_count  INTEGER,
    sentiment    REAL,
    updated_at   TEXT,
    collected_at TEXT NOT NULL
);

-- 清理 hot_rank 历史重复行（保留每组最小 id）
DELETE FROM hot_rank WHERE id NOT IN (
    SELECT MIN(id) FROM hot_rank
    GROUP BY source, COALESCE(stock_code, ''), date(collected_at)
);

-- hot_rank 去重：同一数据源同一股票同一天只保留一条
CREATE UNIQUE INDEX IF NOT EXISTS idx_hot_rank_dedup
    ON hot_rank (source, COALESCE(stock_code, ''), date(collected_at));

-- 清理 news 历史重复行
DELETE FROM news WHERE id NOT IN (
    SELECT MIN(id) FROM news
    GROUP BY source, COALESCE(title, ''), COALESCE(published_at, '')
);

-- news 去重：同一来源同一标题同一发布时间只入库一次
CREATE UNIQUE INDEX IF NOT EXISTS idx_news_dedup
    ON news (source, COALESCE(title, ''), COALESCE(published_at, ''));

-- 股票主数据表
CREATE TABLE IF NOT EXISTS stocks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol     TEXT NOT NULL UNIQUE,  -- 统一格式：600000.SH / 00700.HK
    code       TEXT NOT NULL,         -- 原始代码：600000 / 00700
    name       TEXT,
    market     TEXT NOT NULL,         -- A / HK / US
    exchange   TEXT,                  -- SSE / SZSE / HKEX
    currency   TEXT DEFAULT 'CNY',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 采集任务记录表
CREATE TABLE IF NOT EXISTS source_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    status      TEXT NOT NULL DEFAULT 'running',  -- running / success / failed
    row_count   INTEGER DEFAULT 0,
    error       TEXT
);

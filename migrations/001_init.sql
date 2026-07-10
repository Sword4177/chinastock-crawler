-- 初始表结构

CREATE TABLE IF NOT EXISTS hot_rank (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source       TEXT NOT NULL,
    rank         INTEGER,
    stock_code   TEXT,
    stock_name   TEXT,
    score        REAL,
    collected_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS news (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source       TEXT NOT NULL,
    stock_code   TEXT,
    title        TEXT,
    content      TEXT,
    sentiment    REAL,
    published_at TEXT,
    collected_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS capital_flow (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    market       TEXT NOT NULL,
    trade_date   TEXT NOT NULL,
    net_inflow   REAL,
    buy_amount   REAL,
    sell_amount  REAL,
    collected_at TEXT NOT NULL,
    UNIQUE(market, trade_date)
);

CREATE TABLE IF NOT EXISTS hk_quote (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code     TEXT NOT NULL,
    current        REAL,
    percent        REAL,
    volume         INTEGER,
    market_capital REAL,
    high           REAL,
    low            REAL,
    open           REAL,
    collected_at   TEXT NOT NULL,
    UNIQUE(stock_code, collected_at)
);

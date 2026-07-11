"""
repository.py — 数据访问层
所有 SQL 集中在此，业务代码不直接操作 DB。
"""
import re
from datetime import datetime
from database import get_conn


# ── stocks 主档 ────────────────────────────────────────────────────────────────

def _derive_symbol(code: str, market: str) -> tuple[str, str, str]:
    """根据代码和市场推导 (symbol, market, exchange)。
    输入先做 normalization：去掉前后缀、验证格式，无法识别的返回 (None, None, None)。

    A股：6xxxxx→.SH(SSE)，0/1/2/3xxxxx→.SZ(SZSE)，4/8/9xxxxx 北交所暂不处理跳过
    港股：去掉 HK 前缀和 .HK 后缀，补齐 5 位纯数字
    """
    if not code:
        return None, None, None

    code = str(code).strip()

    if market == "HK":
        # 去掉 HK/hk 前缀和 .HK 后缀
        code = re.sub(r'^(?:HK|hk)', '', code)
        code = re.sub(r'\.HK$', '', code, flags=re.IGNORECASE)
        if not code.isdigit():
            return None, None, None
        code = code.zfill(5)  # 港股补齐 5 位
        return f"{code}.HK", "HK", "HKEX"

    # A股：去掉已有后缀
    code = re.sub(r'\.(SH|SZ|BJ)$', '', code, flags=re.IGNORECASE)
    if not code.isdigit() or len(code) != 6:
        return None, None, None

    if code.startswith("6"):
        return f"{code}.SH", "A", "SSE"
    elif code[0] in ("0", "1", "2", "3"):
        return f"{code}.SZ", "A", "SZSE"
    else:
        # 4/8/9xxxxx 含北交所，暂不处理
        return None, None, None


def upsert_stock(code: str, name: str, market: str) -> None:
    """写入或更新股票主档（以 symbol 为唯一键）。
    name 用 COALESCE 保留已有非空值，不会被 None 覆盖。
    """
    symbol, mkt, exchange = _derive_symbol(code, market)
    if not symbol:
        return
    currency = "HKD" if market == "HK" else "CNY"
    conn = get_conn()
    conn.execute(
        """INSERT INTO stocks (symbol, code, name, market, exchange, currency)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(symbol) DO UPDATE SET
               name = COALESCE(excluded.name, stocks.name)""",
        (symbol, code, name, mkt, exchange, currency),
    )
    conn.commit()
    conn.close()


# ── hot_rank ───────────────────────────────────────────────────────────────────

def insert_hot_rank(rows: list[tuple]) -> int:
    """批量写入热股排行（每日快照口径，同源同股同天重复则忽略）。rows: [(source, rank, stock_code, stock_name, score, collected_at)]"""
    # 同步 stocks 主档
    for source, rank, code, name, score, collected_at in rows:
        market = "HK" if "hk" in (source or "").lower() else "A"
        upsert_stock(code, name, market)

    conn = get_conn()
    before = conn.total_changes
    conn.executemany(
        "INSERT OR IGNORE INTO hot_rank (source, rank, stock_code, stock_name, score, collected_at) VALUES (?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    n = conn.total_changes - before
    conn.close()
    return n


def get_top_hot_stocks(n: int = 20, date: str = None) -> list[str]:
    """返回指定日期东财热股榜 Top N 股票代码。"""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    rows = conn.execute(
        """SELECT stock_code FROM hot_rank
           WHERE source = 'eastmoney_hot' AND collected_at LIKE ?
           GROUP BY stock_code ORDER BY MIN(rank) ASC LIMIT ?""",
        (f"{date}%", n),
    ).fetchall()
    conn.close()
    return [r["stock_code"] for r in rows if r["stock_code"]]


# ── news ───────────────────────────────────────────────────────────────────────

def insert_news(rows: list[tuple]) -> int:
    """批量写入新闻（同源同标题同发布时间重复则忽略）。rows: [(source, stock_code, title, content, sentiment, published_at, collected_at)]"""
    conn = get_conn()
    before = conn.total_changes
    conn.executemany(
        "INSERT OR IGNORE INTO news (source, stock_code, title, content, sentiment, published_at, collected_at) VALUES (?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    n = conn.total_changes - before
    conn.close()
    return n


def get_unscored_news() -> list[dict]:
    """返回所有未打情感分的新闻。"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, title, content FROM news WHERE sentiment IS NULL"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_news_sentiment(news_id: int, score: float) -> None:
    conn = get_conn()
    conn.execute("UPDATE news SET sentiment = ? WHERE id = ?", (score, news_id))
    conn.commit()
    conn.close()


# ── capital_flow ───────────────────────────────────────────────────────────────

def insert_capital_flow(rows: list[tuple]) -> int:
    """批量写入资金流向（UNIQUE(market, trade_date) 约束已在 001_init.sql，重复则忽略）。rows: [(market, trade_date, net_inflow, buy_amount, sell_amount, collected_at)]"""
    conn = get_conn()
    before = conn.total_changes
    conn.executemany(
        "INSERT OR IGNORE INTO capital_flow (market, trade_date, net_inflow, buy_amount, sell_amount, collected_at) VALUES (?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    n = conn.total_changes - before
    conn.close()
    return n


# ── hk_quote ──────────────────────────────────────────────────────────────────

def upsert_hk_quote(stock_code: str, item: dict, collected_at: str) -> int:
    """写入或替换单支港股行情，返回 1 表示写入成功。"""
    upsert_stock(stock_code, item.get("name") or stock_code, "HK")
    conn = get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO hk_quote
           (stock_code, current, percent, volume, market_capital, high, low, open, collected_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (stock_code, item.get("current"), item.get("percent"), item.get("volume"),
         item.get("market_capital"), item.get("high"), item.get("low"),
         item.get("open"), collected_at),
    )
    conn.commit()
    conn.close()
    return 1


# ── guba_posts ─────────────────────────────────────────────────────────────────

def upsert_guba_post(post: dict) -> int:
    """写入或更新单条股吧帖子，返回 1 表示写入成功。"""
    upsert_stock(post.get("stock_code"), None, "A")
    conn = get_conn()
    exists = conn.execute(
        "SELECT id FROM guba_posts WHERE post_id = ?", (post["post_id"],)
    ).fetchone()
    if exists:
        conn.execute(
            """UPDATE guba_posts
               SET read_count=?, reply_count=?, title=?, author=?, updated_at=?, collected_at=?
               WHERE post_id=?""",
            (post["read_count"], post["reply_count"], post["title"], post["author"],
             post["updated_at"], post["collected_at"], post["post_id"]),
        )
        if post.get("content"):
            conn.execute(
                "UPDATE guba_posts SET content=?, sentiment=? WHERE post_id=?",
                (post["content"], post["sentiment"], post["post_id"]),
            )
    else:
        conn.execute(
            """INSERT INTO guba_posts
               (post_id, stock_code, title, content, author, read_count, reply_count, sentiment, updated_at, collected_at)
               VALUES (:post_id, :stock_code, :title, :content, :author, :read_count, :reply_count, :sentiment, :updated_at, :collected_at)""",
            post,
        )
    conn.commit()
    conn.close()
    return 1


# ── source_runs ────────────────────────────────────────────────────────────────

def start_source_run(source: str) -> int:
    """记录采集任务开始，返回 run_id。"""
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO source_runs (source, started_at) VALUES (?, ?)",
        (source, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    run_id = cur.lastrowid
    conn.commit()
    conn.close()
    return run_id


def finish_source_run(run_id: int, status: str, row_count: int = 0, error: str = None) -> None:
    """记录采集任务结束。status: 'success' | 'failed'"""
    conn = get_conn()
    conn.execute(
        "UPDATE source_runs SET finished_at=?, status=?, row_count=?, error=? WHERE id=?",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), status, row_count, error, run_id),
    )
    conn.commit()
    conn.close()


# ── 统计 ───────────────────────────────────────────────────────────────────────

def get_daily_stats(date: str) -> dict:
    """返回指定日期各表采集数量。"""
    conn = get_conn()
    like = f"{date}%"
    stats = {
        "hot_count":  conn.execute("SELECT COUNT(*) FROM hot_rank WHERE collected_at LIKE ?", (like,)).fetchone()[0],
        "news_count": conn.execute("SELECT COUNT(*) FROM news WHERE collected_at LIKE ?", (like,)).fetchone()[0],
        "hk_count":   conn.execute("SELECT COUNT(*) FROM hk_quote WHERE collected_at LIKE ?", (like,)).fetchone()[0],
        "guba_count": conn.execute("SELECT COUNT(*) FROM guba_posts WHERE collected_at LIKE ?", (like,)).fetchone()[0],
    }
    conn.close()
    return stats

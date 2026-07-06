"""
东方财富股吧爬虫 — 覆盖热股榜 Top 20
采集帖子列表 + 高热帖正文 + 情感打分
"""
import requests
import time
from bs4 import BeautifulSoup
from datetime import datetime
from database import get_conn, init_db

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://guba.eastmoney.com",
}
NOW = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

BULLISH = ["涨", "突破", "利好", "增长", "超预期", "买入", "新高", "强势", "上涨", "盈利", "看多", "拉升"]
BEARISH = ["跌", "暴跌", "利空", "亏损", "低迷", "卖出", "新低", "弱势", "下跌", "看空", "崩了", "割肉"]


def score(text: str) -> float:
    if not text:
        return 0.0
    bull = sum(1 for w in BULLISH if w in text)
    bear = sum(1 for w in BEARISH if w in text)
    total = bull + bear
    return round((bull - bear) / total, 3) if total else 0.0


def init_guba_table():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS guba_posts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id     TEXT UNIQUE,
            stock_code  TEXT NOT NULL,
            title       TEXT,
            content     TEXT,
            author      TEXT,
            read_count  INTEGER,
            reply_count INTEGER,
            sentiment   REAL,
            updated_at  TEXT,
            collected_at TEXT NOT NULL
        )
    """)
    # 兼容旧表（没有 content/sentiment 列）
    try:
        conn.execute("ALTER TABLE guba_posts ADD COLUMN content TEXT")
        conn.execute("ALTER TABLE guba_posts ADD COLUMN sentiment REAL")
    except Exception:
        pass
    conn.commit()
    conn.close()


def fetch_post_content(post_id: str, stock_code: str) -> str:
    """抓取单帖正文"""
    url = f"https://guba.eastmoney.com/news,{stock_code},{post_id}.html"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        node = soup.find(id="newscontent")
        if node:
            return node.get_text(separator=" ", strip=True)[:2000]
    except Exception:
        pass
    return ""


def fetch_guba(stock_code: str, pages: int = 2) -> list[dict]:
    """抓取帖子列表"""
    posts = []
    for page in range(1, pages + 1):
        url = f"https://guba.eastmoney.com/list,{stock_code},{page}.html"
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            for item in soup.find_all(class_="listitem"):
                title_tag = item.select_one("div.title a")
                author_tag = item.select_one("div.author a")
                read_tag = item.select_one("div.read")
                reply_tag = item.select_one("div.reply")
                update_tag = item.select_one("div.update")
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)
                posts.append({
                    "post_id": title_tag.get("data-postid", ""),
                    "stock_code": stock_code,
                    "title": title,
                    "content": None,
                    "author": author_tag.get_text(strip=True) if author_tag else None,
                    "read_count": int(read_tag.get_text(strip=True).replace(",", "")) if read_tag else 0,
                    "reply_count": int(reply_tag.get_text(strip=True).replace(",", "")) if reply_tag else 0,
                    "sentiment": score(title),
                    "updated_at": update_tag.get_text(strip=True) if update_tag else None,
                    "collected_at": NOW,
                })
            time.sleep(0.5)
        except Exception as e:
            print(f"  [{stock_code}] p{page} 失败: {e}")
    return posts


def enrich_top_posts(posts: list[dict], top_n: int = 5):
    """对阅读量最高的 top_n 条抓正文并更新情感分"""
    top = sorted(posts, key=lambda x: x["read_count"], reverse=True)[:top_n]
    for p in top:
        if not p["post_id"]:
            continue
        content = fetch_post_content(p["post_id"], p["stock_code"])
        if content:
            p["content"] = content
            p["sentiment"] = score(p["title"] + " " + content)
        time.sleep(0.3)


def save_posts(posts: list[dict]):
    if not posts:
        return
    conn = get_conn()
    for p in posts:
        exists = conn.execute(
            "SELECT id FROM guba_posts WHERE post_id = ?", (p["post_id"],)
        ).fetchone()
        if exists:
            # 每次都更新热度数据和采集时间，有正文时一并更新
            conn.execute(
                """UPDATE guba_posts
                   SET read_count=?, reply_count=?, collected_at=?
                   WHERE post_id=?""",
                (p["read_count"], p["reply_count"], p["collected_at"], p["post_id"]),
            )
            if p.get("content"):
                conn.execute(
                    "UPDATE guba_posts SET content=?, sentiment=? WHERE post_id=?",
                    (p["content"], p["sentiment"], p["post_id"]),
                )
        else:
            conn.execute(
                """INSERT INTO guba_posts
                   (post_id, stock_code, title, content, author, read_count, reply_count, sentiment, updated_at, collected_at)
                   VALUES (:post_id, :stock_code, :title, :content, :author, :read_count, :reply_count, :sentiment, :updated_at, :collected_at)""",
                p,
            )
    conn.commit()
    conn.close()


def get_top_hot_stocks(n: int = 20) -> list[str]:
    conn = get_conn()
    today = datetime.now().strftime("%Y-%m-%d")
    rows = conn.execute(
        """SELECT stock_code FROM hot_rank
           WHERE source = 'eastmoney_hot' AND collected_at LIKE ?
           GROUP BY stock_code ORDER BY MIN(rank) ASC LIMIT ?""",
        (f"{today}%", n),
    ).fetchall()
    conn.close()
    return [r["stock_code"] for r in rows if r["stock_code"]]


def run(stock_codes: list[str] = None):
    init_db()
    init_guba_table()

    if stock_codes is None:
        stock_codes = get_top_hot_stocks(20)

    if not stock_codes:
        print("[股吧] 热股榜为空，先跑一次 pipeline 再来")
        return

    total = 0
    print(f"[股吧] 开始抓取 {len(stock_codes)} 支股票")
    for code in stock_codes:
        posts = fetch_guba(code, pages=2)
        enrich_top_posts(posts, top_n=5)
        save_posts(posts)
        with_content = sum(1 for p in posts if p["content"])
        print(f"  [{code}] {len(posts)} 条，{with_content} 条含正文")
        total += len(posts)
        time.sleep(0.3)

    print(f"[股吧] 共入库 {total} 条")


if __name__ == "__main__":
    run()

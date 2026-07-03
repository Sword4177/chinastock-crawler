"""
东方财富股吧爬虫 — 覆盖热股榜 Top 20
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


def init_guba_table():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS guba_posts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id     TEXT UNIQUE,
            stock_code  TEXT NOT NULL,
            title       TEXT,
            author      TEXT,
            read_count  INTEGER,
            reply_count INTEGER,
            updated_at  TEXT,
            collected_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def fetch_guba(stock_code: str, pages: int = 2) -> list[dict]:
    """抓取指定股票股吧帖子列表"""
    posts = []
    for page in range(1, pages + 1):
        url = f"https://guba.eastmoney.com/list,{stock_code},{page}.html"
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            items = soup.find_all(class_="listitem")
            for item in items:
                title_tag = item.select_one("div.title a")
                author_tag = item.select_one("div.author a")
                read_tag = item.select_one("div.read")
                reply_tag = item.select_one("div.reply")
                update_tag = item.select_one("div.update")
                if not title_tag:
                    continue
                posts.append({
                    "post_id": title_tag.get("data-postid", ""),
                    "stock_code": stock_code,
                    "title": title_tag.get_text(strip=True),
                    "author": author_tag.get_text(strip=True) if author_tag else None,
                    "read_count": int(read_tag.get_text(strip=True).replace(",", "")) if read_tag else 0,
                    "reply_count": int(reply_tag.get_text(strip=True).replace(",", "")) if reply_tag else 0,
                    "updated_at": update_tag.get_text(strip=True) if update_tag else None,
                    "collected_at": NOW,
                })
            time.sleep(0.5)
        except Exception as e:
            print(f"  [{stock_code}] p{page} 失败: {e}")
    return posts


def save_posts(posts: list[dict]):
    if not posts:
        return
    conn = get_conn()
    conn.executemany(
        """INSERT OR IGNORE INTO guba_posts
           (post_id, stock_code, title, author, read_count, reply_count, updated_at, collected_at)
           VALUES (:post_id, :stock_code, :title, :author, :read_count, :reply_count, :updated_at, :collected_at)""",
        posts,
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
        save_posts(posts)
        print(f"  [{code}] {len(posts)} 条")
        total += len(posts)
        time.sleep(0.3)

    print(f"[股吧] 共入库 {total} 条")


if __name__ == "__main__":
    run()

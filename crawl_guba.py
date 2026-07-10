"""
东方财富股吧爬虫 — 覆盖热股榜 Top 20
采集帖子列表 + 高热帖正文 + 情感打分
"""
import requests
import time
from bs4 import BeautifulSoup
from datetime import datetime
from database import init_db
from repository import upsert_guba_post, get_top_hot_stocks

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
    """已由 migrations/002_guba_posts.sql 处理，保留此函数避免 pipeline.py 调用报错。"""
    pass


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


def save_posts(posts: list[dict]) -> int:
    return sum(upsert_guba_post(p) for p in posts)




def run(stock_codes: list[str] = None) -> int:
    init_db()
    init_guba_table()

    if stock_codes is None:
        stock_codes = get_top_hot_stocks(20)

    if not stock_codes:
        print("[股吧] 热股榜为空，先跑一次 pipeline 再来")
        return 0

    total = 0
    print(f"[股吧] 开始抓取 {len(stock_codes)} 支股票")
    for code in stock_codes:
        posts = fetch_guba(code, pages=2)
        enrich_top_posts(posts, top_n=5)
        written = save_posts(posts)
        with_content = sum(1 for p in posts if p["content"])
        print(f"  [{code}] 抓到 {len(posts)} 条，写入 {written} 条，{with_content} 条含正文")
        total += written
        time.sleep(0.3)

    print(f"[股吧] 共写入 {total} 条")
    return total


if __name__ == "__main__":
    run()

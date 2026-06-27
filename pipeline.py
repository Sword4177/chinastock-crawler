"""
每日 pipeline：热股榜 → 批量个股新闻 → 情感打分 → 入库
"""
import akshare as ak
from datetime import datetime
from database import get_conn, init_db
from collect_a_sentiment import (
    collect_hot_rank, collect_hot_up_rank, collect_stock_news, collect_telegraph,
    collect_xueqiu_hot, collect_xueqiu_follow, collect_investor_qa,
)
from collect_hk_sentiment import collect_southbound_flow, collect_hk_hot_rank
from collect_global_sentiment import collect_av_news

BULLISH_WORDS = ["涨", "突破", "利好", "增长", "超预期", "买入", "新高", "强势", "上涨", "盈利"]
BEARISH_WORDS = ["跌", "暴跌", "利空", "亏损", "低迷", "卖出", "新低", "弱势", "下跌", "亏损"]


def score_sentiment(text: str) -> float:
    """基于关键词的简单情感打分，返回 -1.0 到 1.0"""
    if not text:
        return 0.0
    bull = sum(1 for w in BULLISH_WORDS if w in text)
    bear = sum(1 for w in BEARISH_WORDS if w in text)
    total = bull + bear
    if total == 0:
        return 0.0
    return round((bull - bear) / total, 3)


def update_news_sentiment():
    """对 news 表中未打分的条目计算情感分"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, title, content FROM news WHERE sentiment IS NULL"
    ).fetchall()
    updated = 0
    for row in rows:
        text = (row["title"] or "") + " " + (row["content"] or "")
        score = score_sentiment(text)
        conn.execute("UPDATE news SET sentiment = ? WHERE id = ?", (score, row["id"]))
        updated += 1
    conn.commit()
    conn.close()
    print(f"[情感打分] {updated} 条更新")


def get_top_hot_stocks(n: int = 20) -> list[str]:
    """从 hot_rank 表取当日最热的 N 支股票（去重）"""
    conn = get_conn()
    today = datetime.now().strftime("%Y-%m-%d")
    rows = conn.execute(
        """
        SELECT stock_code FROM hot_rank
        WHERE source = 'eastmoney_hot' AND collected_at LIKE ?
        GROUP BY stock_code
        ORDER BY MIN(rank) ASC LIMIT ?
        """,
        (f"{today}%", n),
    ).fetchall()
    conn.close()
    return [r["stock_code"] for r in rows if r["stock_code"]]


def run():
    init_db()
    print(f"\n=== Pipeline 开始 {datetime.now().strftime('%Y-%m-%d %H:%M')} ===")

    print("\n--- Step 1: A股热股榜 ---")
    collect_hot_rank()
    collect_hot_up_rank()
    collect_xueqiu_hot()
    collect_xueqiu_follow()

    print("\n--- Step 2: 港股数据 ---")
    collect_southbound_flow()
    collect_hk_hot_rank()

    print("\n--- Step 3: 批量抓个股新闻 ---")
    top_stocks = get_top_hot_stocks(20)
    print(f"  热股前20: {top_stocks}")
    for code in top_stocks:
        collect_stock_news(code)

    print("\n--- Step 4: 财新新闻 + 互动易问答 + 全球宏观 ---")
    collect_telegraph()
    collect_investor_qa()
    collect_av_news()

    print("\n--- Step 5: 情感打分 ---")
    update_news_sentiment()

    print("\n=== Pipeline 完成 ===")


if __name__ == "__main__":
    run()

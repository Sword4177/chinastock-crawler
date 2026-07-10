"""
每日 pipeline：热股榜 → 批量个股新闻 → 情感打分 → 入库
"""
import os
import requests
from datetime import datetime
from database import init_db
from repository import (
    get_top_hot_stocks, get_daily_stats,
    get_unscored_news, update_news_sentiment,
)
from collect_a_sentiment import (
    collect_hot_rank, collect_hot_up_rank, collect_stock_news, collect_telegraph,
    collect_xueqiu_hot, collect_xueqiu_follow, collect_investor_qa,
)
from collect_hk_sentiment import collect_southbound_flow, collect_hk_hot_rank, collect_xueqiu_hk_quote
from collect_global_sentiment import collect_av_news
from crawl_guba import run as crawl_guba, init_guba_table

LARK_WEBHOOK = os.environ.get("LARK_WEBHOOK", "")

BULLISH_WORDS = ["涨", "突破", "利好", "增长", "超预期", "买入", "新高", "强势", "上涨", "盈利"]
BEARISH_WORDS = ["跌", "暴跌", "利空", "亏损", "低迷", "卖出", "新低", "弱势", "下跌", "亏损"]


def notify_lark(msg: str):
    if not LARK_WEBHOOK:
        return
    try:
        requests.post(LARK_WEBHOOK, json={"msg_type": "text", "content": {"text": msg}}, timeout=10)
    except Exception:
        pass


def _score(text: str) -> float:
    if not text:
        return 0.0
    bull = sum(1 for w in BULLISH_WORDS if w in text)
    bear = sum(1 for w in BEARISH_WORDS if w in text)
    total = bull + bear
    return round((bull - bear) / total, 3) if total else 0.0


def run_news_sentiment():
    """对 news 表中未打分的条目计算情感分。"""
    rows = get_unscored_news()
    for row in rows:
        text = (row["title"] or "") + " " + (row["content"] or "")
        update_news_sentiment(row["id"], _score(text))
    print(f"[情感打分] {len(rows)} 条更新")


def run():
    init_db()
    init_guba_table()
    start = datetime.now()
    print(f"\n=== Pipeline 开始 {start.strftime('%Y-%m-%d %H:%M')} ===")

    print("\n--- Step 1: A股热股榜 ---")
    collect_hot_rank()
    collect_hot_up_rank()
    collect_xueqiu_hot()
    collect_xueqiu_follow()

    print("\n--- Step 2: 港股数据 ---")
    collect_southbound_flow()
    collect_hk_hot_rank()
    collect_xueqiu_hk_quote()

    print("\n--- Step 3: 批量抓个股新闻 ---")
    top_stocks = get_top_hot_stocks(20)
    print(f"  热股前20: {top_stocks}")
    for code in top_stocks:
        collect_stock_news(code)

    print("\n--- Step 3.5: 股吧帖子 ---")
    crawl_guba(stock_codes=top_stocks)

    print("\n--- Step 4: 财新新闻 + 互动易问答 + 全球宏观 ---")
    collect_telegraph()
    collect_investor_qa()
    collect_av_news()

    print("\n--- Step 5: 情感打分 ---")
    run_news_sentiment()

    today = start.strftime("%Y-%m-%d")
    stats = get_daily_stats(today)
    elapsed = int((datetime.now() - start).total_seconds())

    msg = (
        f"✅ 数据采集完成 {today}\n"
        f"- 热股榜条目: {stats['hot_count']} 条\n"
        f"- 股吧帖子: {stats['guba_count']} 条\n"
        f"- 新闻/问答: {stats['news_count']} 条\n"
        f"- 港股行情: {stats['hk_count']} 支\n"
        f"- 耗时: {elapsed}秒"
    )
    print(f"\n=== Pipeline 完成 ===\n{msg}")
    notify_lark(msg)


if __name__ == "__main__":
    run()

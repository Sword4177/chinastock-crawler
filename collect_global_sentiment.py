"""
全球宏观情感采集：Alpha Vantage News Sentiment API
免费版限 25 次/天，每次跑抓 2 个 topic
"""
import requests
from datetime import datetime
from config import ALPHA_VANTAGE_KEY
from database import init_db
from exceptions import CollectorSkipped
from repository import insert_news

NOW = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
AV_URL = "https://www.alphavantage.co/query"
TOPICS = ["economy_fiscal", "economy_macro"]


def _parse_time(ts: str) -> str:
    """20260627T053724 → 2026-06-27 05:37:24"""
    try:
        return datetime.strptime(ts, "%Y%m%dT%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ts


def collect_av_news() -> int:
    """拉取 Alpha Vantage 宏观新闻情感（已含 ML 情感分，直接入库）"""
    if not ALPHA_VANTAGE_KEY:
        raise CollectorSkipped("ALPHA_VANTAGE_KEY 未设置")

    total = 0
    for topic in TOPICS:
        r = requests.get(
            AV_URL,
            params={"function": "NEWS_SENTIMENT", "topics": topic,
                    "limit": 50, "apikey": ALPHA_VANTAGE_KEY},
            timeout=20,
        )
        feed = r.json().get("feed", [])
        rows = [
            (f"alpha_vantage_{topic}", None,
             item.get("title"), item.get("summary"),
             float(item.get("overall_sentiment_score", 0)),
             _parse_time(item.get("time_published", "")), NOW)
            for item in feed
        ]
        n = insert_news(rows)
        total += n
        print(f"[Alpha Vantage {topic}] {n} 条")

    print(f"[Alpha Vantage] 共 {total} 条入库")
    return total


if __name__ == "__main__":
    init_db()
    collect_av_news()

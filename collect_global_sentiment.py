"""
全球宏观情感采集：Alpha Vantage News Sentiment API
免费版限 25 次/天，每次跑抓 2 个 topic
"""
import requests
from datetime import datetime
from config import ALPHA_VANTAGE_KEY
from database import get_conn, init_db

NOW = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
AV_URL = "https://www.alphavantage.co/query"

TOPICS = ["economy_fiscal", "economy_macro"]


def _parse_time(ts: str) -> str:
    """20260627T053724 → 2026-06-27 05:37:24"""
    try:
        return datetime.strptime(ts, "%Y%m%dT%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ts


def collect_av_news():
    """拉取 Alpha Vantage 宏观新闻情感（已含 ML 情感分，直接入库）"""
    if not ALPHA_VANTAGE_KEY:
        print("[Alpha Vantage] 未设置 ALPHA_VANTAGE_KEY，跳过")
        return

    conn = get_conn()
    total = 0
    for topic in TOPICS:
        try:
            r = requests.get(
                AV_URL,
                params={"function": "NEWS_SENTIMENT", "topics": topic,
                        "limit": 50, "apikey": ALPHA_VANTAGE_KEY},
                timeout=20,
            )
            data = r.json()
            feed = data.get("feed", [])
            rows = []
            for item in feed:
                rows.append((
                    f"alpha_vantage_{topic}",
                    None,
                    item.get("title"),
                    item.get("summary"),
                    float(item.get("overall_sentiment_score", 0)),
                    _parse_time(item.get("time_published", "")),
                    NOW,
                ))
            conn.executemany(
                "INSERT INTO news (source, stock_code, title, content, sentiment, published_at, collected_at) VALUES (?,?,?,?,?,?,?)",
                rows,
            )
            conn.commit()
            total += len(rows)
            print(f"[Alpha Vantage {topic}] {len(rows)} 条")
        except Exception as e:
            print(f"[Alpha Vantage {topic}] 失败: {e}")

    conn.close()
    print(f"[Alpha Vantage] 共 {total} 条入库")


if __name__ == "__main__":
    init_db()
    collect_av_news()

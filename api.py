"""
api.py — ChinaStocks 舆情 FastAPI 接口
复用 StockTwits 项目结构

运行：uvicorn api:app --reload --port 8002
"""
import logging
import traceback
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from database import get_conn, init_db

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(
    title="ChinaStocks Sentiment API",
    description="A股/港股舆情数据 API — 热股排行 + 单股情绪快照",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def query(sql: str, params: tuple = ()) -> list[dict]:
    try:
        conn = get_conn()
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error("DB query failed: %s\nSQL: %s\nParams: %s\n%s", e, sql, params, traceback.format_exc())
        raise HTTPException(status_code=500, detail="数据库查询失败，请稍后重试")


@app.on_event("startup")
def startup():
    init_db()


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "service": "ChinaStocks Sentiment API", "version": "1.0.0"}


# ── 热股排行 ───────────────────────────────────────────────────────────────────

@app.get("/api/hot", tags=["舆情"])
def hot_rank(
    source: str = Query(
        "eastmoney_hot",
        description="数据源: eastmoney_hot | eastmoney_up | xueqiu_tweet | xueqiu_follow",
    ),
    date: Optional[str] = Query(None, description="日期 YYYY-MM-DD，默认今天"),
    limit: int = Query(20, ge=1, le=100),
):
    """热股排行：按今日热度排名返回股票列表，支持多数据源切换。"""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    logger.info("GET /api/hot source=%s date=%s limit=%d", source, date, limit)

    rows = query(
        """
        SELECT stock_code, stock_name, MIN(rank) AS rank,
               source, AVG(score) AS score, COUNT(*) AS snapshots
        FROM hot_rank
        WHERE source = ? AND collected_at LIKE ?
        GROUP BY stock_code
        ORDER BY rank ASC
        LIMIT ?
        """,
        (source, f"{date}%", limit),
    )

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No data for source='{source}' on {date}",
        )

    return {"date": date, "source": source, "total": len(rows), "data": rows}


# ── 单股情绪快照 ────────────────────────────────────────────────────────────────

@app.get("/api/sentiment/{stock_code}", tags=["舆情"])
def stock_sentiment(
    stock_code: str,
    days: int = Query(7, ge=1, le=30, description="统计最近 N 天"),
):
    """
    单股情绪快照：综合新闻和股吧帖子，返回情感分、多空比例、热帖 Top 3。
    sentiment > 0 偏多，< 0 偏空，= 0 中性。
    """
    logger.info("GET /api/sentiment/%s days=%d", stock_code, days)
    since = f"datetime('now', '-{days} days')"

    news_stat = query(
        f"""
        SELECT COUNT(*) AS count,
               ROUND(AVG(sentiment), 3) AS avg_sentiment,
               SUM(CASE WHEN sentiment > 0 THEN 1 ELSE 0 END) AS bullish,
               SUM(CASE WHEN sentiment < 0 THEN 1 ELSE 0 END) AS bearish,
               SUM(CASE WHEN sentiment = 0 THEN 1 ELSE 0 END) AS neutral
        FROM news
        WHERE stock_code = ? AND sentiment IS NOT NULL
          AND collected_at >= {since}
        """,
        (stock_code,),
    )[0]

    guba_stat = query(
        f"""
        SELECT COUNT(*) AS count,
               ROUND(AVG(sentiment), 3) AS avg_sentiment,
               SUM(CASE WHEN sentiment > 0 THEN 1 ELSE 0 END) AS bullish,
               SUM(CASE WHEN sentiment < 0 THEN 1 ELSE 0 END) AS bearish,
               SUM(CASE WHEN sentiment = 0 THEN 1 ELSE 0 END) AS neutral,
               SUM(read_count) AS total_reads
        FROM guba_posts
        WHERE stock_code = ? AND sentiment IS NOT NULL
          AND collected_at >= {since}
        """,
        (stock_code,),
    )[0]

    top_posts = query(
        f"""
        SELECT post_id, title, sentiment, read_count, reply_count, updated_at
        FROM guba_posts
        WHERE stock_code = ? AND collected_at >= {since}
        ORDER BY read_count DESC
        LIMIT 3
        """,
        (stock_code,),
    )

    news_count = news_stat["count"] or 0
    guba_count = guba_stat["count"] or 0

    if news_count == 0 and guba_count == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No sentiment data for '{stock_code}' in last {days} days",
        )

    news_score = news_stat["avg_sentiment"] or 0.0
    guba_score = guba_stat["avg_sentiment"] or 0.0
    total = news_count + guba_count
    combined = round((news_score * news_count + guba_score * guba_count) / total, 3)

    return {
        "stock_code": stock_code,
        "days": days,
        "combined_sentiment": combined,
        "news": {
            "count": news_count,
            "avg_sentiment": news_score,
            "bullish": news_stat["bullish"] or 0,
            "bearish": news_stat["bearish"] or 0,
            "neutral": news_stat["neutral"] or 0,
        },
        "guba": {
            "count": guba_count,
            "avg_sentiment": guba_score,
            "bullish": guba_stat["bullish"] or 0,
            "bearish": guba_stat["bearish"] or 0,
            "neutral": guba_stat["neutral"] or 0,
            "total_reads": guba_stat["total_reads"] or 0,
        },
        "top_posts": top_posts,
    }

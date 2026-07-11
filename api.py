"""
api.py — ChinaStocks 舆情 FastAPI 接口

运行：uvicorn api:app --reload --port 8002
"""
import logging
import time
import traceback
from collections import defaultdict
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import API_KEY
from database import get_conn, init_db


# ── Response Models ────────────────────────────────────────────────────────────

class HotRankItem(BaseModel):
    stock_code: Optional[str]
    stock_name: Optional[str]
    rank: Optional[int]
    source: str
    score: Optional[float]
    snapshots: int

class HotRankResponse(BaseModel):
    date: str
    source: str
    total: int
    data: List[HotRankItem]


class NewsItem(BaseModel):
    id: int
    source: str
    stock_code: Optional[str]
    title: Optional[str]
    sentiment: Optional[float]
    published_at: Optional[str]
    collected_at: str

class NewsResponse(BaseModel):
    total: int
    limit: int
    offset: int
    data: List[NewsItem]


class GubaPost(BaseModel):
    post_id: Optional[str]
    title: Optional[str]
    author: Optional[str]
    sentiment: Optional[float]
    read_count: Optional[int]
    reply_count: Optional[int]
    updated_at: Optional[str]
    collected_at: str

class GubaResponse(BaseModel):
    stock_code: str
    days: int
    total: int
    limit: int
    offset: int
    data: List[GubaPost]


class CapitalFlowItem(BaseModel):
    market: str
    trade_date: str
    net_inflow: Optional[float]
    buy_amount: Optional[float]
    sell_amount: Optional[float]
    collected_at: str

class CapitalFlowResponse(BaseModel):
    total: int
    data: List[CapitalFlowItem]


class HKQuoteResponse(BaseModel):
    stock_code: str
    current: Optional[float]
    percent: Optional[float]
    volume: Optional[int]
    market_capital: Optional[float]
    high: Optional[float]
    low: Optional[float]
    open: Optional[float]
    collected_at: str


class SentimentStats(BaseModel):
    count: int
    avg_sentiment: Optional[float]
    bullish: int
    bearish: int
    neutral: int

class SentimentGubaStats(SentimentStats):
    total_reads: int

class TopPost(BaseModel):
    post_id: Optional[str]
    title: Optional[str]
    sentiment: Optional[float]
    read_count: Optional[int]
    reply_count: Optional[int]
    updated_at: Optional[str]

class SentimentResponse(BaseModel):
    stock_code: str
    days: int
    combined_sentiment: float
    news: SentimentStats
    guba: SentimentGubaStats
    top_posts: List[TopPost]


class TimelinePoint(BaseModel):
    date: str
    count: int
    avg_sentiment: Optional[float]

class GubaTimelinePoint(TimelinePoint):
    total_reads: Optional[int]

class SentimentTimelineResponse(BaseModel):
    stock_code: str
    days: int
    news_timeline: List[TimelinePoint]
    guba_timeline: List[GubaTimelinePoint]


class SourceRunItem(BaseModel):
    source: str
    status: str
    row_count: int
    error: Optional[str]
    started_at: str
    finished_at: Optional[str]

class SourcesStatusResponse(BaseModel):
    total: int
    data: List[SourceRunItem]

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(
    title="ChinaStocks Sentiment API",
    description="A股/港股舆情数据 API",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate limiting（60 次/分钟/IP）─────────────────────────────────────────────
_rate_store: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT = 60
RATE_WINDOW = 60.0


def check_rate_limit(request: Request):
    ip = request.client.host
    now = time.time()
    hits = [t for t in _rate_store[ip] if now - t < RATE_WINDOW]
    if len(hits) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded: 60 req/min")
    hits.append(now)
    _rate_store[ip] = hits


# ── API Key 认证 ───────────────────────────────────────────────────────────────
def require_api_key(request: Request):
    if not API_KEY:
        return
    key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


DEPS = [Depends(check_rate_limit), Depends(require_api_key)]


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
    return {"status": "ok", "service": "ChinaStocks Sentiment API", "version": "1.1.0"}


# ── 热股排行 ───────────────────────────────────────────────────────────────────

@app.get("/api/hot", tags=["舆情"], dependencies=DEPS, response_model=HotRankResponse)
def hot_rank(
    source: str = Query(
        "eastmoney_hot",
        description="数据源: eastmoney_hot | eastmoney_up | xueqiu_tweet | xueqiu_follow | eastmoney_hk_hot",
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
        raise HTTPException(status_code=404, detail=f"No data for source='{source}' on {date}")

    return {"date": date, "source": source, "total": len(rows), "data": rows}


# ── 新闻列表 ───────────────────────────────────────────────────────────────────

@app.get("/api/news", tags=["新闻"], dependencies=DEPS, response_model=NewsResponse)
def news_list(
    stock_code: Optional[str] = Query(None, description="股票代码，不填返回全部"),
    source: Optional[str] = Query(None, description="数据源，如 eastmoney_news / caixin_news"),
    date_from: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="截止日期 YYYY-MM-DD"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """新闻列表：支持按股票、来源、日期过滤，分页返回。"""
    logger.info("GET /api/news stock=%s source=%s from=%s to=%s", stock_code, source, date_from, date_to)

    conditions = []
    params: list = []

    if stock_code:
        conditions.append("stock_code = ?")
        params.append(stock_code)
    if source:
        conditions.append("source = ?")
        params.append(source)
    if date_from:
        conditions.append("published_at >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("published_at <= ?")
        params.append(date_to + " 23:59:59")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    total_row = query(f"SELECT COUNT(*) AS cnt FROM news {where}", tuple(params))
    total = total_row[0]["cnt"]

    params += [limit, offset]
    rows = query(
        f"""
        SELECT id, source, stock_code, title, sentiment, published_at, collected_at
        FROM news
        {where}
        ORDER BY published_at DESC
        LIMIT ? OFFSET ?
        """,
        tuple(params),
    )

    return {"total": total, "limit": limit, "offset": offset, "data": rows}


# ── 股吧帖子 ───────────────────────────────────────────────────────────────────

@app.get("/api/guba/{stock_code}", tags=["股吧"], dependencies=DEPS, response_model=GubaResponse)
def guba_posts(
    stock_code: str,
    days: int = Query(7, ge=1, le=30, description="最近 N 天"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """股吧帖子：返回指定股票最近 N 天的帖子，按阅读量排序。空页返回 200 + data:[]。"""
    logger.info("GET /api/guba/%s days=%d", stock_code, days)

    total_row = query(
        f"SELECT COUNT(*) AS cnt FROM guba_posts WHERE stock_code = ? AND collected_at >= datetime('now', '-{days} days')",
        (stock_code,),
    )
    total = total_row[0]["cnt"]

    rows = query(
        f"""
        SELECT post_id, title, author, sentiment, read_count, reply_count, updated_at, collected_at
        FROM guba_posts
        WHERE stock_code = ? AND collected_at >= datetime('now', '-{days} days')
        ORDER BY read_count DESC
        LIMIT ? OFFSET ?
        """,
        (stock_code, limit, offset),
    )

    return {"stock_code": stock_code, "days": days, "total": total, "limit": limit, "offset": offset, "data": rows}


# ── 资金流向 ───────────────────────────────────────────────────────────────────

@app.get("/api/capital-flow", tags=["资金"], dependencies=DEPS, response_model=CapitalFlowResponse)
def capital_flow(
    market: Optional[str] = Query(None, description="市场，如 HK_southbound"),
    date_from: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="截止日期 YYYY-MM-DD"),
    limit: int = Query(30, ge=1, le=100),
):
    """资金流向：南向资金等历史数据，按交易日倒序。"""
    logger.info("GET /api/capital-flow market=%s from=%s to=%s", market, date_from, date_to)

    conditions = []
    params: list = []

    if market:
        conditions.append("market = ?")
        params.append(market)
    if date_from:
        conditions.append("trade_date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("trade_date <= ?")
        params.append(date_to)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.append(limit)

    rows = query(
        f"""
        SELECT market, trade_date, net_inflow, buy_amount, sell_amount, collected_at
        FROM capital_flow
        {where}
        ORDER BY trade_date DESC
        LIMIT ?
        """,
        tuple(params),
    )

    if not rows:
        raise HTTPException(status_code=404, detail="No capital flow data found")

    return {"total": len(rows), "data": rows}


# ── 港股行情 ───────────────────────────────────────────────────────────────────

@app.get("/api/hk/quote/{stock_code}", tags=["港股"], dependencies=DEPS, response_model=HKQuoteResponse)
def hk_quote(stock_code: str):
    """港股行情：返回指定股票最新一条行情快照。"""
    logger.info("GET /api/hk/quote/%s", stock_code)

    rows = query(
        """
        SELECT stock_code, current, percent, volume, market_capital, high, low, open, collected_at
        FROM hk_quote
        WHERE stock_code = ?
        ORDER BY collected_at DESC
        LIMIT 1
        """,
        (stock_code,),
    )

    if not rows:
        raise HTTPException(status_code=404, detail=f"No quote data for '{stock_code}'")

    return rows[0]


# ── 单股情绪快照 ───────────────────────────────────────────────────────────────

@app.get("/api/sentiment/{stock_code}", tags=["舆情"], dependencies=DEPS, response_model=SentimentResponse)
def stock_sentiment(
    stock_code: str,
    days: int = Query(7, ge=1, le=30, description="统计最近 N 天"),
):
    """
    单股情绪快照：新闻情绪、股吧情绪、综合评分分开返回。
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
        raise HTTPException(status_code=404, detail=f"No sentiment data for '{stock_code}' in last {days} days")

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


# ── 情绪时间序列 ───────────────────────────────────────────────────────────────

@app.get("/api/sentiment/{stock_code}/timeline", tags=["舆情"], dependencies=DEPS, response_model=SentimentTimelineResponse)
def sentiment_timeline(
    stock_code: str,
    days: int = Query(14, ge=1, le=90, description="最近 N 天"),
):
    """情绪时间序列：按天聚合新闻和股吧情绪，返回趋势数据。"""
    logger.info("GET /api/sentiment/%s/timeline days=%d", stock_code, days)
    since = f"datetime('now', '-{days} days')"

    news_timeline = query(
        f"""
        SELECT date(collected_at) AS date,
               COUNT(*) AS count,
               ROUND(AVG(sentiment), 3) AS avg_sentiment
        FROM news
        WHERE stock_code = ? AND sentiment IS NOT NULL
          AND collected_at >= {since}
        GROUP BY date(collected_at)
        ORDER BY date ASC
        """,
        (stock_code,),
    )

    guba_timeline = query(
        f"""
        SELECT date(collected_at) AS date,
               COUNT(*) AS count,
               ROUND(AVG(sentiment), 3) AS avg_sentiment,
               SUM(read_count) AS total_reads
        FROM guba_posts
        WHERE stock_code = ? AND sentiment IS NOT NULL
          AND collected_at >= {since}
        GROUP BY date(collected_at)
        ORDER BY date ASC
        """,
        (stock_code,),
    )

    if not news_timeline and not guba_timeline:
        raise HTTPException(status_code=404, detail=f"No timeline data for '{stock_code}' in last {days} days")

    return {
        "stock_code": stock_code,
        "days": days,
        "news_timeline": news_timeline,
        "guba_timeline": guba_timeline,
    }


# ── 采集状态 ───────────────────────────────────────────────────────────────────

@app.get("/api/sources/status", tags=["监控"], dependencies=DEPS, response_model=SourcesStatusResponse)
def sources_status():
    """采集任务状态：返回每个数据源最近一次采集记录。"""
    logger.info("GET /api/sources/status")

    rows = query(
        """
        SELECT source, status, row_count, error, started_at, finished_at
        FROM source_runs
        WHERE id IN (
            SELECT MAX(id) FROM source_runs GROUP BY source
        )
        ORDER BY started_at DESC
        """
    )

    return {"total": len(rows), "data": rows}

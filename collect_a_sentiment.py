"""
A股舆情采集：东财人气榜、飙升榜、财新新闻、个股新闻、雪球热榜、互动易问答
"""
import akshare as ak
import pandas as pd
from datetime import datetime
from database import get_conn, init_db

NOW = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def collect_hot_rank():
    """东财人气榜"""
    try:
        df = ak.stock_hot_rank_em()
        df = df.rename(columns={"当前排名": "rank", "代码": "stock_code", "股票名称": "stock_name", "涨跌幅": "score"})
        df["stock_code"] = df["stock_code"].str.replace(r"^[A-Z]{2}", "", regex=True)
        df["source"] = "eastmoney_hot"
        df["collected_at"] = NOW
        rows = df[["source", "rank", "stock_code", "stock_name", "score", "collected_at"]].values.tolist()
        conn = get_conn()
        conn.executemany(
            "INSERT INTO hot_rank (source, rank, stock_code, stock_name, score, collected_at) VALUES (?,?,?,?,?,?)",
            rows,
        )
        conn.commit()
        conn.close()
        print(f"[东财人气榜] {len(rows)} 条")
    except Exception as e:
        print(f"[东财人气榜] 失败: {e}")


def collect_hot_up_rank():
    """东财飙升榜"""
    try:
        df = ak.stock_hot_up_em()
        df = df.rename(columns={"当前排名": "rank", "代码": "stock_code", "股票名称": "stock_name", "涨跌幅": "score"})
        df["stock_code"] = df["stock_code"].str.replace(r"^[A-Z]{2}", "", regex=True)
        df["source"] = "eastmoney_up"
        df["collected_at"] = NOW
        rows = df[["source", "rank", "stock_code", "stock_name", "score", "collected_at"]].values.tolist()
        conn = get_conn()
        conn.executemany(
            "INSERT INTO hot_rank (source, rank, stock_code, stock_name, score, collected_at) VALUES (?,?,?,?,?,?)",
            rows,
        )
        conn.commit()
        conn.close()
        print(f"[东财飙升榜] {len(rows)} 条")
    except Exception as e:
        print(f"[东财飙升榜] 失败: {e}")


def collect_telegraph():
    """财新新闻（stock_news_main_cx）"""
    try:
        df = ak.stock_news_main_cx()
        df["source"] = "caixin_news"
        df["stock_code"] = None
        df["sentiment"] = None
        df["collected_at"] = NOW
        col_map = {"标题": "title", "摘要": "content", "时间": "published_at"}
        df = df.rename(columns=col_map)
        for col in ["title", "content", "published_at"]:
            if col not in df.columns:
                df[col] = None
        rows = df[["source", "stock_code", "title", "content", "sentiment", "published_at", "collected_at"]].values.tolist()
        conn = get_conn()
        conn.executemany(
            "INSERT INTO news (source, stock_code, title, content, sentiment, published_at, collected_at) VALUES (?,?,?,?,?,?,?)",
            rows,
        )
        conn.commit()
        conn.close()
        print(f"[财新新闻] {len(rows)} 条")
    except Exception as e:
        print(f"[财新新闻] 失败: {e}")


def collect_stock_news(stock_code: str):
    """个股新闻（东财）"""
    try:
        df = ak.stock_news_em(symbol=stock_code)
        df["source"] = "eastmoney_news"
        df["stock_code"] = stock_code
        df["sentiment"] = None
        df["collected_at"] = NOW
        col_map = {"新闻标题": "title", "新闻内容": "content", "发布时间": "published_at"}
        df = df.rename(columns=col_map)
        rows = df[["source", "stock_code", "title", "content", "sentiment", "published_at", "collected_at"]].values.tolist()
        conn = get_conn()
        conn.executemany(
            "INSERT INTO news (source, stock_code, title, content, sentiment, published_at, collected_at) VALUES (?,?,?,?,?,?,?)",
            rows,
        )
        conn.commit()
        conn.close()
        print(f"[个股新闻 {stock_code}] {len(rows)} 条")
    except Exception as e:
        print(f"[个股新闻 {stock_code}] 失败: {e}")


def collect_xueqiu_hot():
    """雪球热帖榜（帖子数）"""
    try:
        df = ak.stock_hot_tweet_xq()
        df = df.rename(columns={"股票代码": "stock_code", "股票简称": "stock_name", "关注": "score"})
        df["stock_code"] = df["stock_code"].str.replace(r"^[A-Z]{2}", "", regex=True)
        df["rank"] = range(1, len(df) + 1)
        df["source"] = "xueqiu_tweet"
        df["collected_at"] = NOW
        rows = df[["source", "rank", "stock_code", "stock_name", "score", "collected_at"]].values.tolist()
        conn = get_conn()
        conn.executemany(
            "INSERT INTO hot_rank (source, rank, stock_code, stock_name, score, collected_at) VALUES (?,?,?,?,?,?)",
            rows,
        )
        conn.commit()
        conn.close()
        print(f"[雪球热帖榜] {len(rows)} 条")
    except Exception as e:
        print(f"[雪球热帖榜] 失败: {e}")


def collect_xueqiu_follow():
    """雪球关注榜（关注人数）"""
    try:
        df = ak.stock_hot_follow_xq()
        df = df.rename(columns={"股票代码": "stock_code", "股票简称": "stock_name", "关注": "score"})
        df["stock_code"] = df["stock_code"].str.replace(r"^[A-Z]{2}", "", regex=True)
        df["rank"] = range(1, len(df) + 1)
        df["source"] = "xueqiu_follow"
        df["collected_at"] = NOW
        rows = df[["source", "rank", "stock_code", "stock_name", "score", "collected_at"]].values.tolist()
        conn = get_conn()
        conn.executemany(
            "INSERT INTO hot_rank (source, rank, stock_code, stock_name, score, collected_at) VALUES (?,?,?,?,?,?)",
            rows,
        )
        conn.commit()
        conn.close()
        print(f"[雪球关注榜] {len(rows)} 条")
    except Exception as e:
        print(f"[雪球关注榜] 失败: {e}")


def collect_investor_qa():
    """互动易问答（巨潮）"""
    try:
        df = ak.stock_irm_cninfo()
        df["source"] = "cninfo_irm"
        df["collected_at"] = NOW
        col_map = {
            "股票代码": "stock_code",
            "问题": "title",
            "回答内容": "content",
            "提问时间": "published_at",
        }
        df = df.rename(columns=col_map)
        df["sentiment"] = None
        for col in ["title", "content", "published_at"]:
            if col not in df.columns:
                df[col] = None
        rows = df[["source", "stock_code", "title", "content", "sentiment", "published_at", "collected_at"]].values.tolist()
        conn = get_conn()
        conn.executemany(
            "INSERT INTO news (source, stock_code, title, content, sentiment, published_at, collected_at) VALUES (?,?,?,?,?,?,?)",
            rows,
        )
        conn.commit()
        conn.close()
        print(f"[互动易问答] {len(rows)} 条")
    except Exception as e:
        print(f"[互动易问答] 失败: {e}")


if __name__ == "__main__":
    init_db()
    from config import A_WATCH_LIST
    collect_hot_rank()
    collect_hot_up_rank()
    collect_xueqiu_hot()
    collect_xueqiu_follow()
    collect_telegraph()
    collect_investor_qa()
    for code in A_WATCH_LIST:
        collect_stock_news(code)

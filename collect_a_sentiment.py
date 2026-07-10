"""
A股舆情采集：东财人气榜、飙升榜、财新新闻、个股新闻、雪球热榜、互动易问答
"""
import akshare as ak
from datetime import datetime
from database import init_db
from repository import insert_hot_rank, insert_news

NOW = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def collect_hot_rank():
    """东财人气榜"""
    try:
        df = ak.stock_hot_rank_em()
        df = df.rename(columns={"当前排名": "rank", "代码": "stock_code", "股票名称": "stock_name", "涨跌幅": "score"})
        df["stock_code"] = df["stock_code"].str.replace(r"^[A-Z]{2}", "", regex=True)
        rows = [(r"eastmoney_hot", row["rank"], row["stock_code"], row["stock_name"], row["score"], NOW)
                for _, row in df.iterrows()]
        n = insert_hot_rank(rows)
        print(f"[东财人气榜] {n} 条")
    except Exception as e:
        print(f"[东财人气榜] 失败: {e}")


def collect_hot_up_rank():
    """东财飙升榜"""
    try:
        df = ak.stock_hot_up_em()
        df = df.rename(columns={"当前排名": "rank", "代码": "stock_code", "股票名称": "stock_name", "涨跌幅": "score"})
        df["stock_code"] = df["stock_code"].str.replace(r"^[A-Z]{2}", "", regex=True)
        rows = [("eastmoney_up", row["rank"], row["stock_code"], row["stock_name"], row["score"], NOW)
                for _, row in df.iterrows()]
        n = insert_hot_rank(rows)
        print(f"[东财飙升榜] {n} 条")
    except Exception as e:
        print(f"[东财飙升榜] 失败: {e}")


def collect_telegraph():
    """财新新闻"""
    try:
        df = ak.stock_news_main_cx()
        df = df.rename(columns={"标题": "title", "摘要": "content", "时间": "published_at"})
        for col in ["title", "content", "published_at"]:
            if col not in df.columns:
                df[col] = None
        rows = [("caixin_news", None, row.get("title"), row.get("content"), None, row.get("published_at"), NOW)
                for _, row in df.iterrows()]
        n = insert_news(rows)
        print(f"[财新新闻] {n} 条")
    except Exception as e:
        print(f"[财新新闻] 失败: {e}")


def collect_stock_news(stock_code: str):
    """个股新闻（东财）"""
    try:
        df = ak.stock_news_em(symbol=stock_code)
        df = df.rename(columns={"新闻标题": "title", "新闻内容": "content", "发布时间": "published_at"})
        rows = [("eastmoney_news", stock_code, row.get("title"), row.get("content"), None, row.get("published_at"), NOW)
                for _, row in df.iterrows()]
        n = insert_news(rows)
        print(f"[个股新闻 {stock_code}] {n} 条")
    except Exception as e:
        print(f"[个股新闻 {stock_code}] 失败: {e}")


def collect_xueqiu_hot():
    """雪球热帖榜"""
    try:
        df = ak.stock_hot_tweet_xq()
        df = df.rename(columns={"股票代码": "stock_code", "股票简称": "stock_name", "关注": "score"})
        df["stock_code"] = df["stock_code"].str.replace(r"^[A-Z]{2}", "", regex=True)
        rows = [("xueqiu_tweet", i + 1, row["stock_code"], row["stock_name"], row["score"], NOW)
                for i, (_, row) in enumerate(df.iterrows())]
        n = insert_hot_rank(rows)
        print(f"[雪球热帖榜] {n} 条")
    except Exception as e:
        print(f"[雪球热帖榜] 失败: {e}")


def collect_xueqiu_follow():
    """雪球关注榜"""
    try:
        df = ak.stock_hot_follow_xq()
        df = df.rename(columns={"股票代码": "stock_code", "股票简称": "stock_name", "关注": "score"})
        df["stock_code"] = df["stock_code"].str.replace(r"^[A-Z]{2}", "", regex=True)
        rows = [("xueqiu_follow", i + 1, row["stock_code"], row["stock_name"], row["score"], NOW)
                for i, (_, row) in enumerate(df.iterrows())]
        n = insert_hot_rank(rows)
        print(f"[雪球关注榜] {n} 条")
    except Exception as e:
        print(f"[雪球关注榜] 失败: {e}")


def collect_investor_qa():
    """互动易问答"""
    try:
        df = ak.stock_irm_cninfo()
        df = df.rename(columns={"股票代码": "stock_code", "问题": "title", "回答内容": "content", "提问时间": "published_at"})
        for col in ["title", "content", "published_at"]:
            if col not in df.columns:
                df[col] = None
        rows = [("cninfo_irm", row.get("stock_code"), row.get("title"), row.get("content"), None, row.get("published_at"), NOW)
                for _, row in df.iterrows()]
        n = insert_news(rows)
        print(f"[互动易问答] {n} 条")
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

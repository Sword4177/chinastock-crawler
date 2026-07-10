"""
港股舆情采集：南向资金流向、东财港股人气榜、雪球港股实时行情
"""
import akshare as ak
import requests
from datetime import datetime
from config import HK_WATCH_LIST, XUEQIU_TOKEN
from database import init_db
from exceptions import CollectorSkipped
from repository import insert_hot_rank, insert_capital_flow, upsert_hk_quote

NOW = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def collect_southbound_flow() -> int:
    """南向资金流向"""
    df = ak.stock_hsgt_fund_flow_summary_em()
    df = df[df["资金方向"] == "南向"].copy()
    df = df.rename(columns={"交易日": "trade_date", "资金净流入": "net_inflow", "成交净买额": "buy_amount"})
    rows = [("HK_southbound", row["trade_date"], row["net_inflow"], row["buy_amount"], None, NOW)
            for _, row in df.iterrows()]
    n = insert_capital_flow(rows)
    print(f"[南向资金] {n} 条")
    return n


def collect_hk_hot_rank() -> int:
    """东财港股人气榜"""
    df = ak.stock_hk_hot_rank_em()
    df = df.rename(columns={"当前排名": "rank", "代码": "stock_code", "股票名称": "stock_name", "涨跌幅": "score"})
    rows = [("eastmoney_hk_hot", row["rank"], row["stock_code"], row["stock_name"], row["score"], NOW)
            for _, row in df.iterrows()]
    n = insert_hot_rank(rows)
    print(f"[东财港股人气榜] {n} 条")
    return n


def collect_xueqiu_hk_quote() -> int:
    """雪球港股实时行情"""
    if not XUEQIU_TOKEN:
        raise CollectorSkipped("XUEQIU_TOKEN 未设置")
    url = "https://stock.xueqiu.com/v5/stock/realtime/quotec.json"
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://xueqiu.com"}
    cookies = {"xq_a_token": XUEQIU_TOKEN}
    total = 0
    for code in HK_WATCH_LIST:
        r = requests.get(url, params={"symbol": code}, headers=headers, cookies=cookies, timeout=10)
        data = r.json().get("data", [])
        if not data:
            continue
        total += upsert_hk_quote(code, data[0], NOW)
    print(f"[雪球港股行情] {total} 支写入")
    return total


if __name__ == "__main__":
    init_db()
    collect_southbound_flow()
    collect_hk_hot_rank()
    collect_xueqiu_hk_quote()

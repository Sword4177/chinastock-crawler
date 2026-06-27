"""
港股舆情采集：南向资金流向、东财港股人气榜
"""
import akshare as ak
from datetime import datetime
from database import get_conn, init_db

NOW = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def collect_southbound_flow():
    """南向资金流向（沪深港通汇总，过滤南向）"""
    try:
        df = ak.stock_hsgt_fund_flow_summary_em()
        df = df[df["资金方向"] == "南向"].copy()
        df = df.rename(columns={"交易日": "trade_date", "资金净流入": "net_inflow", "成交净买额": "buy_amount"})
        df["market"] = "HK_southbound"
        df["sell_amount"] = None
        df["collected_at"] = NOW
        rows = df[["market", "trade_date", "net_inflow", "buy_amount", "sell_amount", "collected_at"]].values.tolist()
        conn = get_conn()
        conn.executemany(
            "INSERT OR IGNORE INTO capital_flow (market, trade_date, net_inflow, buy_amount, sell_amount, collected_at) VALUES (?,?,?,?,?,?)",
            rows,
        )
        conn.commit()
        conn.close()
        print(f"[南向资金] {len(rows)} 条")
    except Exception as e:
        print(f"[南向资金] 失败: {e}")


def collect_hk_hot_rank():
    """东财港股人气榜"""
    try:
        df = ak.stock_hk_hot_rank_em()
        df = df.rename(columns={"当前排名": "rank", "代码": "stock_code", "股票名称": "stock_name", "涨跌幅": "score"})
        df["source"] = "eastmoney_hk_hot"
        df["collected_at"] = NOW
        rows = df[["source", "rank", "stock_code", "stock_name", "score", "collected_at"]].values.tolist()
        conn = get_conn()
        conn.executemany(
            "INSERT INTO hot_rank (source, rank, stock_code, stock_name, score, collected_at) VALUES (?,?,?,?,?,?)",
            rows,
        )
        conn.commit()
        conn.close()
        print(f"[东财港股人气榜] {len(rows)} 条")
    except Exception as e:
        print(f"[东财港股人气榜] 失败: {e}")


if __name__ == "__main__":
    init_db()
    collect_southbound_flow()
    collect_hk_hot_rank()

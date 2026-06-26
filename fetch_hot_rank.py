"""
fetch_hot_rank.py — 抓取东方财富热股榜数据，保存为 CSV
用法：python fetch_hot_rank.py
"""
import akshare as ak
import pandas as pd
from datetime import datetime

def fetch_and_save():
    print("正在抓取东方财富热股榜...")
    df = ak.stock_hot_rank_em()

    # 加上抓取时间
    df["collected_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 保存为 CSV
    filename = f"hot_rank_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(filename, index=False, encoding="utf-8-sig")

    print(f"抓取完成，共 {len(df)} 条数据")
    print(f"已保存至：{filename}")
    print(df.head(10))
    return df

if __name__ == "__main__":
    fetch_and_save()

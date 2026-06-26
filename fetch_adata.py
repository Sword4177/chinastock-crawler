"""
fetch_adata.py — 用 AData 抓取 A 股热度、龙虎榜、资金流向数据
"""
import adata
import pandas as pd
from datetime import datetime

today = datetime.now().strftime("%Y-%m-%d")

# 1. 全部股票代码列表
print("=== 股票列表 ===")
df_codes = adata.stock.info.all_code()
print(df_codes.head(5))
df_codes.to_csv(f"stock_codes_{today}.csv", index=False, encoding="utf-8-sig")

# 2. 市场实时行情（含涨跌幅）
print("\n=== 市场实时行情 ===")
df_market = adata.stock.market.list_market_current()
print(df_market.head(5))
df_market.to_csv(f"market_current_{today}.csv", index=False, encoding="utf-8-sig")

# 3. 资金流向
print("\n=== 资金流向 ===")
df_fund = adata.stock.market.get_capital_flow(stock_code="000001")
print(df_fund.head(5))
df_fund.to_csv(f"capital_flow_{today}.csv", index=False, encoding="utf-8-sig")

print("\n完成，CSV 已保存")

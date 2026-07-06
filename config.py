A_WATCH_LIST = [
    "000001",  # 平安银行
    "000002",  # 万科A
    "600519",  # 贵州茅台
    "600036",  # 招商银行
    "300750",  # 宁德时代
]

HK_WATCH_LIST = [
    "00700",   # 腾讯
    "09988",   # 阿里巴巴
    "03690",   # 美团
    "01810",   # 小米
    "02318",   # 中国平安
]

DB_PATH = "chinastocks.db"

# 每天采集4次，间隔6小时
COLLECT_INTERVAL_SEC = 6 * 60 * 60

import os
ALPHA_VANTAGE_KEY = os.environ.get("ALPHA_VANTAGE_KEY", "")
XUEQIU_TOKEN = os.environ.get("XUEQIU_TOKEN", "")
LARK_WEBHOOK = os.environ.get("LARK_WEBHOOK", "")
API_KEY = os.environ.get("API_KEY", "")  # 空字符串=本地开发开放访问

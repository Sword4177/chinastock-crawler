# ChinaStocks Crawler — A股/港股舆情采集

A 股 + 港股多源舆情数据自动采集、入库、API 对外输出。  
数据来源：东方财富热股榜、股吧、雪球、财新、互动易、Alpha Vantage。

---

## 快速开始

```bash
git clone https://github.com/Sword4177/chinastock-crawler.git
cd chinastock-crawler
pip install -r requirements.txt
python pipeline.py          # 跑一次完整采集
```

---

## 环境变量

| 变量名 | 说明 | 必填 |
|---|---|---|
| `ALPHA_VANTAGE_KEY` | Alpha Vantage API Key（全球宏观新闻） | 否 |
| `XUEQIU_TOKEN` | 雪球 JWT Token（港股实时行情） | 否 |
| `LARK_WEBHOOK` | 飞书自定义 Bot Webhook URL（采集结果通知） | 否 |

本地开发直接 `export` 或创建 `.env` 文件（已在 `.gitignore` 中排除）。  
GitHub Actions 在仓库 Settings → Secrets 中配置。

---

## 项目结构

```
pipeline.py          # 完整采集入口（一次性/GitHub Actions 用）
scheduler.py         # 持续运行调度器（本地/服务器用，每6小时一次）
api.py               # FastAPI 对外接口
database.py          # SQLite 初始化 & 连接
config.py            # 全局配置（Watch List、DB路径、采集间隔）
collect_a_sentiment.py   # A股：热股榜、雪球、财新、互动易
collect_hk_sentiment.py  # 港股：南向资金、港股热榜、雪球港股行情
collect_global_sentiment.py  # 全球：Alpha Vantage 宏观新闻
crawl_guba.py        # 东方财富股吧爬虫（帖子列表 + 正文 + 情感打分）
```

---

## 定时采集（scheduler.py）

本地或服务器**持续运行**模式，每 6 小时采集一次：

```bash
python scheduler.py
```

日志同时输出控制台和 `scheduler.log`。  
连续失败 3 次会打 `CRITICAL` 级别日志，方便定位问题。

**GitHub Actions 自动调度**（无需手动运行）：每个工作日触发 4 次，时间对齐 A 股交易时段：

| 触发时间（北京） | 场景 |
|---|---|
| 09:00 | 开盘前 |
| 11:30 | 上午收盘前 |
| 13:30 | 下午开盘 |
| 15:30 | 收盘后 |

---

## API 服务（api.py）

```bash
uvicorn api:app --reload --port 8002
```

交互式文档：http://localhost:8002/docs

### GET /api/hot — 热股排行

按指定数据源返回当日热股排名。

**参数**

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `source` | string | `eastmoney_hot` | `eastmoney_hot` / `eastmoney_up` / `xueqiu_tweet` / `xueqiu_follow` |
| `date` | string | 今天 | 格式 `YYYY-MM-DD` |
| `limit` | int | 20 | 最多返回条数（1-100） |

**示例请求**

```
GET /api/hot?source=eastmoney_hot&date=2026-06-27&limit=3
```

**真实返回**

```json
{
  "date": "2026-06-27",
  "source": "eastmoney_hot",
  "total": 3,
  "data": [
    {
      "stock_code": "000725",
      "stock_name": "京东方A",
      "rank": 1,
      "source": "eastmoney_hot",
      "score": 3.59,
      "snapshots": 6
    },
    {
      "stock_code": "002407",
      "stock_name": "多氟多",
      "rank": 2,
      "source": "eastmoney_hot",
      "score": -5.21,
      "snapshots": 6
    },
    {
      "stock_code": "600206",
      "stock_name": "有研新材",
      "rank": 3,
      "source": "eastmoney_hot",
      "score": 8.19,
      "snapshots": 6
    }
  ]
}
```

---

### GET /api/sentiment/{stock_code} — 单股情绪快照

综合新闻和股吧帖子，返回情感分、多空比例、热帖 Top 3。  
`combined_sentiment > 0` 偏多，`< 0` 偏空，`= 0` 中性，范围 `-1.0 ~ 1.0`。

**参数**

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `days` | int | 7 | 统计最近 N 天（1-30） |

**示例请求**

```
GET /api/sentiment/600519?days=30
```

**真实返回**

```json
{
  "stock_code": "600519",
  "days": 30,
  "combined_sentiment": 0.223,
  "news": {
    "count": 30,
    "avg_sentiment": 0.2,
    "bullish": 6,
    "bearish": 0,
    "neutral": 24
  },
  "guba": {
    "count": 5,
    "avg_sentiment": 0.36,
    "bullish": 4,
    "bearish": 0,
    "neutral": 1,
    "total_reads": 473467
  },
  "top_posts": [
    {
      "post_id": "1736164102",
      "title": "批量「对子顶」？高价科技股再出「玄学」",
      "sentiment": 0.0,
      "read_count": 213461,
      "reply_count": 777,
      "updated_at": "07-01 06:17"
    },
    {
      "post_id": "1732778093",
      "title": "坐不住了？坚守茅台的前千亿基金经理疑似调仓 10天收复近一年跌幅",
      "sentiment": 0.2,
      "read_count": 190962,
      "reply_count": 581,
      "updated_at": "06-26 12:27"
    },
    {
      "post_id": "1729460010",
      "title": "350亿分红 贵州茅台本周发放",
      "sentiment": 1.0,
      "read_count": 25364,
      "reply_count": 112,
      "updated_at": "06-22 05:29"
    }
  ]
}
```

---

## 数据库表

| 表名 | 说明 |
|---|---|
| `hot_rank` | 各来源热股排行快照 |
| `news` | 个股新闻 + 情感打分 |
| `guba_posts` | 股吧帖子 + 正文 + 情感打分 |
| `hk_quote` | 港股实时行情快照 |
| `capital_flow` | 南向资金流 |

---

## 技术栈

- Python 3.11+
- AkShare 1.18.64（A股/港股数据）
- BeautifulSoup4（股吧爬虫）
- FastAPI + Uvicorn（API 服务）
- SQLite（本地存储）
- GitHub Actions（自动调度）
- 飞书 Bot（采集结果通知）

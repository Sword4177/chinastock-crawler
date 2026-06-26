# ChinaStocks Crawler — A股热股数据采集

## 项目简介

通过 AkShare 抓取东方财富热股榜数据，为 ARTI 量化策略提供 A 股热度信号。

## 数据来源

- **东方财富热股榜**：实时反映 A 股市场热度最高的股票

## 字段说明

| 字段 | 说明 |
|------|------|
| 代码 | 股票代码 |
| 名称 | 股票名称 |
| 最新价 | 当前股价 |
| 涨跌幅 | 当日涨跌幅（%）|
| 换手率 | 当日换手率（%）|
| 资金流入 | 当日净流入资金 |
| collected_at | 数据采集时间 |

## 调研结论（2026-06-25）

- AkShare 热股榜接口（`stock_hot_rank_em`）可用，返回行情数据
- AkShare 股吧帖子接口已移除，无法获取帖子文字内容
- 东方财富股吧直接接口已关闭（返回 404）
- **结论**：A 股目前无免费稳定的股吧帖子 API，行情热度数据可用

## 快速开始

```bash
pip install -r requirements.txt
python fetch_hot_rank.py
```

## 技术栈

- Python 3.11+
- AkShare
- pandas

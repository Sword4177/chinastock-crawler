"""
定时调度入口 — 本地/服务器持续运行模式
每天4次（间隔6小时），对应 A股交易时段
GitHub Actions 模式直接跑 pipeline.py 即可
"""
import logging
import time
import traceback
from datetime import datetime

from config import COLLECT_INTERVAL_SEC
from pipeline import run as run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("scheduler.log", encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)

_MAX_CONSECUTIVE_FAILURES = 3


def run_loop() -> None:
    logger.info("调度器启动，采集间隔 %d 秒（%.1f 小时）", COLLECT_INTERVAL_SEC, COLLECT_INTERVAL_SEC / 3600)
    run_count = 0
    consecutive_failures = 0

    while True:
        run_count += 1
        start = datetime.now()
        logger.info("=== 第 %d 次采集开始 %s ===", run_count, start.strftime("%Y-%m-%d %H:%M:%S"))

        try:
            run_pipeline()
            elapsed = int((datetime.now() - start).total_seconds())
            logger.info("=== 第 %d 次采集完成，耗时 %ds ===", run_count, elapsed)
            consecutive_failures = 0
        except Exception as e:
            consecutive_failures += 1
            logger.error(
                "=== 第 %d 次采集失败（连续第 %d 次）: %s ===\n%s",
                run_count, consecutive_failures, e, traceback.format_exc(),
            )
            if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                logger.critical(
                    "连续失败 %d 次，请检查网络/数据库/API 配置。调度器继续运行但需人工介入。",
                    consecutive_failures,
                )

        logger.info("下次采集将在 %.1f 小时后（%s）",
                    COLLECT_INTERVAL_SEC / 3600,
                    datetime.fromtimestamp(time.time() + COLLECT_INTERVAL_SEC).strftime("%H:%M:%S"))
        time.sleep(COLLECT_INTERVAL_SEC)


if __name__ == "__main__":
    run_loop()

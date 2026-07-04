"""
定时调度入口 — 本地/服务器持续运行模式
每天4次（间隔6小时），对应 A股交易时段
GitHub Actions 模式直接跑 pipeline.py 即可
"""
import logging
import time

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


def run_loop() -> None:
    logger.info("调度器启动，采集间隔 %d 秒（%.1f 小时）", COLLECT_INTERVAL_SEC, COLLECT_INTERVAL_SEC / 3600)
    while True:
        try:
            run_pipeline()
        except Exception as e:
            logger.error("Pipeline 异常: %s", e)
        logger.info("下次采集将在 %.1f 小时后", COLLECT_INTERVAL_SEC / 3600)
        time.sleep(COLLECT_INTERVAL_SEC)


if __name__ == "__main__":
    run_loop()

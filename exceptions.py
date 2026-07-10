class CollectorSkipped(Exception):
    """采集器主动跳过，通常因配置缺失（如 token/key 未设置）。"""

"""轻量日志配置；Phase3 可替换为 structlog 或 loguru。"""

from __future__ import annotations

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=level.upper(), format=fmt, stream=sys.stdout, force=True)

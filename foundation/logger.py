"""统一日志。所有层经此记录，便于审计（尤其是证据与权重来源）。"""

import logging
import sys
from logging.handlers import RotatingFileHandler

from foundation.config import AppConfig

_LOGGER_NAME = "garden-spirit"
_configured = False


def setup_logging(config: AppConfig | None = None) -> logging.Logger:
    """初始化根 logger。幂等。"""
    global _configured

    logger = logging.getLogger(_LOGGER_NAME)
    if _configured:
        return logger

    level = getattr(logging, (config or AppConfig()).log_level.upper(), logging.INFO)
    logger.setLevel(level)

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logger.addHandler(console)

    # Rotating file handler（便于审计）
    try:
        file_handler = RotatingFileHandler(
            "garden-spirit.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s")
        )
        logger.addHandler(file_handler)
    except OSError:
        pass  # 文件日志失败不阻塞

    _configured = True
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """获取带子命名的 logger。"""
    return logging.getLogger(f"{_LOGGER_NAME}.{name}" if name else _LOGGER_NAME)

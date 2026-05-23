from __future__ import annotations

import logging
from functools import lru_cache

from utils.config import get_config


@lru_cache(maxsize=1)
def get_logger(name: str = 'cost_forge') -> logging.Logger:
    config = get_config()

    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    level = getattr(logging, config.log_level, logging.INFO)
    logger.setLevel(level)

    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s %(name)s - %(message)s'
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.propagate = False

    return logger

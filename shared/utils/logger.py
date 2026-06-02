from __future__ import annotations

import logging
import os

_CONFIGURED = False


def _configure_root() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    level = os.environ.get("GOPIPE_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    _configure_root()
    return logging.getLogger(name)

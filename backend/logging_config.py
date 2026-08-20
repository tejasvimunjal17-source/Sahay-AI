"""
backend/logging_config.py
--------------------------
Centralized logging setup, adapted from LearnMate's backend/logger_setup.py
pattern. PHASE 1: used only for basic app startup/navigation logging —
nothing sensitive is logged (no message content, no credentials, per the
master spec's logging rules, which nothing in this codebase violates yet
since no AI/DB calls exist).
"""

from __future__ import annotations

import logging


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

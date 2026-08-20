"""utils/validators.py — small, genuinely Phase-1-usable input validators
(no AI/DB dependency, safe to implement now)."""

from __future__ import annotations


def is_non_empty(text: str) -> bool:
    return bool(text and text.strip())


def clamp_text_length(text: str, max_len: int = 2000) -> str:
    return text if len(text) <= max_len else text[:max_len]

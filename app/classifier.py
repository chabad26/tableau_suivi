"""Expose les fonctions de classification du script existant."""

from mailrecever import (
    decode_text as decode_text,
    detect_status as detect_status,
    normalize as normalize,
    parse_date as parse_date,
    score_message as score_message,
)

__all__ = [
    "decode_text",
    "detect_status",
    "normalize",
    "parse_date",
    "score_message",
]

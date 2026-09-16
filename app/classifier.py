"""Expose les fonctions de classification du script existant."""

from mailrecever import decode_text as decode_text
from mailrecever import detect_status as detect_status
from mailrecever import normalize as normalize
from mailrecever import parse_date as parse_date
from mailrecever import score_message as score_message

__all__ = ["decode_text", "detect_status", "normalize", "parse_date", "score_message"]

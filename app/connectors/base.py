"""Description minimale d'un connecteur API enregistré."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from app.models import DetectedEmail


@dataclass(frozen=True)
class ConnectorSpec:
    name: str
    configured: bool
    scan: Callable[[datetime], list[DetectedEmail]]

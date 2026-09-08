from dataclasses import dataclass
from datetime import datetime


@dataclass
class DetectedEmail:
    mailbox: str
    date: datetime
    sender: str
    subject: str
    message_id: str
    score: int
    status: str
    reasons: list[str]
    body: str = ""


@dataclass
class Application:
    id: int | None
    company: str
    job_title: str
    source: str
    first_seen: datetime
    last_update: datetime
    current_status: str
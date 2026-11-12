"""Indicateurs agrégés : aucune donnée détaillée de candidature n'est sélectionnée."""

from datetime import datetime, timezone
from typing import TypedDict

from app.application_history import effective_status_sql
from app.database import get_connection
from app.owned_applications import require_user_id
from app.statuses import STATUS_ORDER

# La vue campus est une autorisation distincte des modules personnels.
CAMPUS_DASHBOARD_ROLES = frozenset({"admin"})


class MonthStatistics(TypedDict):
    month: str
    new: int
    changes: int
    counts: dict[str, int]


class LearnerStatistics(TypedDict):
    id: int
    email: str
    promotion: str
    active: bool
    total: int
    counts: dict[str, int]


def dashboard_statistics(
    actor_id: int,
    *,
    scope: str = "personal",
    promotion: str = "",
    months: int = 6,
    now: datetime | None = None,
) -> dict:
    actor_id = require_user_id(actor_id)
    if (
        scope not in {"personal", "campus"}
        or type(months) is not int
        or months not in {6, 12}
    ):
        raise ValueError("Filtre de dashboard invalide.")
    if promotion and promotion != "unassigned":
        try:
            promotion_id = int(promotion)
        except ValueError:
            raise ValueError("Promotion invalide.") from None
        if not 0 < promotion_id < 2**63:
            raise ValueError("Promotion invalide.")
    else:
        promotion_id = None
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("La date de référence doit inclure un fuseau horaire.")
    now = now.astimezone(timezone.utc)
    month_index = now.year * 12 + now.month - 1
    timeline: list[MonthStatistics] = []
    for index in range(month_index - months + 1, month_index + 1):
        year, month = divmod(index, 12)
        timeline.append(
            {
                "month": f"{year:04}-{month + 1:02}",
                "new": 0,
                "changes": 0,
                "counts": {status: 0 for status in STATUS_ORDER},
            }
        )
    since = str(timeline[0]["month"]) + "-01T00:00:00+00:00"
    by_month = {row["month"]: row for row in timeline}
    with get_connection() as connection:
        connection.execute("BEGIN")
        actor = connection.execute(
            "SELECT role,active,promotion_id FROM users WHERE id=?", (actor_id,)
        ).fetchone()
        if actor is None or not actor["active"]:
            raise PermissionError("Compte inactif ou inexistant.")
        if actor["role"] not in {"admin", "student"}:
            raise PermissionError(
                "Dashboard réservé aux apprenants et à l'équipe pédagogique."
            )
        can_view_campus = actor["role"] in CAMPUS_DASHBOARD_ROLES
        if scope == "campus" and not can_view_campus:
            raise PermissionError("Vue campus non autorisée.")
        if scope == "personal":
            if promotion and (
                (promotion == "unassigned" and actor["promotion_id"] is not None)
                or (promotion != "unassigned" and promotion_id != actor["promotion_id"])
            ):
                raise PermissionError("Promotion hors du périmètre personnel.")
            where, params = "u.id=?", [actor_id]
            promotions = connection.execute(
                "SELECT id,name FROM promotions WHERE id=?", (actor["promotion_id"],)
            ).fetchall()
        else:
            # La vue pédagogique porte sur les apprenants. Les candidatures
            # personnelles des membres de l'équipe restent dans leur propre vue.
            where, params = "u.role='student'", []
            promotions = connection.execute(
                "SELECT id,name FROM promotions ORDER BY name COLLATE NOCASE,id"
            ).fetchall()
        if promotion == "unassigned":
            where += " AND u.promotion_id IS NULL"
        elif promotion_id is not None:
            if (
                connection.execute(
                    "SELECT 1 FROM promotions WHERE id=?", (promotion_id,)
                ).fetchone()
                is None
            ):
                raise ValueError("Promotion introuvable.")
            where += " AND u.promotion_id=?"
            params.append(promotion_id)
        counts = {status: 0 for status in STATUS_ORDER}
        for row in connection.execute(
            f"SELECT {effective_status_sql('a')} AS status,COUNT(*) AS total FROM applications a JOIN users u ON u.id=a.user_id WHERE {where} GROUP BY status",
            params,
        ).fetchall():
            counts[row["status"]] = int(row["total"])
        accounts = connection.execute(
            f"SELECT COUNT(*) FROM users u WHERE {where}", params
        ).fetchone()[0]
        learners: dict[int, LearnerStatistics] = {}
        if scope == "campus":
            # Une seule requête pour tous les apprenants, y compris ceux sans
            # candidature. Les vues personnelles ne sélectionnent pas ces identités.
            for row in connection.execute(
                f"SELECT u.id,u.email,u.active,p.name AS promotion,{effective_status_sql('a')} AS status,COUNT(a.id) AS total FROM users u LEFT JOIN promotions p ON p.id=u.promotion_id LEFT JOIN applications a ON a.user_id=u.id WHERE {where} GROUP BY u.id,status ORDER BY u.email COLLATE NOCASE,u.id",
                params,
            ).fetchall():
                identifier = int(row["id"])
                if identifier not in learners:
                    learners[identifier] = {
                        "id": identifier,
                        "email": str(row["email"]),
                        "promotion": str(row["promotion"] or ""),
                        "active": bool(row["active"]),
                        "total": 0,
                        "counts": {status: 0 for status in STATUS_ORDER},
                    }
                total = int(row["total"])
                learners[identifier]["counts"][row["status"]] = total
                learners[identifier]["total"] += total
        for row in connection.execute(
            f"SELECT strftime('%Y-%m',a.first_seen) AS month,COUNT(*) AS total FROM applications a JOIN users u ON u.id=a.user_id WHERE {where} AND julianday(a.first_seen)>=julianday(?) AND julianday(a.first_seen)<=julianday(?) GROUP BY month",
            [*params, since, now.isoformat()],
        ).fetchall():
            if row["month"] in by_month:
                by_month[row["month"]]["new"] = int(row["total"])
        for row in connection.execute(
            f"SELECT strftime('%Y-%m',h.recorded_at) AS month,h.status,COUNT(*) AS total FROM application_status_history h JOIN applications a ON a.id=h.application_id AND a.user_id=h.user_id JOIN users u ON u.id=a.user_id WHERE {where} AND h.event_kind='change' AND julianday(h.recorded_at)>=julianday(?) AND julianday(h.recorded_at)<=julianday(?) GROUP BY month,h.status",
            [*params, since, now.isoformat()],
        ).fetchall():
            if row["month"] in by_month and row["status"] in counts:
                by_month[row["month"]]["counts"][row["status"]] = int(row["total"])
                by_month[row["month"]]["changes"] += int(row["total"])
        started_at = connection.execute(
            "SELECT value FROM application_history_metadata WHERE key='started_at'"
        ).fetchone()[0]
        return {
            "scope": scope,
            "can_view_campus": can_view_campus,
            "can_manage_promotions": actor["role"] == "admin",
            "promotions": [dict(row) for row in promotions],
            "allow_unassigned": scope == "campus" or actor["promotion_id"] is None,
            "promotion": promotion,
            "months": months,
            "counts": counts,
            "total": sum(counts.values()),
            "accounts": int(accounts),
            "learners": list(learners.values()),
            "timeline": timeline,
            "history_started_at": str(started_at),
        }

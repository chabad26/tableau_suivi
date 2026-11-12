"""Journal des statuts affichés, sans recopier le contenu des candidatures."""

import sqlite3

from app.statuses import STATUS_ORDER


def effective_status_sql(alias: str) -> str:
    """SQL interne : alias et statuts viennent uniquement du code."""
    value = f"CASE WHEN {alias}.manual_override=1 THEN {alias}.manual_status ELSE {alias}.current_status END"
    allowed = ",".join(f"'{status}'" for status in STATUS_ORDER)
    return f"CASE WHEN ({value}) IN ({allowed}) THEN ({value}) ELSE 'OTHER' END"


def init_application_history(connection: sqlite3.Connection) -> None:
    new = effective_status_sql("NEW")
    old = effective_status_sql("OLD")
    connection.execute("""
        CREATE TABLE IF NOT EXISTS application_status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL,
            event_kind TEXT NOT NULL CHECK(event_kind IN ('created','snapshot','change')),
            previous_status TEXT,
            status TEXT NOT NULL,
            recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f+00:00','now'))
        )
    """)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_status_history_user_date ON application_status_history(user_id, recorded_at)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_status_history_application ON application_status_history(application_id)"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS application_history_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    connection.execute(
        "INSERT OR IGNORE INTO application_history_metadata VALUES ('started_at', strftime('%Y-%m-%dT%H:%M:%f+00:00','now'))"
    )
    connection.execute(f"""
        CREATE TRIGGER IF NOT EXISTS record_application_created
        AFTER INSERT ON applications WHEN NEW.user_id IS NOT NULL BEGIN
            INSERT INTO application_status_history(application_id,user_id,event_kind,status)
            VALUES (NEW.id,NEW.user_id,'created',{new});
        END
    """)
    connection.execute(f"""
        CREATE TRIGGER IF NOT EXISTS record_application_status_changed
        AFTER UPDATE OF current_status, manual_status, manual_override ON applications
        WHEN NEW.user_id IS NOT NULL AND OLD.user_id IS NEW.user_id
             AND ({old}) IS NOT ({new}) BEGIN
            INSERT INTO application_status_history(application_id,user_id,event_kind,previous_status,status)
            VALUES (NEW.id,NEW.user_id,'change',{old},{new});
        END
    """)
    connection.execute(f"""
        CREATE TRIGGER IF NOT EXISTS reset_application_history_on_owner_change
        AFTER UPDATE OF user_id ON applications WHEN OLD.user_id IS NOT NEW.user_id BEGIN
            DELETE FROM application_status_history WHERE application_id=NEW.id;
            INSERT INTO application_status_history(application_id,user_id,event_kind,status)
            SELECT NEW.id,NEW.user_id,'snapshot',{new} WHERE NEW.user_id IS NOT NULL;
        END
    """)
    connection.execute("""
        CREATE TRIGGER IF NOT EXISTS delete_application_history
        AFTER DELETE ON applications BEGIN
            DELETE FROM application_status_history WHERE application_id=OLD.id;
        END
    """)
    connection.execute(f"""
        INSERT INTO application_status_history(application_id,user_id,event_kind,status)
        SELECT a.id,a.user_id,'snapshot',{effective_status_sql("a")}
        FROM applications a WHERE a.user_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM application_status_history h WHERE h.application_id=a.id
        )
    """)

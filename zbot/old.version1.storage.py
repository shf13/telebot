import sqlite3
from dataclasses import dataclass
from typing import Optional, Iterable


@dataclass
class UserPrefs:
    user_id: int
    chat_id: int
    time_hhmm: Optional[str] = None   # "08:15"
    timezone: str = "UTC"
    enabled: bool = True


class Storage:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS user_prefs (
                    user_id INTEGER PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    time_hhmm TEXT,
                    timezone TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1
                )
                """
            )

    def upsert_user(self, user_id: int, chat_id: int, timezone: str):
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO user_prefs(user_id, chat_id, timezone, enabled)
                VALUES(?, ?, ?, 1)
                ON CONFLICT(user_id) DO UPDATE SET
                    chat_id=excluded.chat_id,
                    timezone=excluded.timezone
                """,
                (user_id, chat_id, timezone),
            )

    def set_timezone(self, user_id: int, chat_id: int, timezone: str):
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO user_prefs(user_id, chat_id, timezone, enabled)
                VALUES(?, ?, ?, 1)
                ON CONFLICT(user_id) DO UPDATE SET
                    chat_id=excluded.chat_id,
                    timezone=excluded.timezone,
                    enabled=1
                """,
                (user_id, chat_id, timezone),
            )

    def set_time(self, user_id: int, chat_id: int, time_hhmm: str):
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO user_prefs(user_id, chat_id, time_hhmm, enabled, timezone)
                VALUES(?, ?, ?, 1, COALESCE((SELECT timezone FROM user_prefs WHERE user_id=?), 'UTC'))
                ON CONFLICT(user_id) DO UPDATE SET
                    chat_id=excluded.chat_id,
                    time_hhmm=excluded.time_hhmm,
                    enabled=1
                """,
                (user_id, chat_id, time_hhmm, user_id),
            )

    def set_enabled(self, user_id: int, enabled: bool):
        with self._connect() as con:
            con.execute(
                "UPDATE user_prefs SET enabled=? WHERE user_id=?",
                (1 if enabled else 0, user_id),
            )

    def get_user(self, user_id: int) -> Optional[UserPrefs]:
        with self._connect() as con:
            row = con.execute(
                "SELECT user_id, chat_id, time_hhmm, timezone, enabled FROM user_prefs WHERE user_id=?",
                (user_id,),
            ).fetchone()
        if not row:
            return None
        return UserPrefs(
            user_id=row[0],
            chat_id=row[1],
            time_hhmm=row[2],
            timezone=row[3],
            enabled=bool(row[4]),
        )

    def list_enabled_users(self) -> Iterable[UserPrefs]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT user_id, chat_id, time_hhmm, timezone, enabled FROM user_prefs WHERE enabled=1"
            ).fetchall()
        for row in rows:
            yield UserPrefs(
                user_id=row[0],
                chat_id=row[1],
                time_hhmm=row[2],
                timezone=row[3],
                enabled=bool(row[4]),
            )
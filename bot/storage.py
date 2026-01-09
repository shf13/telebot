import sqlite3
from dataclasses import dataclass
from typing import Optional, Iterable


@dataclass
class UserPrefs:
    user_id: int
    chat_id: int
    time_hhmm: Optional[str] = None   # "08:15"
    enabled: bool = True


class Storage:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _table_columns(self, con) -> set[str]:
        rows = con.execute("PRAGMA table_info(user_prefs)").fetchall()
        # PRAGMA columns: cid, name, type, notnull, dflt_value, pk
        return {r[1] for r in rows}

    def _init_db(self):
        with self._connect() as con:
            # Create minimal schema if not exists
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS user_prefs (
                    user_id INTEGER PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    time_hhmm TEXT,
                    enabled INTEGER NOT NULL DEFAULT 1
                )
                """
            )

            # If you previously had a timezone column, keep it (no need to drop).
            # If you want to ensure it's not there, you'd need a rebuild; not necessary.

    def upsert_user(self, user_id: int, chat_id: int):
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO user_prefs(user_id, chat_id, enabled)
                VALUES(?, ?, 1)
                ON CONFLICT(user_id) DO UPDATE SET
                    chat_id=excluded.chat_id
                """,
                (user_id, chat_id),
            )

    def set_time(self, user_id: int, chat_id: int, time_hhmm: str):
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO user_prefs(user_id, chat_id, time_hhmm, enabled)
                VALUES(?, ?, ?, 1)
                ON CONFLICT(user_id) DO UPDATE SET
                    chat_id=excluded.chat_id,
                    time_hhmm=excluded.time_hhmm,
                    enabled=1
                """,
                (user_id, chat_id, time_hhmm),
            )

    def set_enabled(self, user_id: int, enabled: bool):
        with self._connect() as con:
            con.execute(
                "UPDATE user_prefs SET enabled=? WHERE user_id=?",
                (1 if enabled else 0, user_id),
            )

    def get_user(self, user_id: int) -> Optional[UserPrefs]:
        with self._connect() as con:
            cols = self._table_columns(con)

            # Backward-compatible read if old DB has timezone column
            if "timezone" in cols:
                row = con.execute(
                    "SELECT user_id, chat_id, time_hhmm, enabled FROM user_prefs WHERE user_id=?",
                    (user_id,),
                ).fetchone()
            else:
                row = con.execute(
                    "SELECT user_id, chat_id, time_hhmm, enabled FROM user_prefs WHERE user_id=?",
                    (user_id,),
                ).fetchone()

        if not row:
            return None

        return UserPrefs(
            user_id=row[0],
            chat_id=row[1],
            time_hhmm=row[2],
            enabled=bool(row[3]),
        )

    def list_enabled_users(self) -> Iterable[UserPrefs]:
        with self._connect() as con:
            cols = self._table_columns(con)

            # Backward-compatible query even if timezone exists
            if "timezone" in cols:
                rows = con.execute(
                    "SELECT user_id, chat_id, time_hhmm, enabled FROM user_prefs WHERE enabled=1"
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT user_id, chat_id, time_hhmm, enabled FROM user_prefs WHERE enabled=1"
                ).fetchall()

        for row in rows:
            yield UserPrefs(
                user_id=row[0],
                chat_id=row[1],
                time_hhmm=row[2],
                enabled=bool(row[3]),
            )
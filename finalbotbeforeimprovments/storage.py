import sqlite3
from dataclasses import dataclass
from typing import Optional, Iterable


@dataclass
class UserPrefs:
    user_id: int
    chat_id: int
    time_hhmm: Optional[str] = None  # "08:15"
    enabled: bool = True
    language: Optional[str] = None   # "en" | "ar" | "ru"


class Storage:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _table_columns(self, con) -> set[str]:
        rows = con.execute("PRAGMA table_info(user_prefs)").fetchall()
        return {r[1] for r in rows}

    def _init_db(self):
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS user_prefs (
                    user_id INTEGER PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    time_hhmm TEXT,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    language TEXT
                )
                """
            )

            # migration: add language column if older DB doesn't have it
            cols = self._table_columns(con)
            if "language" not in cols:
                con.execute("ALTER TABLE user_prefs ADD COLUMN language TEXT")

    def upsert_user(self, user_id: int, chat_id: int):
        """Create user row if missing; always update chat_id."""
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

    def set_language(self, user_id: int, chat_id: int, language: str):
        """Set language and ensure user exists."""
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO user_prefs(user_id, chat_id, enabled, language)
                VALUES(?, ?, 1, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    chat_id=excluded.chat_id,
                    language=excluded.language
                """,
                (user_id, chat_id, language),
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
            row = con.execute(
                "SELECT user_id, chat_id, time_hhmm, enabled, language FROM user_prefs WHERE user_id=?",
                (user_id,),
            ).fetchone()

        if not row:
            return None

        return UserPrefs(
            user_id=row[0],
            chat_id=row[1],
            time_hhmm=row[2],
            enabled=bool(row[3]),
            language=row[4],
        )

    def list_enabled_users(self) -> Iterable[UserPrefs]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT user_id, chat_id, time_hhmm, enabled, language FROM user_prefs WHERE enabled=1"
            ).fetchall()

        for row in rows:
            yield UserPrefs(
                user_id=row[0],
                chat_id=row[1],
                time_hhmm=row[2],
                enabled=bool(row[3]),
                language=row[4],
            )


    def get_stats(self):
        """Returns (total_users, enabled_users, language_dict)"""
        with self._connect() as con:
            # Count total
            total = con.execute("SELECT COUNT(*) FROM user_prefs").fetchone()[0]
            # Count enabled
            enabled = con.execute("SELECT COUNT(*) FROM user_prefs WHERE enabled=1").fetchone()[0]
            # Count languages
            langs = {}
            rows = con.execute("SELECT language, COUNT(*) FROM user_prefs GROUP BY language").fetchall()
            for lang, count in rows:
                if lang:
                    langs[lang] = count
                else:
                    langs['unknown'] = count
                    
        return total, enabled, langs            
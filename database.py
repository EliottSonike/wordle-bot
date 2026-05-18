import sqlite3
from datetime import datetime, timezone

DB_PATH = "wordle.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scores (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT    NOT NULL,
                username    TEXT    NOT NULL,
                wordle_num  INTEGER NOT NULL,
                attempts    INTEGER NOT NULL,
                recorded_at TEXT    NOT NULL,
                week_start  TEXT    NOT NULL,
                UNIQUE(user_id, wordle_num)
            )
        """)
        conn.commit()


def insert_score(user_id, username, wordle_num, attempts, week_start):
    """Returns True if inserted, False if already exists."""
    try:
        with get_db() as conn:
            conn.execute(
                """INSERT INTO scores
                   (user_id, username, wordle_num, attempts, recorded_at, week_start)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    user_id,
                    username,
                    wordle_num,
                    attempts,
                    datetime.now(timezone.utc).isoformat(),
                    week_start,
                ),
            )
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def get_weekly_rows(week_start):
    with get_db() as conn:
        return conn.execute(
            """SELECT username,
                      COUNT(*)                                          AS games,
                      AVG(attempts)                                     AS avg_attempts,
                      MIN(attempts)                                     AS best,
                      SUM(CASE WHEN attempts = 7 THEN 1 ELSE 0 END)    AS failed
               FROM scores
               WHERE week_start = ?
               GROUP BY user_id
               ORDER BY avg_attempts ASC, games DESC""",
            (week_start,),
        ).fetchall()


def get_user_scores(user_id, week_start):
    with get_db() as conn:
        return conn.execute(
            """SELECT wordle_num, attempts FROM scores
               WHERE user_id = ? AND week_start = ?
               ORDER BY wordle_num""",
            (user_id, week_start),
        ).fetchall()

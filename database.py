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
                guild_id    TEXT    NOT NULL,
                user_id     TEXT    NOT NULL,
                username    TEXT    NOT NULL,
                wordle_num  INTEGER NOT NULL,
                attempts    INTEGER NOT NULL,
                recorded_at TEXT    NOT NULL,
                week_start  TEXT    NOT NULL,
                UNIQUE(guild_id, user_id, wordle_num)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_names (
                guild_id   TEXT NOT NULL,
                user_id    TEXT NOT NULL,
                username   TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        conn.commit()


def insert_score(guild_id, user_id, username, wordle_num, attempts, week_start):
    """Returns True if inserted, False if already exists."""
    try:
        with get_db() as conn:
            conn.execute(
                """INSERT INTO scores
                   (guild_id, user_id, username, wordle_num, attempts, recorded_at, week_start)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    guild_id,
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


def get_weekly_rows(guild_id, week_start):
    with get_db() as conn:
        return conn.execute(
            """WITH
                 wordles AS (
                   SELECT DISTINCT wordle_num FROM scores WHERE guild_id = ? AND week_start = ?
                 ),
                 players AS (
                   SELECT user_id, MAX(username) AS username FROM scores WHERE guild_id = ? AND week_start = ? GROUP BY user_id
                 ),
                 all_combos AS (
                   SELECT p.user_id, p.username, w.wordle_num FROM players p CROSS JOIN wordles w
                 ),
                 filled AS (
                   SELECT ac.user_id, ac.username,
                          COALESCE(s.attempts, 7) AS attempts
                   FROM all_combos ac
                   LEFT JOIN scores s
                     ON s.guild_id = ? AND s.user_id = ac.user_id AND s.wordle_num = ac.wordle_num
                 )
               SELECT user_id,
                      username,
                      SUM(attempts)                                        AS total_points,
                      COUNT(*)                                             AS total_wordles,
                      SUM(CASE WHEN attempts <= 6 THEN 1 ELSE 0 END)      AS played,
                      MIN(attempts)                                        AS best
               FROM filled
               GROUP BY user_id
               ORDER BY total_points ASC, played DESC""",
            (guild_id, week_start, guild_id, week_start, guild_id),
        ).fetchall()


def upsert_username(guild_id: str, user_id: str, username: str):
    """Keep user_names up to date with the latest display name."""
    with get_db() as conn:
        conn.execute(
            """INSERT INTO user_names (guild_id, user_id, username, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(guild_id, user_id) DO UPDATE SET
                   username   = excluded.username,
                   updated_at = excluded.updated_at""",
            (guild_id, user_id, username, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()


def get_user_id_by_name(guild_id: str, name: str) -> str | None:
    """Resolve a display name to a user_id. Checks user_names first, then scores."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT user_id FROM user_names WHERE guild_id = ? AND username = ? LIMIT 1",
            (guild_id, name),
        ).fetchone()
        if row:
            return row["user_id"]
        row = conn.execute(
            "SELECT user_id FROM scores WHERE guild_id = ? AND username = ? LIMIT 1",
            (guild_id, name),
        ).fetchone()
        return row["user_id"] if row else None


def get_user_scores(guild_id, user_id, week_start):
    with get_db() as conn:
        return conn.execute(
            """SELECT wordle_num, attempts FROM scores
               WHERE guild_id = ? AND user_id = ? AND week_start = ?
               ORDER BY wordle_num""",
            (guild_id, user_id, week_start),
        ).fetchall()

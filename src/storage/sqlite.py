import sqlite3
import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


TIMEZONE = ZoneInfo("Asia/Shanghai")


class SQLiteStorage:
    """记录每次任务执行的历史，方便日后查看和统计"""

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "history.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _today(self) -> date:
        return datetime.now(TIMEZONE).date()

    def _now_iso(self) -> str:
        return datetime.now(TIMEZONE).isoformat()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    output_summary TEXT,
                    error_message TEXT,
                    report_path TEXT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT
                )
            """)
            self._ensure_task_history_schema(conn)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trend_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_name TEXT NOT NULL,
                    date TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    stars INTEGER DEFAULT 0,
                    forks INTEGER DEFAULT 0,
                    language TEXT DEFAULT '',
                    metric_name TEXT DEFAULT '',
                    metric_value INTEGER DEFAULT 0,
                    rank INTEGER DEFAULT 0,
                    UNIQUE(task_name, date, title)
                )
            """)
            self._ensure_trend_schema(conn)

    def _ensure_task_history_schema(self, conn: sqlite3.Connection):
        columns = {row[1] for row in conn.execute("PRAGMA table_info(task_history)").fetchall()}
        if "report_path" not in columns:
            conn.execute("ALTER TABLE task_history ADD COLUMN report_path TEXT")

    def _ensure_trend_schema(self, conn: sqlite3.Connection):
        columns = {row[1] for row in conn.execute("PRAGMA table_info(trend_items)").fetchall()}
        if "metric_name" not in columns:
            conn.execute("ALTER TABLE trend_items ADD COLUMN metric_name TEXT DEFAULT ''")
        if "metric_value" not in columns:
            conn.execute("ALTER TABLE trend_items ADD COLUMN metric_value INTEGER DEFAULT 0")

        conn.execute("""
            UPDATE trend_items
            SET metric_name = 'stars'
            WHERE (metric_name IS NULL OR metric_name = '') AND stars IS NOT NULL
        """)
        conn.execute("""
            UPDATE trend_items
            SET metric_value = stars
            WHERE (metric_value IS NULL OR metric_value = 0) AND stars > 0
        """)

    @staticmethod
    def _as_int(value, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _extract_metric(self, extra: dict) -> tuple[str, int]:
        if "stars" in extra:
            return "stars", self._as_int(extra.get("stars"))
        if "score" in extra:
            return "score", self._as_int(extra.get("score"))
        if "comments" in extra:
            return "comments", self._as_int(extra.get("comments"))
        return "", 0

    def save_trend_items(self, task_name: str, items: list[dict], run_date: str | None = None):
        today = run_date or self._today().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            for rank, item in enumerate(items, 1):
                extra = item.get("extra") or {}
                metric_name, metric_value = self._extract_metric(extra)
                conn.execute(
                    """INSERT OR REPLACE INTO trend_items
                       (task_name, date, title, url, stars, forks, language, metric_name, metric_value, rank)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        task_name,
                        today,
                        item["title"],
                        item["url"],
                        self._as_int(extra.get("stars")),
                        self._as_int(extra.get("forks")),
                        extra.get("language", ""),
                        metric_name,
                        metric_value,
                        rank,
                    ),
                )

    def get_trend_history(
        self, task_name: str, days: int = 7, end_date: str | date | None = None
    ) -> dict[str, list[dict]]:
        if days <= 0:
            return {}

        if end_date is None:
            end = self._today()
        elif isinstance(end_date, str):
            end = date.fromisoformat(end_date)
        else:
            end = end_date

        start = end - timedelta(days=days)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT * FROM trend_items
                   WHERE task_name = ? AND date >= ? AND date < ?
                   ORDER BY date DESC, rank ASC""",
                (task_name, start.isoformat(), end.isoformat()),
            ).fetchall()
        result = {}
        for r in rows:
            d = dict(r)
            date_key = d.pop("date")
            result.setdefault(date_key, []).append(d)
        return result

    def record_start(self, task_name: str) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "INSERT INTO task_history (task_name, status, started_at) VALUES (?, ?, ?)",
                (task_name, "running", self._now_iso()),
            )
            return cur.lastrowid

    def record_success(self, record_id: int, output_summary: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE task_history SET status=?, output_summary=?, finished_at=? WHERE id=?",
                ("success", output_summary[:500], self._now_iso(), record_id),
            )

    def record_report(self, record_id: int, report_path: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE task_history SET report_path=? WHERE id=?",
                (report_path, record_id),
            )

    def get_report_path(self, record_id: int) -> str | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT report_path FROM task_history WHERE id=?", (record_id,)
            ).fetchone()
        return row[0] if row and row[0] else None

    def record_failure(self, record_id: int, error: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE task_history SET status=?, error_message=?, finished_at=? WHERE id=?",
                ("failed", error[:500], self._now_iso(), record_id),
            )

    def get_recent(self, limit: int = 20) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM task_history ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

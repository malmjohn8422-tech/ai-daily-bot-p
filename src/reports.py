import json
import os
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = PROJECT_ROOT / "reports"
TIMEZONE = ZoneInfo("Asia/Shanghai")


class ReportArchive:
    """Store generated reports as Markdown files plus small JSON metadata sidecars."""

    def __init__(self, root: str | os.PathLike | None = None):
        self.root = Path(root) if root is not None else REPORT_ROOT

    @staticmethod
    def _safe_slug(task_name: str) -> str:
        slug = re.sub(r"[^\w]+", "-", task_name, flags=re.UNICODE).strip("-_").lower()
        return (slug or "task")[:40]

    def _stored_path(self, path: Path) -> str:
        try:
            return path.relative_to(PROJECT_ROOT).as_posix()
        except ValueError:
            return str(path)

    def resolve(self, stored_path: str | os.PathLike) -> Path:
        path = Path(stored_path)
        if path.is_absolute():
            return path
        return PROJECT_ROOT / path

    def build_path(self, task_name: str, record_id: int) -> Path:
        today = datetime.now(TIMEZONE).date().isoformat()
        filename = f"{record_id:06d}-{self._safe_slug(task_name)}.md"
        return self.root / today / filename

    def save(
        self,
        task_name: str,
        record_id: int,
        content: str,
        items: list[dict] | None = None,
    ) -> str:
        path = self.build_path(task_name, record_id)
        path.parent.mkdir(parents=True, exist_ok=True)

        tmp_path = path.with_suffix(".md.tmp")
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(tmp_path, path)

        meta = {
            "task_name": task_name,
            "record_id": record_id,
            "created_at": datetime.now(TIMEZONE).isoformat(),
            "items": items or [],
        }
        meta_path = path.with_suffix(".json")
        tmp_meta_path = meta_path.with_suffix(".json.tmp")
        tmp_meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp_meta_path, meta_path)

        return self._stored_path(path)

    def load(self, stored_path: str | os.PathLike) -> str:
        return self.resolve(stored_path).read_text(encoding="utf-8")

    def exists(self, stored_path: str | os.PathLike | None) -> bool:
        return bool(stored_path) and self.resolve(stored_path).is_file()

    def load_items(self, stored_path: str | os.PathLike) -> list[dict]:
        meta_path = self.resolve(stored_path).with_suffix(".json")
        if not meta_path.is_file():
            return []

        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        items = meta.get("items")
        return items if isinstance(items, list) else []


report_archive = ReportArchive()

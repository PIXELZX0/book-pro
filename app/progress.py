from datetime import datetime, timezone
from threading import Lock
from typing import Any

_ALLOWED_STATUS = {"queued", "processing", "completed", "failed"}


def _to_iso_utc(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


class UploadProgressStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._items: dict[str, dict[str, Any]] = {}

    def init(self, upload_id: str, *, file_name: str) -> None:
        now = datetime.now(tz=timezone.utc).timestamp()
        with self._lock:
            self._items[upload_id] = {
                "upload_id": upload_id,
                "file_name": file_name,
                "book_title": "",
                "status": "queued",
                "progress": 0,
                "stage": "queued",
                "message": "업로드 대기 중",
                "chapter_index": None,
                "chapter_total": None,
                "chapter_title": None,
                "character_index": None,
                "character_total": None,
                "character_name": None,
                "error": "",
                "updated_at": _to_iso_utc(now),
            }

    def get(self, upload_id: str) -> dict[str, Any] | None:
        with self._lock:
            item = self._items.get(upload_id)
            if not item:
                return None
            return dict(item)

    def list(self, *, statuses: set[str] | None = None) -> list[dict[str, Any]]:
        with self._lock:
            items = [
                dict(item)
                for item in self._items.values()
                if statuses is None or item.get("status") in statuses
            ]
        items.sort(key=lambda row: row.get("updated_at", ""), reverse=True)
        return items

    def update(self, upload_id: str, **fields: Any) -> dict[str, Any] | None:
        now = datetime.now(tz=timezone.utc).timestamp()
        with self._lock:
            item = self._items.get(upload_id)
            if not item:
                return None

            status = fields.get("status")
            if isinstance(status, str) and status in _ALLOWED_STATUS:
                item["status"] = status

            progress = fields.get("progress")
            if isinstance(progress, (int, float)):
                item["progress"] = max(0, min(int(progress), 100))

            for key in (
                "book_title",
                "stage",
                "message",
                "chapter_index",
                "chapter_total",
                "chapter_title",
                "character_index",
                "character_total",
                "character_name",
                "error",
            ):
                if key in fields:
                    item[key] = fields[key]

            item["updated_at"] = _to_iso_utc(now)
            return dict(item)

    def complete(self, upload_id: str, *, message: str = "요약 완료") -> dict[str, Any] | None:
        return self.update(
            upload_id,
            status="completed",
            progress=100,
            stage="done",
            message=message,
            error="",
        )

    def fail(self, upload_id: str, *, error: str) -> dict[str, Any] | None:
        return self.update(
            upload_id,
            status="failed",
            progress=100,
            stage="failed",
            message="요약 실패",
            error=error,
        )


_store = UploadProgressStore()


def init_upload_progress(upload_id: str, *, file_name: str) -> None:
    _store.init(upload_id, file_name=file_name)


def get_upload_progress(upload_id: str) -> dict[str, Any] | None:
    return _store.get(upload_id)


def update_upload_progress(upload_id: str, **fields: Any) -> dict[str, Any] | None:
    return _store.update(upload_id, **fields)


def complete_upload_progress(upload_id: str, *, message: str = "요약 완료") -> dict[str, Any] | None:
    return _store.complete(upload_id, message=message)


def fail_upload_progress(upload_id: str, *, error: str) -> dict[str, Any] | None:
    return _store.fail(upload_id, error=error)


def list_upload_progress(*, active_only: bool = False) -> list[dict[str, Any]]:
    if active_only:
        return _store.list(statuses={"queued", "processing"})
    return _store.list()

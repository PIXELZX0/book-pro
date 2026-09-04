import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

_MAX_READ_BYTES = 200 * 1024
_MAX_WRITE_BYTES = 1024 * 1024
_DEFAULT_READ_CHARS = 12000
_MAX_READ_CHARS = 24000
_ALLOWED_EXTENSIONS = {".md", ".json", ".txt"}
_PROTECTED_FILES = {"studio.json", "series.json"}
_HISTORY_DIR = ".studio-history"
_PENDING_ACTIONS_FILE = "studio/pending-actions.json"

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": (
                "List files and directories under a relative path inside the "
                "project sandbox (and the series sandbox when the project belongs to a series)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path. Use \"\" for the project root.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file (.md/.json/.txt) from the sandbox.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path."},
                    "offset": {"type": "integer", "description": "Character offset to start from."},
                    "max_chars": {"type": "integer", "description": f"Max characters to return (<= {_MAX_READ_CHARS})."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Create or overwrite a text file with the given content. "
                "Chapter files must be stored as chapter/c-<number>-<title>.md."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path."},
                    "content": {"type": "string", "description": "Full file content to write."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Replace occurrences of an exact substring inside a text file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path."},
                    "find": {"type": "string", "description": "Exact text to find."},
                    "replace": {"type": "string", "description": "Replacement text."},
                    "count": {"type": "integer", "description": "Number of occurrences to replace (default 1)."},
                },
                "required": ["path", "find", "replace"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Delete a file (moved to books/.trash so it can be recovered manually).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path."},
                },
                "required": ["path"],
            },
        },
    },
]

TOOL_NAMES = {schema["function"]["name"] for schema in TOOL_SCHEMAS}


class StudioFileSandbox:
    def __init__(self, root_dir: str | Path, *, slug: str, series_slug: str | None = None) -> None:
        self.root_dir = Path(root_dir)
        self.slug = slug
        self.series_slug = series_slug
        self.primary_root = self.root_dir / slug
        self.roots: list[Path] = [self.primary_root]
        if series_slug:
            self.roots.append(self.root_dir / series_slug)

    def root_of(self, resolved: Path) -> Path:
        for root in self.roots:
            if resolved.is_relative_to(root.resolve()):
                return root
        raise ValueError("샌드박스 외부 경로입니다.")

    def resolve(self, raw_path: str) -> Path:
        cleaned = (raw_path or "").strip().replace("\\", "/")
        if not cleaned or cleaned == ".":
            return self.primary_root.resolve()
        if cleaned.startswith("/") or Path(cleaned).is_absolute():
            raise ValueError(f"프로젝트 내부의 상대 경로만 사용할 수 있습니다: {raw_path}")
        candidate = Path(cleaned)
        if any(part == ".." for part in candidate.parts):
            raise ValueError(f"상위 디렉터리 이동(..)은 허용되지 않습니다: {raw_path}")
        if any(part.startswith(".") for part in candidate.parts):
            raise ValueError(f"숨김 파일/폴더에는 접근할 수 없습니다: {raw_path}")

        resolved_candidates = [
            (root / candidate).resolve() for root in self.roots
        ]
        for resolved in resolved_candidates:
            if resolved.exists():
                self._ensure_within(resolved)
                return resolved
        primary = resolved_candidates[0]
        self._ensure_within(primary)
        return primary

    def _ensure_within(self, resolved: Path) -> None:
        for root in self.roots:
            if resolved.is_relative_to(root.resolve()):
                return
        raise ValueError(f"샌드박스를 벗어난 경로입니다: {resolved}")

    def check_readable(self, resolved: Path) -> None:
        if resolved.suffix.lower() not in _ALLOWED_EXTENSIONS:
            raise ValueError(f"허용되지 않은 파일 형식입니다: {resolved.name}")
        if not resolved.is_file():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {resolved.name}")

    def check_writable(self, resolved: Path) -> None:
        if resolved.name in _PROTECTED_FILES:
            raise ValueError(f"보호된 파일은 직접 수정할 수 없습니다: {resolved.name}")
        if resolved.suffix.lower() not in _ALLOWED_EXTENSIONS:
            raise ValueError(f"허용되지 않은 파일 형식입니다: {resolved.name}")

    def snapshot(self, resolved: Path, *, tool: str) -> dict[str, Any] | None:
        if not resolved.is_file():
            return None
        root = self.root_of(resolved)
        rel = resolved.relative_to(root.resolve())
        root_label = self.slug if root == self.primary_root else (self.series_slug or "series")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        entry_id = f"{stamp}-{uuid4().hex[:8]}"
        history_dir = self.primary_root / _HISTORY_DIR
        backup_path = history_dir / entry_id / root_label / rel
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(resolved, backup_path)

        index_path = history_dir / "index.json"
        entries: list[dict[str, Any]] = []
        if index_path.exists():
            try:
                loaded = json.loads(index_path.read_text(encoding="utf-8"))
                entries = loaded.get("entries", []) if isinstance(loaded, dict) else []
            except (json.JSONDecodeError, OSError):
                entries = []
        entry = {
            "id": entry_id,
            "tool": tool,
            "root": root_label,
            "path": str(rel),
            "backup_path": str(backup_path),
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        entries.append(entry)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(
            json.dumps({"entries": entries[-200:]}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return entry


class PendingActionStore:
    def __init__(self, root_dir: str | Path, *, slug: str) -> None:
        self.path = Path(root_dir) / slug / _PENDING_ACTIONS_FILE

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        actions = payload.get("actions", []) if isinstance(payload, dict) else []
        return [action for action in actions if isinstance(action, dict)]

    def _save(self, actions: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"actions": actions}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list(self) -> list[dict[str, Any]]:
        return self._load()

    def add(self, *, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        actions = self._load()
        action = {
            "id": f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-{uuid4().hex[:8]}",
            "tool": tool,
            "arguments": arguments,
            "path": str(arguments.get("path", "")),
            "preview": _build_preview(tool, arguments),
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        actions.append(action)
        self._save(actions[-50:])
        return action

    def take(self, action_id: str) -> dict[str, Any]:
        actions = self._load()
        for index, action in enumerate(actions):
            if action.get("id") == action_id:
                self._save(actions[:index] + actions[index + 1 :])
                return action
        raise FileNotFoundError(f"승인 대기 작업을 찾을 수 없습니다: {action_id}")


def _build_preview(tool: str, arguments: dict[str, Any]) -> str:
    if tool == "edit_file":
        return (
            f"찾기: {str(arguments.get('find', ''))[:600]}\n"
            f"바꾸기: {str(arguments.get('replace', ''))[:600]}"
        )
    if tool == "delete_file":
        return f"삭제: {arguments.get('path', '')}"
    content = str(arguments.get("content", ""))
    head = content[:2000]
    suffix = "\n..." if len(content) > 2000 else ""
    return f"{head}{suffix}"


def list_files(sandbox: StudioFileSandbox, path: str = "") -> dict[str, Any]:
    target = sandbox.resolve(path)
    if not target.exists():
        raise FileNotFoundError(f"디렉터리를 찾을 수 없습니다: {path}")

    files: list[str] = []
    directories: list[str] = []
    roots = sandbox.roots if target == sandbox.primary_root.resolve() else [target]

    for root in roots:
        if not root.exists():
            continue
        for entry in sorted(root.rglob("*")):
            rel = entry.relative_to(root.resolve())
            if any(part.startswith(".") for part in rel.parts):
                continue
            if entry.is_dir():
                directories.append(str(rel))
            elif entry.suffix.lower() in _ALLOWED_EXTENSIONS:
                files.append(str(rel))

    return {
        "path": path or ".",
        "files": sorted(set(files)),
        "directories": sorted(set(directories)),
    }


def read_file(
    sandbox: StudioFileSandbox,
    path: str,
    offset: int = 0,
    max_chars: int = _DEFAULT_READ_CHARS,
) -> dict[str, Any]:
    resolved = sandbox.resolve(path)
    sandbox.check_readable(resolved)
    if resolved.stat().st_size > _MAX_READ_BYTES:
        raise ValueError(f"파일이 너무 큽니다 (최대 {_MAX_READ_BYTES // 1024}KB): {resolved.name}")

    content = resolved.read_text(encoding="utf-8", errors="ignore")
    start = max(int(offset or 0), 0)
    limit = min(max(int(max_chars or _DEFAULT_READ_CHARS), 1), _MAX_READ_CHARS)
    chunk = content[start : start + limit]
    return {
        "path": path,
        "total_chars": len(content),
        "offset": start,
        "returned_chars": len(chunk),
        "content": chunk,
    }


def write_file(sandbox: StudioFileSandbox, path: str, content: str) -> dict[str, Any]:
    resolved = sandbox.resolve(path)
    sandbox.check_writable(resolved)
    payload = str(content or "")
    if len(payload.encode("utf-8")) > _MAX_WRITE_BYTES:
        raise ValueError(f"쓰기 내용이 너무 큽니다 (최대 {_MAX_WRITE_BYTES // 1024}KB)")

    created = not resolved.exists()
    sandbox.snapshot(resolved, tool="write_file")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(payload, encoding="utf-8")
    return {
        "path": path,
        "bytes": len(payload.encode("utf-8")),
        "created": created,
        "message": f"{'생성' if created else '덮어쓰기'} 완료: {path}",
    }


def edit_file(
    sandbox: StudioFileSandbox,
    path: str,
    find: str,
    replace: str,
    count: int = 1,
) -> dict[str, Any]:
    resolved = sandbox.resolve(path)
    sandbox.check_readable(resolved)
    sandbox.check_writable(resolved)

    target = str(find or "")
    if not target:
        raise ValueError("찾을 텍스트(find)를 입력해 주세요.")
    content = resolved.read_text(encoding="utf-8", errors="ignore")
    occurrences = content.count(target)
    if occurrences == 0:
        raise ValueError("찾을 텍스트가 파일에 없습니다.")

    applied = min(max(int(count or 1), 1), occurrences)
    sandbox.snapshot(resolved, tool="edit_file")
    resolved.write_text(content.replace(target, str(replace or ""), applied), encoding="utf-8")
    return {
        "path": path,
        "replaced": applied,
        "occurrences_total": occurrences,
        "message": f"{applied}군데 치환 완료: {path}",
    }


def delete_file(sandbox: StudioFileSandbox, path: str) -> dict[str, Any]:
    resolved = sandbox.resolve(path)
    sandbox.check_readable(resolved)
    sandbox.check_writable(resolved)

    root = sandbox.root_of(resolved)
    rel = resolved.relative_to(root.resolve())
    root_label = sandbox.slug if root == sandbox.primary_root else (sandbox.series_slug or "series")
    trash_root = sandbox.root_dir / ".trash"
    trash_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    trash_target = trash_root / f"{sandbox.slug}-{stamp}-{uuid4().hex[:8]}" / root_label / rel
    trash_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(resolved), str(trash_target))
    return {
        "path": path,
        "trash_path": str(trash_target),
        "message": f"삭제 완료(휴지통 이동): {path}",
    }


_TOOL_IMPLEMENTATIONS = {
    "list_files": lambda sandbox, **args: list_files(sandbox, str(args.get("path", "") or "")),
    "read_file": lambda sandbox, **args: read_file(
        sandbox,
        str(args.get("path", "")),
        offset=_to_int(args.get("offset"), 0),
        max_chars=_to_int(args.get("max_chars"), _DEFAULT_READ_CHARS),
    ),
    "write_file": lambda sandbox, **args: write_file(
        sandbox, str(args.get("path", "")), str(args.get("content", ""))
    ),
    "edit_file": lambda sandbox, **args: edit_file(
        sandbox,
        str(args.get("path", "")),
        str(args.get("find", "")),
        str(args.get("replace", "")),
        count=_to_int(args.get("count"), 1),
    ),
    "delete_file": lambda sandbox, **args: delete_file(sandbox, str(args.get("path", ""))),
}

_WRITE_TOOLS = {"write_file", "edit_file", "delete_file"}


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def execute_tool(
    sandbox: StudioFileSandbox,
    *,
    name: str,
    arguments: dict[str, Any],
    mode: str = "auto",
    pending_store: PendingActionStore | None = None,
) -> dict[str, Any]:
    if name not in _TOOL_IMPLEMENTATIONS:
        return {"error": f"알 수 없는 도구입니다: {name}"}

    if mode == "approve" and name in _WRITE_TOOLS and pending_store is not None:
        action = pending_store.add(tool=name, arguments=arguments)
        return {
            "pending": True,
            "message": "승인 대기 상태로 저장되었습니다. 사용자가 승인하면 적용됩니다.",
            "action": action,
        }

    implementation = _TOOL_IMPLEMENTATIONS[name]
    try:
        return implementation(sandbox, **(arguments or {}))
    except (ValueError, FileNotFoundError, OSError) as exc:
        return {"error": str(exc)}


def execute_pending_action(sandbox: StudioFileSandbox, action: dict[str, Any]) -> dict[str, Any]:
    return execute_tool(
        sandbox,
        name=str(action.get("tool", "")),
        arguments=dict(action.get("arguments", {})),
        mode="auto",
    )


def list_history(root_dir: str | Path, *, slug: str) -> list[dict[str, Any]]:
    index_path = Path(root_dir) / slug / _HISTORY_DIR / "index.json"
    if not index_path.exists():
        return []
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    entries = payload.get("entries", []) if isinstance(payload, dict) else []
    return [entry for entry in entries if isinstance(entry, dict)]


def restore_history_entry(root_dir: str | Path, *, slug: str, entry_id: str) -> dict[str, Any]:
    entries = list_history(root_dir, slug=slug)
    entry = next((item for item in entries if item.get("id") == entry_id), None)
    if entry is None:
        raise FileNotFoundError(f"되돌릴 이력을 찾을 수 없습니다: {entry_id}")

    backup_path = Path(entry["backup_path"])
    if not backup_path.exists():
        raise FileNotFoundError(f"백업 파일이 없습니다: {entry_id}")

    root_label = entry.get("root", slug)
    root = Path(root_dir) / root_label
    target = root / str(entry.get("path", ""))
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("복원 경로가 올바르지 않습니다.")

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup_path, target)
    return {
        "slug": slug,
        "entry_id": entry_id,
        "path": str(entry.get("path", "")),
        "restored": True,
    }

"""持久化下行请求与上行事件；一个实例目录只允许一个 Adapter 持有。"""

import fcntl
import hashlib
import json
import os
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ag_ui.core import RunStartedEvent

from .config_sync import private_directory
from .events import build_abort_events


def _open_lock_file(path: Path):
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    return os.fdopen(fd, "a", encoding="utf-8")


class Journal:
    def __init__(self, root: Path, identity: str, on_event: Callable[[str], None] | None = None):
        self.root = private_directory(root)
        self._on_event = on_event
        self._lock = _open_lock_file(self.root / ".journal.lock")
        self.db = None
        try:
            fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._initialize(identity)
        except BlockingIOError:
            self.close()
            raise RuntimeError("adapter instance is already running") from None
        except BaseException:
            self.close()
            raise

    def __enter__(self) -> "Journal":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _notify(self, run_id: str) -> None:
        if self._on_event is not None:
            self._on_event(run_id)

    def _initialize(self, identity: str) -> None:
        path = self.root / "events.sqlite3"
        if path.is_symlink():
            raise ValueError("symlinked journal is not allowed")
        self.db = sqlite3.connect(path)
        os.chmod(path, 0o600)
        self.db.executescript("""
            PRAGMA synchronous=FULL;
            CREATE TABLE IF NOT EXISTS identity (value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY, thread_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
                terminal INTEGER NOT NULL DEFAULT 0, dispatched INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS events (
                run_id TEXT NOT NULL, sequence INTEGER NOT NULL, payload TEXT NOT NULL,
                PRIMARY KEY (run_id, sequence));
        """)
        saved = self.db.execute("SELECT value FROM identity").fetchone()
        if saved and saved[0] != identity:
            raise ValueError("journal identity mismatch; use a separate instance directory")
        with self.db:
            if not saved:
                self.db.execute("INSERT INTO identity VALUES (?)", (identity,))
            columns = {row[1] for row in self.db.execute("PRAGMA table_info(runs)")}
            if "dispatched" not in columns:
                # 旧日志无法证明未执行，按已发送处理，防止静默丢失上下文。
                self.db.execute("ALTER TABLE runs ADD COLUMN dispatched INTEGER NOT NULL DEFAULT 1")
            self.db.execute("CREATE INDEX IF NOT EXISTS runs_thread ON runs(thread_id, dispatched)")
        for (run_id,) in self.db.execute("SELECT run_id FROM runs WHERE terminal=0").fetchall():
            self.abort(run_id, "EXECUTION_UNKNOWN", "Adapter restarted; execution outcome unknown")

    def close(self) -> None:
        if self.db is not None:
            self.db.close()
        self._lock.close()

    def contains(self, run_id: str) -> bool:
        return self.db.execute("SELECT 1 FROM runs WHERE run_id=?", (run_id,)).fetchone() is not None

    def belongs_to(self, run_id: str, thread_id: str) -> bool:
        return (
            self.db.execute("SELECT 1 FROM runs WHERE run_id=? AND thread_id=?", (run_id, thread_id)).fetchone()
            is not None
        )

    def claim(self, run_id: str, thread_id: str, request: dict[str, Any]) -> bool:
        for value in (run_id, thread_id):
            if not value or len(value) > 200 or any(c in value for c in "\r\n\x00"):
                raise ValueError("invalid run/thread id")
        fingerprint = hashlib.sha256(json.dumps(request, sort_keys=True).encode("utf-8")).hexdigest()
        existing = self.db.execute("SELECT thread_id, fingerprint FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if existing:
            if existing != (thread_id, fingerprint):
                raise ValueError("run_id already belongs to a different request")
            return False
        with self.db:
            self.db.execute(
                "INSERT INTO runs(run_id,thread_id,fingerprint,dispatched) VALUES (?,?,?,0)",
                (run_id, thread_id, fingerprint),
            )
            self._append(run_id, RunStartedEvent(thread_id=thread_id, run_id=run_id))
        self._notify(run_id)
        return True

    def mark_dispatched(self, run_id: str) -> None:
        with self.db:
            self.db.execute("UPDATE runs SET dispatched=1 WHERE run_id=?", (run_id,))

    def has_thread(self, thread_id: str, excluding_run: str) -> bool:
        return (
            self.db.execute(
                "SELECT 1 FROM runs WHERE thread_id=? AND dispatched=1 AND run_id<>? LIMIT 1",
                (thread_id, excluding_run),
            ).fetchone()
            is not None
        )

    def append(self, run_id: str, event: Any, *, terminal: bool = False) -> None:
        with self.db:
            written = self._append(run_id, event, terminal=terminal)
        if written:
            self._notify(run_id)

    def _append(self, run_id: str, event: Any, *, terminal: bool = False) -> bool:
        row = self.db.execute("SELECT thread_id, terminal FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            raise KeyError("unknown run")
        if row[1]:
            return False
        sequence = self.db.execute(
            "SELECT COALESCE(MAX(sequence),0)+1 FROM events WHERE run_id=?", (run_id,)
        ).fetchone()[0]
        envelope = {
            "runId": run_id,
            "threadId": row[0],
            "sequence": sequence,
            "eventId": f"{run_id}:{sequence}",
            "event": event.model_dump(mode="json", by_alias=True, exclude_none=True),
        }
        self.db.execute("INSERT INTO events VALUES (?,?,?)", (run_id, sequence, json.dumps(envelope)))
        if terminal:
            self.db.execute("UPDATE runs SET terminal=1 WHERE run_id=?", (run_id,))
        return True

    def abort(self, run_id: str, code: str, message: str) -> None:
        """从已提交日志恢复开放的事件，整个收口事务原子提交，可重复调用。"""
        row = self.db.execute("SELECT thread_id, terminal FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None or row[1]:
            return
        thread_id = row[0]
        persisted = [
            json.loads(payload)["event"]
            for (payload,) in self.db.execute("SELECT payload FROM events WHERE run_id=? ORDER BY sequence", (run_id,))
        ]
        closing = build_abort_events(persisted, thread_id=thread_id, run_id=run_id, code=code, message=message)
        with self.db:
            for index, event in enumerate(closing):
                self._append(run_id, event, terminal=(index == len(closing) - 1))
        self._notify(run_id)

    def replay(self, run_id: str, after: int = 0) -> list[dict[str, Any]]:
        if not self.contains(run_id):
            raise KeyError("unknown run")
        maximum = self.db.execute("SELECT COALESCE(MAX(sequence),0) FROM events WHERE run_id=?", (run_id,)).fetchone()[
            0
        ]
        if type(after) is not int or not 0 <= after <= maximum:
            raise ValueError("cursor must be an integer within the persisted event range")
        return [
            json.loads(row[0])
            for row in self.db.execute(
                "SELECT payload FROM events WHERE run_id=? AND sequence>? ORDER BY sequence LIMIT 256", (run_id, after)
            )
        ]

    def terminal(self, run_id: str) -> bool:
        row = self.db.execute("SELECT terminal FROM runs WHERE run_id=?", (run_id,)).fetchone()
        return bool(row and row[0])

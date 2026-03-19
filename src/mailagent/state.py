from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ThreadMessage:
    message_id: str
    from_addr: str
    date: str
    body_snippet: str


@dataclass
class ThreadContext:
    is_reply: bool
    is_reply_to_own: bool
    depth: int
    prior_messages: list[ThreadMessage] | None = None


class ThreadState:
    """JSON-backed tracker for outgoing Message-IDs per inbox."""

    def __init__(self, data_dir: str | Path, inbox_address: str) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.filepath = self.data_dir / _thread_filename(inbox_address)
        self._entries: dict[str, dict] = self._load()

    def record_sent(self, message_id: str, in_reply_to: str | None) -> None:
        depth = self.get_depth(in_reply_to or "")
        self._entries[message_id] = {
            "in_reply_to": in_reply_to or "",
            "depth": depth,
            "timestamp": time.time(),
        }
        self._save()

    def is_own(self, message_id: str) -> bool:
        return message_id in self._entries

    def get_depth(self, in_reply_to: str) -> int:
        if not in_reply_to or in_reply_to not in self._entries:
            return 0
        return self._entries[in_reply_to]["depth"] + 1

    def prune(self, max_age_days: int = 30) -> int:
        cutoff = time.time() - (max_age_days * 86400)
        before = len(self._entries)
        self._entries = {
            mid: entry
            for mid, entry in self._entries.items()
            if entry.get("timestamp", 0) > cutoff
        }
        if len(self._entries) < before:
            self._save()
        return before - len(self._entries)

    def _load(self) -> dict[str, dict]:
        if not self.filepath.exists():
            return {}
        try:
            data = json.loads(self.filepath.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load thread state %s: %s", self.filepath, exc)
        return {}

    def _save(self) -> None:
        self.filepath.write_text(
            json.dumps(self._entries, indent=2), encoding="utf-8"
        )


def _thread_filename(inbox_address: str) -> str:
    local, domain = inbox_address.split("@", 1)
    return f"threads_{local}_{domain}.json"


class InboxState:
    """File-backed idempotency tracker for a single inbox."""

    def __init__(self, data_dir: str | Path, inbox_address: str) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.filepath = self.data_dir / _state_filename(inbox_address)
        self._processed = self._load()

    def has(self, filename: str) -> bool:
        return filename in self._processed

    def add(self, filename: str) -> None:
        if filename in self._processed:
            return
        self._processed.add(filename)
        with self.filepath.open("a", encoding="utf-8") as handle:
            handle.write(filename + "\n")

    def prune(self, watch_path: str | Path, threshold: int = 1000) -> tuple[int, int]:
        if not self.filepath.exists():
            return (0, 0)

        entries = self.filepath.read_text(encoding="utf-8").splitlines()
        if len(entries) < threshold:
            return (len(entries), len(entries))

        existing = {path.name for path in Path(watch_path).iterdir() if path.is_file()}
        kept = [entry for entry in entries if entry in existing]
        self.filepath.write_text(
            ("\n".join(kept) + "\n") if kept else "", encoding="utf-8"
        )
        self._processed = set(kept)
        return (len(entries), len(kept))

    def _load(self) -> set[str]:
        if not self.filepath.exists():
            return set()
        return set(self.filepath.read_text(encoding="utf-8").splitlines())


def _state_filename(inbox_address: str) -> str:
    local, domain = inbox_address.split("@", 1)
    return f"processed_{local}_{domain}.txt"

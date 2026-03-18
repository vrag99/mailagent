from pathlib import Path


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

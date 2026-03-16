from dotenv import load_dotenv

load_dotenv()

import logging
import os
import time
from pathlib import Path

import inotify_simple

import classifier
import parser
import workflows

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

STATE_FILE = Path("/app/data/processed.txt")
DEBOUNCE_MS = 100
PRUNE_THRESHOLD = 1000


def _load_state() -> set[str]:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not STATE_FILE.exists():
        return set()
    return set(STATE_FILE.read_text().splitlines())


def _record_processed(filename: str) -> None:
    with STATE_FILE.open("a") as f:
        f.write(filename + "\n")


def _prune_state(watch_path: Path) -> None:
    if not STATE_FILE.exists():
        return
    entries = STATE_FILE.read_text().splitlines()
    if len(entries) < PRUNE_THRESHOLD:
        return
    existing = {p.name for p in watch_path.iterdir() if p.is_file()}
    kept = [e for e in entries if e in existing]
    STATE_FILE.write_text("\n".join(kept) + "\n" if kept else "")
    logger.info("Pruned state file: %d → %d entries", len(entries), len(kept))


def _process(filepath: str, config: workflows.Config, processed: set[str]) -> None:
    filename = Path(filepath).name

    if filename in processed:
        logger.debug("Already processed, skipping: %s", filename)
        return

    logger.info("Processing: %s", filepath)

    try:
        parsed = parser.parse(filepath)
    except Exception as exc:
        logger.error("Failed to parse %s: %s", filepath, exc)
        processed.add(filename)
        _record_processed(filename)
        return

    logger.info("Email from=%s subject=%r", parsed.from_email, parsed.subject)

    try:
        workflow_name = classifier.classify(parsed, config.workflows)
    except Exception as exc:
        logger.error("Classification error for %s: %s", filepath, exc)
        workflow_name = "fallback"

    logger.info("Classified as: %s", workflow_name)

    try:
        workflows.execute(workflow_name, parsed, config)
    except Exception as exc:
        logger.error("Workflow execution error for %s: %s", filepath, exc)

    processed.add(filename)
    _record_processed(filename)


def _watch_loop(watch_path: Path, config: workflows.Config) -> None:
    processed = _load_state()
    _prune_state(watch_path)

    if os.environ.get("CATCH_UP_ON_START", "true").lower() == "true":
        logger.info("Catch-up scan on %s", watch_path)
        for p in sorted(watch_path.iterdir()):
            if p.is_file():
                _process(str(p), config, processed)

    inotify = inotify_simple.INotify()
    flags = inotify_simple.flags.MOVED_TO | inotify_simple.flags.CREATE
    inotify.add_watch(str(watch_path), flags)
    logger.info("Watching %s", watch_path)

    while True:
        events = inotify.read(timeout=None)
        for event in events:
            if not event.name:
                continue
            time.sleep(DEBOUNCE_MS / 1000)
            filepath = watch_path / event.name
            if filepath.is_file():
                _process(str(filepath), config, processed)


def main() -> None:
    mail_domain = os.environ.get("MAIL_DOMAIN", "")
    mail_user = os.environ.get("MAIL_USER", "")
    if not mail_domain or not mail_user:
        logger.error("MAIL_DOMAIN and MAIL_USER must be set")
        raise SystemExit(1)
    watch_path = Path(f"/var/mail/{mail_domain}/{mail_user}/new")

    if not watch_path.exists():
        logger.error("Watch path does not exist: %s", watch_path)
        raise SystemExit(1)

    config = workflows.load_config("/app/config.yml")
    logger.info("Loaded %d workflows", len(config.workflows))

    while True:
        try:
            _watch_loop(watch_path, config)
        except Exception as exc:
            logger.exception("Watcher crashed: %s — restarting in 5s", exc)
            time.sleep(5)


if __name__ == "__main__":
    main()

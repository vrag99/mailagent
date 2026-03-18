from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .classifier import classify
from .config import Config, InboxConfig
from .parser import parse
from .providers import BaseProvider, get_provider
from .state import InboxState
from .workflows import execute

logger = logging.getLogger(__name__)


@dataclass
class InboxRuntime:
    inbox: InboxConfig
    watch_path: Path
    state: InboxState
    classify_provider: BaseProvider
    reply_provider: BaseProvider


def run(config: Config, stop_event: threading.Event | None = None) -> None:
    notifier, watch_flags = _create_notifier()
    wd_to_runtime: dict[int, InboxRuntime] = {}

    for inbox in config.inboxes:
        watch_path = maildir_new_path(inbox.address)
        if not watch_path.exists():
            logger.error("Maildir not found for %s: %s", inbox.address, watch_path)
            continue

        runtime = InboxRuntime(
            inbox=inbox,
            watch_path=watch_path,
            state=InboxState(config.settings.data_dir, inbox.address),
            classify_provider=build_provider(config, inbox.classify_provider),
            reply_provider=build_provider(config, inbox.reply_provider),
        )
        before, after = runtime.state.prune(watch_path)
        if before != after:
            logger.info(
                "Pruned state for %s: %d -> %d entries", inbox.address, before, after
            )

        wd = notifier.add_watch(str(watch_path), watch_flags)
        wd_to_runtime[wd] = runtime
        logger.info("Watching %s at %s", inbox.address, watch_path)

    if not wd_to_runtime:
        logger.error("No valid inbox watch paths were configured")
        return

    if config.settings.catch_up_on_start:
        for runtime in wd_to_runtime.values():
            catch_up(runtime, config)

    while True:
        if stop_event and stop_event.is_set():
            logger.info("Stop requested, exiting watcher loop")
            return

        events = notifier.read(timeout=1000)
        for event in events:
            runtime = wd_to_runtime.get(event.wd)
            if runtime is None:
                continue
            if not event.name:
                continue

            if config.settings.debounce_ms > 0:
                time.sleep(config.settings.debounce_ms / 1000)

            filepath = runtime.watch_path / event.name
            if filepath.is_file():
                process_email(filepath, runtime, config)


def catch_up(runtime: InboxRuntime, config: Config) -> None:
    logger.info("Catch-up scan for %s on %s", runtime.inbox.address, runtime.watch_path)
    for path in sorted(runtime.watch_path.iterdir()):
        if path.is_file():
            process_email(path, runtime, config)


def process_email(
    filepath: Path, runtime: InboxRuntime, config: Config
) -> dict[str, Any] | None:
    filename = filepath.name
    if runtime.state.has(filename):
        logger.debug("Already processed, skipping: %s", filename)
        return None

    logger.info("Processing %s for inbox %s", filepath, runtime.inbox.address)

    try:
        parsed = parse(filepath, truncate_at=config.settings.classify_body_limit)
    except Exception as exc:
        logger.error("Failed to parse %s: %s", filepath, exc)
        runtime.state.add(filename)
        return {"ok": False, "reason": "parse_failed", "error": str(exc)}

    logger.info("Email from=%s subject=%r", parsed.from_email, parsed.subject)

    try:
        classification = classify(
            email=parsed,
            workflows=runtime.inbox.workflows,
            provider=runtime.classify_provider,
            system_prompt=runtime.inbox.system_prompt
            or "You are a helpful email assistant.",
        )
        workflow_name = classification.workflow_name
        logger.info(
            "Classified for inbox %s as workflow=%s method=%s",
            runtime.inbox.address,
            classification.workflow_name,
            classification.method,
        )
    except Exception as exc:
        logger.error("Classification failed for %s: %s", filepath, exc)
        workflow_name = "fallback"

    try:
        result = execute(
            workflow_name=workflow_name,
            parsed_email=parsed,
            inbox=runtime.inbox,
            config=config,
            reply_provider=runtime.reply_provider,
            dry_run=False,
        )
    except Exception as exc:
        logger.error("Workflow execution failed for %s: %s", filepath, exc)
        result = {"ok": False, "reason": "workflow_execution_failed", "error": str(exc)}

    runtime.state.add(filename)
    return result


def build_provider(config: Config, provider_name: str) -> BaseProvider:
    provider_cfg = config.providers[provider_name]
    kwargs: dict[str, Any] = {
        "model": provider_cfg.model,
        "api_key": provider_cfg.api_key,
        "base_url": provider_cfg.base_url,
        "timeout": provider_cfg.timeout,
        "retries": provider_cfg.retries,
    }

    if provider_cfg.type == "openrouter":
        kwargs["http_referer"] = provider_cfg.http_referer
        kwargs["x_title"] = provider_cfg.x_title

    return get_provider(provider_cfg.type, **kwargs)


def maildir_new_path(address: str) -> Path:
    local, domain = address.split("@", 1)
    return Path(f"/var/mail/{domain}/{local}/new")


def _create_notifier() -> tuple[Any, Any]:
    try:
        import inotify_simple
    except ImportError as exc:
        raise RuntimeError(
            "inotify_simple is required for 'mailagent run' and is only available on Linux"
        ) from exc

    notifier = inotify_simple.INotify()
    flags = inotify_simple.flags.MOVED_TO | inotify_simple.flags.CREATE
    return notifier, flags

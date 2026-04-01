from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .classifier import classify
from ..config import Config, ConfigError, InboxConfig, load_config
from .parser import parse
from ..providers import BaseProvider, get_provider
from .state import InboxState, ThreadContext, ThreadState
from .workflows import execute

RELOAD_CHECK_INTERVAL = 5  # seconds between config mtime checks

logger = logging.getLogger(__name__)


@dataclass
class InboxRuntime:
    inbox: InboxConfig
    watch_path: Path
    state: InboxState
    thread_state: ThreadState
    classify_provider: BaseProvider
    reply_provider: BaseProvider


def run(
    config: Config,
    stop_event: threading.Event | None = None,
    config_path: str | Path | None = None,
) -> None:
    notifier, watch_flags = _create_notifier()
    wd_to_runtime: dict[int, InboxRuntime] = {}
    addr_to_wd: dict[str, int] = {}

    for inbox in config.inboxes:
        wd = _setup_inbox_watch(inbox, config, notifier, watch_flags, wd_to_runtime)
        if wd is not None:
            addr_to_wd[inbox.address] = wd

    if not wd_to_runtime:
        logger.warning("No inbox watch paths are active; daemon is idle")

    if config.settings.catch_up_on_start:
        for runtime in wd_to_runtime.values():
            catch_up(runtime, config)

    # Config hot-reload state
    last_mtime: float = 0.0
    last_reload_check: float = 0.0
    if config_path:
        config_path = Path(config_path)
        try:
            last_mtime = os.stat(config_path).st_mtime
        except OSError:
            pass

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

        # Periodically check for config changes
        if config_path:
            now = time.monotonic()
            if now - last_reload_check >= RELOAD_CHECK_INTERVAL:
                last_reload_check = now
                config, last_mtime = _maybe_reload_config(
                    config_path,
                    last_mtime,
                    config,
                    notifier,
                    watch_flags,
                    wd_to_runtime,
                    addr_to_wd,
                )


def _setup_inbox_watch(
    inbox: InboxConfig,
    config: Config,
    notifier: Any,
    watch_flags: Any,
    wd_to_runtime: dict[int, InboxRuntime],
) -> int | None:
    """Set up an inotify watch for a single inbox. Returns the watch descriptor or None."""
    watch_path = maildir_new_path(inbox.address)
    if not watch_path.exists():
        logger.warning(
            "Maildir not found for %s: %s — skipping (no email has arrived yet?)",
            inbox.address,
            watch_path,
        )
        return None

    thread_state = ThreadState(config.settings.data_dir, inbox.address)
    thread_state.prune()

    runtime = InboxRuntime(
        inbox=inbox,
        watch_path=watch_path,
        state=InboxState(config.settings.data_dir, inbox.address),
        thread_state=thread_state,
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
    return wd


def _maybe_reload_config(
    config_path: Path,
    last_mtime: float,
    config: Config,
    notifier: Any,
    watch_flags: Any,
    wd_to_runtime: dict[int, InboxRuntime],
    addr_to_wd: dict[str, int],
) -> tuple[Config, float]:
    """Check if config file changed and reload if so. Returns (config, mtime)."""
    try:
        current_mtime = os.stat(config_path).st_mtime
    except OSError:
        return config, last_mtime

    if current_mtime <= last_mtime:
        return config, last_mtime

    logger.info("Config file changed, reloading...")
    try:
        load_result = load_config(config_path)
    except ConfigError as exc:
        logger.warning("Config reload failed, keeping current config: %s", exc)
        return config, current_mtime

    new_config = load_result.config
    for warning in load_result.warnings:
        logger.warning(warning)

    old_addrs = {inbox.address for inbox in config.inboxes}
    new_addrs = {inbox.address for inbox in new_config.inboxes}

    # Remove watches for deleted inboxes
    for removed in old_addrs - new_addrs:
        wd = addr_to_wd.pop(removed, None)
        if wd is not None:
            try:
                import inotify_simple
                notifier.rm_watch(wd)
            except Exception:
                pass
            wd_to_runtime.pop(wd, None)
            logger.info("Removed watch for deleted inbox: %s", removed)

    # Add watches for new inboxes
    for added in new_addrs - old_addrs:
        inbox = next(i for i in new_config.inboxes if i.address == added)
        wd = _setup_inbox_watch(inbox, new_config, notifier, watch_flags, wd_to_runtime)
        if wd is not None:
            addr_to_wd[added] = wd

    # Update existing inboxes (rebuild providers if config changed)
    for addr in old_addrs & new_addrs:
        wd = addr_to_wd.get(addr)
        if wd is None:
            continue
        runtime = wd_to_runtime.get(wd)
        if runtime is None:
            continue
        new_inbox = next(i for i in new_config.inboxes if i.address == addr)
        runtime.inbox = new_inbox
        runtime.classify_provider = build_provider(new_config, new_inbox.classify_provider)
        runtime.reply_provider = build_provider(new_config, new_inbox.reply_provider)

    logger.info("Config reloaded successfully")
    return new_config, current_mtime


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

    thread_ctx = ThreadContext(
        is_reply=bool(parsed.in_reply_to),
        is_reply_to_own=runtime.thread_state.is_own(parsed.in_reply_to or ""),
        depth=runtime.thread_state.get_depth(parsed.in_reply_to or ""),
    )

    try:
        classification = classify(
            email=parsed,
            workflows=runtime.inbox.workflows,
            provider=runtime.classify_provider,
            system_prompt=runtime.inbox.system_prompt
            or "You are a helpful email assistant.",
            thread_ctx=thread_ctx,
        )
        workflow_name = classification.workflow_name
        conf_str = f" confidence={classification.confidence}" if classification.confidence is not None else ""
        logger.info(
            "Classified for inbox %s as workflow=%s method=%s%s",
            runtime.inbox.address,
            classification.workflow_name,
            classification.method,
            conf_str,
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
            thread_ctx=thread_ctx,
            thread_state=runtime.thread_state,
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

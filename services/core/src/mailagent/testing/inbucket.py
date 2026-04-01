"""Inbucket container management and REST API client for live tests."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SMTP_PORT = 2500
IMAP_PORT = 1100
WEB_PORT = 9000


def start_inbucket(data_dir: str | None = None) -> tuple[Any, dict[str, int]]:
    """Start an Inbucket Docker container. Returns (container, ports_dict).

    Requires the ``docker`` package (``pip install mailagent[test]``).
    """
    try:
        import docker
    except ImportError as exc:
        raise RuntimeError(
            "The 'docker' package is required for live tests. "
            "Install it with: pip install mailagent[test]"
        ) from exc

    client = docker.from_env()
    volumes = {}
    env = {"INBUCKET_STORAGE_TYPE": "memory"}
    if data_dir:
        volumes[data_dir] = {"bind": "/storage", "mode": "rw"}
        env["INBUCKET_STORAGE_TYPE"] = "file"
        env["INBUCKET_STORAGE_PARAMS"] = "/storage"

    container = client.containers.run(
        "inbucket/inbucket",
        detach=True,
        name="mailagent-test-inbucket",
        ports={
            f"{SMTP_PORT}/tcp": SMTP_PORT,
            f"{IMAP_PORT}/tcp": IMAP_PORT,
            f"{WEB_PORT}/tcp": WEB_PORT,
        },
        volumes=volumes or None,
        environment=env,
        remove=True,
    )

    ports = {"smtp": SMTP_PORT, "imap": IMAP_PORT, "web": WEB_PORT}
    _wait_for_ready(f"http://127.0.0.1:{WEB_PORT}")
    logger.info("Inbucket started (SMTP:%d, Web:%d)", SMTP_PORT, WEB_PORT)
    return container, ports


def stop_inbucket(container: Any) -> None:
    try:
        container.stop(timeout=5)
    except Exception:
        logger.debug("Inbucket container already stopped")


def _wait_for_ready(base_url: str, timeout: float = 30) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = httpx.get(f"{base_url}/api/v1/mailbox/healthcheck", timeout=2)
            if resp.status_code < 500:
                return
        except (httpx.ConnectError, httpx.TimeoutException):
            pass
        time.sleep(0.5)
    raise TimeoutError(f"Inbucket not ready at {base_url} after {timeout}s")


# ── REST API client ──────────────────────────────────────────────


def get_messages(mailbox: str, base_url: str = "http://127.0.0.1:9000") -> list[dict[str, Any]]:
    resp = httpx.get(f"{base_url}/api/v1/mailbox/{mailbox}", timeout=5)
    resp.raise_for_status()
    return resp.json()


def get_message_source(
    mailbox: str, message_id: str, base_url: str = "http://127.0.0.1:9000"
) -> str:
    resp = httpx.get(f"{base_url}/api/v1/mailbox/{mailbox}/{message_id}/source", timeout=5)
    resp.raise_for_status()
    return resp.text


def purge_mailbox(mailbox: str, base_url: str = "http://127.0.0.1:9000") -> None:
    resp = httpx.delete(f"{base_url}/api/v1/mailbox/{mailbox}", timeout=5)
    resp.raise_for_status()


def wait_for_messages(
    mailbox: str,
    expected_count: int = 1,
    base_url: str = "http://127.0.0.1:9000",
    timeout: float = 30,
    interval: float = 0.5,
) -> list[dict[str, Any]]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        messages = get_messages(mailbox, base_url)
        if len(messages) >= expected_count:
            return messages
        time.sleep(interval)
    return get_messages(mailbox, base_url)

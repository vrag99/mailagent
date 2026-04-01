"""Lightweight HTTP server that captures webhook POSTs for test assertions."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


@dataclass
class CapturedRequest:
    path: str
    headers: dict[str, str]
    body: Any


class _Handler(BaseHTTPRequestHandler):
    captured: list[CapturedRequest]

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(content_length) if content_length else b""
        try:
            body = json.loads(raw) if raw else None
        except (json.JSONDecodeError, ValueError):
            body = raw.decode("utf-8", errors="replace")

        self.server.captured.append(  # type: ignore[attr-defined]
            CapturedRequest(
                path=self.path,
                headers=dict(self.headers),
                body=body,
            )
        )
        self.send_response(200)
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        pass  # silence request logs


class WebhookCaptureServer:
    """Start a local HTTP server on a random port to capture webhook calls."""

    def __init__(self) -> None:
        self._server = HTTPServer(("127.0.0.1", 0), _Handler)
        self._server.captured = []  # type: ignore[attr-defined]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def captured(self) -> list[CapturedRequest]:
        return self._server.captured  # type: ignore[attr-defined]

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()

    def clear(self) -> None:
        self._server.captured.clear()  # type: ignore[attr-defined]

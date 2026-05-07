#!/usr/bin/env python3
"""Tiny OpenRouter-compatible mock server for Playwright E2E tests.

The backend talks to OpenRouter via the OpenAI-compatible chat/completions
endpoint. This mock keeps E2E deterministic and avoids any external network
call or secret requirement.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

HOST = os.environ.get("MOCK_OPENROUTER_HOST", "127.0.0.1")
PORT = int(os.environ.get("MOCK_OPENROUTER_PORT", "8899"))
MODEL_NAME = os.environ.get("MOCK_OPENROUTER_MODEL", "mock-narrator")


class MockOpenRouterHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def _send_json(self, status_code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            decoded = {}
        return decoded if isinstance(decoded, dict) else {}

    def do_GET(self) -> None:  # noqa: N802
        if self.path in {"/health", "/api/v1/models", "/v1/models"}:
            if self.path.endswith("/models"):
                self._send_json(
                    200,
                    {
                        "object": "list",
                        "data": [
                            {
                                "id": MODEL_NAME,
                                "object": "model",
                                "owned_by": "mnesos",
                            }
                        ],
                    },
                )
                return

            self._send_json(200, {"status": "ok"})
            return

        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path not in {"/api/v1/chat/completions", "/v1/chat/completions", "/chat/completions"}:
            self._send_json(404, {"error": "not found"})
            return

        request_payload = self._read_json_body()
        messages = request_payload.get("messages", [])
        last_user_message = ""
        for message in reversed(messages):
            if isinstance(message, dict) and message.get("role") == "user":
                last_user_message = str(message.get("content", ""))
                break

        assistant_text = (
            "Mock narrator: the OpenRouter call was intercepted locally. "
            f"You said: {last_user_message or 'nothing yet'}."
        )
        self._send_json(
            200,
            {
                "id": "chatcmpl-mock",
                "object": "chat.completion",
                "created": 0,
                "model": request_payload.get("model", MODEL_NAME),
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": assistant_text,
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 16,
                    "total_tokens": 28,
                },
            },
        )


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), MockOpenRouterHandler)
    print(f"Mock OpenRouter listening on http://{HOST}:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()

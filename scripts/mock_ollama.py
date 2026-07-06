#!/usr/bin/env python3
"""Tiny Ollama-shaped server used only by smoke and browser tests.

It makes end-to-end behavior deterministic without downloading a model. It is
never imported by the production application.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/tags":
            self._json(200, {"models": [{"name": "llama3.2:1b"}]})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/chat":
            self._json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        request = json.loads(self.rfile.read(length) or b"{}")
        proactive = any(
            "Autonomous check-in" in message.get("content", "")
            for message in request.get("messages", [])
        )
        content = (
            "Mock initiative: The rain started. It made me wonder how your work is going."
            if proactive
            else "Mock reply: I heard you. What are we making tonight?"
        )
        self._json(
            200,
            {
                "message": {"role": "assistant", "content": content},
                "prompt_eval_count": 42,
                "eval_count": 18,
            },
        )

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 11434), Handler).serve_forever()


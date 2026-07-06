#!/usr/bin/env python3
"""Fast API smoke test for an already-running Kindred server."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request


BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8000"


def request(path: str, method: str = "GET", body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    with urllib.request.urlopen(
        urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method),
        timeout=10,
    ) as response:
        return response.status, json.loads(response.read() or b"null")


def main() -> int:
    try:
        status, health = request("/api/health")
        assert status == 200 and health["status"] == "ok"
        _, characters = request("/api/characters")
        assert characters, "No seed characters were found"
        _, thread = request(
            "/api/threads",
            "POST",
            {"character_id": characters[0]["id"], "title": "Smoke test"},
        )
        _, messages = request(f"/api/threads/{thread['id']}/messages")
        assert messages == []
        print(
            f"Kindred smoke test passed: API {health['version']}, "
            f"{len(characters)} character(s), SQLite and thread creation healthy."
        )
        return 0
    except (AssertionError, KeyError, urllib.error.URLError) as exc:
        print(f"Kindred smoke test failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


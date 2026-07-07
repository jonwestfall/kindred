#!/usr/bin/env python3
"""Exercise Kindred's notification delivery path against a running server.

The script is intentionally dependency-free so it can run on a Mac, Raspberry
Pi, or a shell on the Docker host. It verifies the API-side pieces that are
easy to miss before testing the visible banner on a phone:

- authentication succeeds;
- VAPID/Web Push is configured;
- this signed-in account has at least one saved browser subscription;
- a logged character-message test event can be published;
- optionally, a forced daemon run can publish a real autonomous message.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


TOKEN = ""


def request(base: str, path: str, method: str = "GET", body: dict[str, Any] | None = None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    with urllib.request.urlopen(
        urllib.request.Request(f"{base}{path}", data=data, headers=headers, method=method),
        timeout=20,
    ) as response:
        raw = response.read()
        return response.status, json.loads(raw or b"null")


def login(base: str, username: str, password: str) -> None:
    global TOKEN
    if os.getenv("KINDRED_API_TOKEN"):
        TOKEN = os.environ["KINDRED_API_TOKEN"]
        return
    _, session = request(
        base,
        "/api/auth/login",
        "POST",
        {"username": username, "password": password},
    )
    TOKEN = session["token"]


def choose_character(base: str, character_id: int | None) -> int:
    if character_id is not None:
        return character_id
    _, characters = request(base, "/api/characters")
    if not characters:
        raise AssertionError("No characters are available to this account.")
    return int(characters[0]["id"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url", help="Kindred origin, for example https://host.ts.net")
    parser.add_argument("--character-id", type=int, help="Character ID to send the test from")
    parser.add_argument("--content", default="Kindred API notification test.")
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Also force /api/daemon/run-once for the character. Requires admin.",
    )
    parser.add_argument(
        "--allow-no-subscription",
        action="store_true",
        help="Do not fail when the account has no saved Web Push subscription.",
    )
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    username = os.getenv("KINDRED_ADMIN_USERNAME", "admin")
    password = os.getenv("KINDRED_ADMIN_PASSWORD", "change-me-now")

    try:
        login(base, username, password)
        _, health = request(base, "/api/health")
        _, key = request(base, "/api/notifications/public-key")
        character_id = choose_character(base, args.character_id)
        _, result = request(
            base,
            "/api/notifications/test",
            "POST",
            {"character_id": character_id, "content": args.content},
        )

        print(f"Kindred {health['version']} at {base}")
        print(f"Notification test message: #{result['message']['id']} in thread #{result['thread_id']}")
        print(f"Web Push configured: {result['web_push_configured']}")
        print(f"Saved subscriptions for this account: {result['subscription_count']}")

        failures: list[str] = []
        if not key.get("web_push_configured") or not result.get("web_push_configured"):
            failures.append("VAPID/Web Push is not configured on the server.")
        if result.get("subscription_count", 0) < 1 and not args.allow_no_subscription:
            failures.append("No saved subscription exists for this account. Open Kindred on the phone and tap the bell.")

        if args.daemon:
            path = f"/api/daemon/run-once?{urllib.parse.urlencode({'character_id': character_id})}"
            _, daemon = request(base, path, "POST")
            first = daemon[0] if daemon else {}
            print(f"Forced daemon result: {first.get('note', 'no result')}")
            if not first.get("initiate") or first.get("message_count", 0) < 1:
                failures.append("Forced daemon run did not create a message.")

        if failures:
            for failure in failures:
                print(f"FAIL: {failure}", file=sys.stderr)
            return 1
        print("Notification API test passed. Now confirm the banner appeared on the subscribed device.")
        return 0
    except (AssertionError, KeyError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"Notification API test failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

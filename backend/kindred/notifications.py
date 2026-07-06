"""WebSocket live events and optional standards-based Web Push delivery."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket

from .config import Settings
from .database import Database


@dataclass(slots=True)
class NotificationService:
    """Fan out new messages to open clients and saved push subscriptions."""

    settings: Settings
    database: Database
    sockets: set[WebSocket] = field(default_factory=set)

    async def connect(self, socket: WebSocket) -> None:
        await socket.accept()
        self.sockets.add(socket)

    def disconnect(self, socket: WebSocket) -> None:
        self.sockets.discard(socket)

    async def publish(self, event: dict[str, Any]) -> None:
        """Broadcast immediately, then attempt Web Push without blocking chat."""

        stale: list[WebSocket] = []
        for socket in list(self.sockets):
            try:
                await socket.send_json(event)
            except Exception:
                stale.append(socket)
        for socket in stale:
            self.disconnect(socket)
        if event.get("type") == "character_message":
            await asyncio.to_thread(self._send_web_push, event)

    def _send_web_push(self, event: dict[str, Any]) -> None:
        if not self.database.get_settings().get("notifications", {}).get("enabled", True):
            return
        if not self.settings.vapid_private_key or not self.settings.vapid_public_key:
            return
        try:
            from pywebpush import WebPushException, webpush
        except ImportError:
            return
        payload = json.dumps(
            {
                "title": event.get("character_name", "Kindred"),
                "body": event.get("content", "A character sent a message."),
                "url": f"/?thread={event.get('thread_id', '')}",
            }
        )
        for subscription in self.database.list_subscriptions():
            try:
                webpush(
                    subscription_info=subscription,
                    data=payload,
                    vapid_private_key=self.settings.vapid_private_key,
                    vapid_claims={"sub": self.settings.vapid_subject},
                )
            except WebPushException as exc:
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status in {404, 410}:
                    self.database.delete_subscription(subscription.get("endpoint", ""))

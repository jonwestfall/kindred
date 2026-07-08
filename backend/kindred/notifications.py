"""WebSocket live events and optional standards-based Web Push delivery."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket

from .auth import Principal
from .config import Settings
from .database import Database

_MISSING = object()

@dataclass(slots=True)
class NotificationService:
    """Fan out new messages to open clients and saved push subscriptions."""

    settings: Settings
    database: Database
    sockets: dict[WebSocket, Principal] = field(default_factory=dict)

    async def connect(self, socket: WebSocket, principal: Principal) -> None:
        await socket.accept()
        self.sockets[socket] = principal

    def disconnect(self, socket: WebSocket) -> None:
        self.sockets.pop(socket, None)

    async def publish(self, event: dict[str, Any]) -> None:
        """Broadcast immediately, then attempt Web Push without blocking chat."""

        stale: list[WebSocket] = []
        target_user_id = event.get("user_id", _MISSING)
        for socket, principal in list(self.sockets.items()):
            if target_user_id is not _MISSING and not (
                principal.is_admin or principal.user_id == target_user_id
            ):
                continue
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
        message = event.get("message") if isinstance(event.get("message"), dict) else {}
        thread_id = event.get("thread_id", "")
        message_id = message.get("id") or event.get("message_id") or ""
        payload = json.dumps(
            {
                "title": event.get("character_name", "Kindred"),
                "body": event.get("content", "A character sent a message."),
                "url": f"/?thread={thread_id}",
                "thread_id": thread_id,
                "message_id": message_id,
                "tag": f"kindred-message-{message_id}" if message_id else f"kindred-thread-{thread_id}",
            }
        )
        target_user_id = event.get("user_id", _MISSING)
        subscriptions = (
            self.database.list_subscriptions(target_user_id)
            if target_user_id is not _MISSING
            else self.database.list_subscriptions()
        )
        for subscription in subscriptions:
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

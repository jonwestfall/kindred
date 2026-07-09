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


def _maybe_int(value: Any) -> int | None:
    """Best-effort conversion for optional event identifiers."""

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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
        target_user_id = event.get("user_id", _MISSING)
        message = event.get("message") if isinstance(event.get("message"), dict) else {}
        thread_id = event.get("thread_id", "")
        message_id = message.get("id") or event.get("message_id") or ""
        context = {
            "user_id": None if target_user_id is _MISSING else _maybe_int(target_user_id),
            "thread_id": _maybe_int(thread_id),
            "message_id": _maybe_int(message_id),
            "character_id": _maybe_int(event.get("character_id")),
        }

        if not self.database.get_settings().get("notifications", {}).get("enabled", True):
            self.database.log_notification_delivery(
                channel="web_push",
                status="skipped",
                detail="Notifications are disabled in Kindred settings.",
                **context,
            )
            return
        if not self.settings.vapid_private_key or not self.settings.vapid_public_key:
            self.database.log_notification_delivery(
                channel="web_push",
                status="skipped",
                detail="VAPID keys are not configured; Web Push was not attempted.",
                **context,
            )
            return
        try:
            from pywebpush import WebPushException, webpush
        except ImportError:
            self.database.log_notification_delivery(
                channel="web_push",
                status="skipped",
                detail="pywebpush is not installed; Web Push was not attempted.",
                **context,
            )
            return
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
        subscriptions = (
            self.database.list_subscription_records(target_user_id, include_subscription=True)
            if target_user_id is not _MISSING
            else self.database.list_subscription_records(include_subscription=True)
        )
        if not subscriptions:
            self.database.log_notification_delivery(
                channel="web_push",
                status="skipped",
                detail="No saved push subscriptions matched this message.",
                **context,
            )
            return
        for record in subscriptions:
            subscription = record["subscription"]
            endpoint = str(record.get("endpoint") or subscription.get("endpoint") or "")
            row_context = {
                **context,
                "user_id": _maybe_int(record.get("user_id")),
                "endpoint": endpoint,
            }
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
                    self.database.delete_subscription(endpoint)
                    self.database.log_notification_delivery(
                        channel="web_push",
                        status="expired",
                        detail=f"Push endpoint returned {status}; subscription was removed.",
                        **row_context,
                    )
                else:
                    detail = (
                        f"Push endpoint failed with HTTP {status}."
                        if status
                        else "Push endpoint failed."
                    )
                    self.database.log_notification_delivery(
                        channel="web_push",
                        status="failed",
                        detail=detail,
                        **row_context,
                    )
            except Exception as exc:
                self.database.log_notification_delivery(
                    channel="web_push",
                    status="failed",
                    detail=f"Unexpected Web Push error: {type(exc).__name__}.",
                    **row_context,
                )
            else:
                self.database.log_notification_delivery(
                    channel="web_push",
                    status="sent",
                    detail="Web Push request accepted by the browser push service.",
                    **row_context,
                )

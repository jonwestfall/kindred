"""Autonomous character scheduling with explicit anti-spam controls."""

from __future__ import annotations

import asyncio
import math
import random
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any, Callable
from zoneinfo import ZoneInfo

from .config import Settings
from .database import Database
from .llm import BackendUnavailable, LLMService
from .notifications import NotificationService


@dataclass(frozen=True, slots=True)
class Decision:
    """A testable explanation of one autonomous scheduling decision."""

    initiate: bool
    note: str


def _parse_clock(value: str) -> time:
    hour, minute = (int(part) for part in value.split(":", 1))
    return time(hour=hour, minute=minute)


def in_quiet_hours(now: datetime, start_value: str, end_value: str) -> bool:
    """Support both same-day and overnight quiet-hour windows."""

    current = now.timetz().replace(tzinfo=None)
    start = _parse_clock(start_value)
    end = _parse_clock(end_value)
    if start == end:
        return False
    if start < end:
        return start <= current < end
    return current >= start or current < end


def should_initiate(
    *,
    character: dict[str, Any],
    daemon_settings: dict[str, Any],
    now: datetime,
    last_message_at: datetime | None,
    last_checked_at: datetime | None,
    initiated_last_hour: int,
    initiated_last_day: int,
    random_value: Callable[[], float] = random.random,
) -> Decision:
    """Decide whether to initiate, without I/O or hidden mutable state."""

    if not daemon_settings.get("enabled", True):
        return Decision(False, "Daemon disabled")
    frequency = float(character.get("initiative_frequency", 0))
    if frequency <= 0:
        return Decision(False, "Character initiative disabled")
    if in_quiet_hours(
        now,
        daemon_settings.get("quiet_hours_start", "22:00"),
        daemon_settings.get("quiet_hours_end", "08:00"),
    ):
        return Decision(False, "Inside quiet hours")
    cooldown = timedelta(minutes=int(character.get("cooldown_minutes", 240)))
    if last_message_at and now - last_message_at < cooldown:
        return Decision(False, "Character cooldown active")
    if initiated_last_hour >= int(daemon_settings.get("global_messages_per_hour", 4)):
        return Decision(False, "Global hourly autonomous limit reached")
    if initiated_last_day >= int(daemon_settings.get("global_messages_per_day", 12)):
        return Decision(False, "Global daily autonomous limit reached")
    elapsed = now - (last_checked_at or now - timedelta(minutes=1))
    elapsed_days = max(elapsed.total_seconds(), 1) / 86400
    probability = 1 - math.exp(-frequency * elapsed_days)
    if random_value() < probability:
        return Decision(True, f"Random schedule selected this check (p={probability:.4f})")
    return Decision(False, f"Random schedule deferred this check (p={probability:.4f})")


class CharacterDaemon:
    """Periodic autonomous message service owned by the FastAPI lifespan."""

    def __init__(
        self,
        settings: Settings,
        database: Database,
        llm: LLMService,
        notifications: NotificationService,
    ):
        self.settings = settings
        self.database = database
        self.llm = llm
        self.notifications = notifications
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        """Start one loop per process when enabled by the environment."""

        if self.settings.daemon_enabled and self._task is None:
            self._task = asyncio.create_task(self._loop(), name="kindred-character-daemon")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self.settings.daemon_interval_seconds)
            await self.run_once()

    async def run_once(self, *, force_character_id: int | None = None) -> list[dict[str, Any]]:
        """Evaluate all characters or force one character for manual testing."""

        now = datetime.now(ZoneInfo(self.settings.timezone))
        daemon_settings = self.database.get_settings().get("daemon", {})
        results: list[dict[str, Any]] = []
        for character in self.database.list_characters():
            if force_character_id is not None and character["id"] != force_character_id:
                continue
            state = self.database.get_daemon_state(character["id"])
            last_checked = (
                datetime.fromisoformat(state["last_checked_at"]).astimezone(now.tzinfo)
                if state.get("last_checked_at")
                else None
            )
            last_message = self.database.latest_message_time(character["id"])
            if last_message:
                last_message = last_message.astimezone(now.tzinfo)
            decision = (
                Decision(True, "Forced manual daemon check")
                if force_character_id is not None
                else should_initiate(
                    character=character,
                    daemon_settings=daemon_settings,
                    now=now,
                    last_message_at=last_message,
                    last_checked_at=last_checked,
                    initiated_last_hour=self.database.count_initiated_since(now - timedelta(hours=1)),
                    initiated_last_day=self.database.count_initiated_since(now - timedelta(days=1)),
                )
            )
            result = {"character_id": character["id"], "initiate": decision.initiate, "note": decision.note}
            if decision.initiate:
                messages: list[dict[str, Any]] = []
                try:
                    for user_id in self.database.daemon_recipient_user_ids(character["id"]):
                        thread = self.database.get_or_create_thread(character["id"], user_id=user_id)
                        history = self.database.list_messages(thread["id"], limit=40)
                        generated, context_summary, rationale = await self.llm.respond(
                            character, history, proactive=True
                        )
                        message = self.database.add_message(
                            thread["id"],
                            character["id"],
                            "character",
                            generated.content,
                            backend=generated.backend,
                            model=generated.model,
                            prompt_context_summary=context_summary,
                            character_rationale=rationale,
                            initiated=True,
                            user_id=user_id,
                        )
                        await self.notifications.publish(
                            {
                                "type": "character_message",
                                "message": message,
                                "user_id": user_id,
                                "thread_id": thread["id"],
                                "character_id": character["id"],
                                "character_name": character["name"],
                                "content": generated.content,
                            }
                        )
                        messages.append(message)
                    self.database.set_daemon_state(
                        character["id"], checked_at=now, initiated_at=now, note=decision.note
                    )
                    result["messages"] = messages
                    result["message_count"] = len(messages)
                except BackendUnavailable as exc:
                    result["initiate"] = False
                    result["note"] = f"{decision.note}; generation skipped: {exc}"
                    self.database.set_daemon_state(
                        character["id"], checked_at=now, initiated_at=None, note=result["note"]
                    )
            else:
                self.database.set_daemon_state(
                    character["id"], checked_at=now, initiated_at=None, note=decision.note
                )
            results.append(result)
        return results

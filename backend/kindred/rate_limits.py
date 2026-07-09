"""Cloud request budgets and cost-protection checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .database import Database


class LimitExceeded(RuntimeError):
    """Raised before a cloud call when a configured budget is exhausted."""


@dataclass(slots=True)
class RateLimiter:
    """Evaluate request, token, spend, and image budgets from usage logs."""

    database: Database

    def _check_windows(
        self,
        *,
        settings: dict,
        hourly: dict[str, float],
        daily: dict[str, float],
        image_daily: dict[str, float] | None = None,
        estimated_tokens: int,
        estimated_cost_usd: float,
        request_kind: str,
    ) -> None:
        """Raise when the supplied usage windows cannot fit a new request."""

        if hourly["requests"] >= float(settings.get("requests_per_hour", 20)):
            raise LimitExceeded("Cloud requests-per-hour limit reached")
        if daily["requests"] >= float(settings.get("requests_per_day", 100)):
            raise LimitExceeded("Cloud requests-per-day limit reached")
        if daily["tokens"] + estimated_tokens > float(settings.get("tokens_per_day", 50000)):
            raise LimitExceeded("Cloud tokens-per-day limit would be exceeded")
        if daily["cost"] + estimated_cost_usd > float(
            settings.get("cloud_spend_ceiling_usd", 2.0)
        ):
            raise LimitExceeded("Cloud spend ceiling would be exceeded")
        if request_kind == "image" and image_daily is not None:
            if image_daily["requests"] >= float(settings.get("image_generations_per_day", 2)):
                raise LimitExceeded("Image-generations-per-day limit reached")

    def check_cloud(
        self,
        estimated_tokens: int,
        *,
        estimated_cost_usd: float = 0,
        request_kind: str = "chat",
    ) -> None:
        settings = self.database.get_settings().get("limits", {})
        now = datetime.now(UTC)
        hourly = self.database.usage_since(now - timedelta(hours=1))
        daily = self.database.usage_since(now - timedelta(days=1))
        image_daily = (
            self.database.usage_since(now - timedelta(days=1), request_kind="image")
            if request_kind == "image"
            else None
        )
        self._check_windows(
            settings=settings,
            hourly=hourly,
            daily=daily,
            image_daily=image_daily,
            estimated_tokens=estimated_tokens,
            estimated_cost_usd=estimated_cost_usd,
            request_kind=request_kind,
        )

    def reserve_cloud(
        self,
        *,
        provider: str,
        model: str,
        request_kind: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        estimated_cost_usd: float = 0,
        dry_run: bool = False,
        character_id: int | None = None,
    ) -> int:
        """Atomically check budget and insert a conservative usage reservation."""

        settings = self.database.get_settings().get("limits", {})
        now = datetime.now(UTC)
        with self.database.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            hourly = self.database.usage_since(now - timedelta(hours=1), connection=connection)
            daily = self.database.usage_since(now - timedelta(days=1), connection=connection)
            image_daily = (
                self.database.usage_since(
                    now - timedelta(days=1),
                    request_kind="image",
                    connection=connection,
                )
                if request_kind == "image"
                else None
            )
            self._check_windows(
                settings=settings,
                hourly=hourly,
                daily=daily,
                image_daily=image_daily,
                estimated_tokens=input_tokens + output_tokens,
                estimated_cost_usd=estimated_cost_usd,
                request_kind=request_kind,
            )
            cursor = connection.execute(
                """INSERT INTO usage_logs(
                    timestamp, provider, model, request_kind, input_tokens, output_tokens,
                    estimated_cost_usd, dry_run, character_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    now.isoformat(),
                    provider,
                    model,
                    request_kind,
                    input_tokens,
                    output_tokens,
                    estimated_cost_usd,
                    int(dry_run),
                    character_id,
                ),
            )
            return int(cursor.lastrowid)

    def summary(self) -> dict[str, object]:
        """Return current window usage alongside configured limits."""

        now = datetime.now(UTC)
        return {
            "hour": self.database.usage_since(now - timedelta(hours=1)),
            "day": self.database.usage_since(now - timedelta(days=1)),
            "limits": self.database.get_settings().get("limits", {}),
        }

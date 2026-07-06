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
        if request_kind == "image":
            images = self.database.usage_since(now - timedelta(days=1), request_kind="image")
            if images["requests"] >= float(settings.get("image_generations_per_day", 2)):
                raise LimitExceeded("Image-generations-per-day limit reached")

    def summary(self) -> dict[str, object]:
        """Return current window usage alongside configured limits."""

        now = datetime.now(UTC)
        return {
            "hour": self.database.usage_since(now - timedelta(hours=1)),
            "day": self.database.usage_since(now - timedelta(days=1)),
            "limits": self.database.get_settings().get("limits", {}),
        }

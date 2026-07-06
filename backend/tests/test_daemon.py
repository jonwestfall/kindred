"""Pure daemon scheduling policy coverage."""

from datetime import UTC, datetime, timedelta

from kindred.daemon import in_quiet_hours, should_initiate


CHARACTER = {
    "initiative_frequency": 2.0,
    "cooldown_minutes": 240,
}
SETTINGS = {
    "enabled": True,
    "quiet_hours_start": "22:00",
    "quiet_hours_end": "08:00",
    "global_messages_per_hour": 4,
    "global_messages_per_day": 12,
}


def test_overnight_quiet_hours():
    assert in_quiet_hours(datetime(2026, 1, 1, 23, 0, tzinfo=UTC), "22:00", "08:00")
    assert in_quiet_hours(datetime(2026, 1, 1, 7, 59, tzinfo=UTC), "22:00", "08:00")
    assert not in_quiet_hours(datetime(2026, 1, 1, 12, 0, tzinfo=UTC), "22:00", "08:00")


def test_cooldown_prevents_initiation():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    decision = should_initiate(
        character=CHARACTER,
        daemon_settings=SETTINGS,
        now=now,
        last_message_at=now - timedelta(minutes=30),
        last_checked_at=now - timedelta(hours=1),
        initiated_last_hour=0,
        initiated_last_day=0,
        random_value=lambda: 0,
    )
    assert not decision.initiate
    assert "cooldown" in decision.note.lower()


def test_elapsed_time_and_random_sample_can_initiate():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    decision = should_initiate(
        character=CHARACTER,
        daemon_settings=SETTINGS,
        now=now,
        last_message_at=now - timedelta(days=1),
        last_checked_at=now - timedelta(hours=12),
        initiated_last_hour=0,
        initiated_last_day=0,
        random_value=lambda: 0,
    )
    assert decision.initiate
    assert "selected" in decision.note


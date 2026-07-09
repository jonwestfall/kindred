"""Strict pre-call cloud budget coverage."""

from datetime import UTC, datetime, timedelta

import pytest

from kindred.rate_limits import LimitExceeded, RateLimiter


def test_hourly_request_limit_blocks_before_call(database):
    limiter = RateLimiter(database)
    for _ in range(2):
        database.log_usage(
            provider="test",
            model="cloud-model",
            request_kind="chat",
            input_tokens=10,
            output_tokens=10,
        )

    with pytest.raises(LimitExceeded, match="per-hour"):
        limiter.check_cloud(estimated_tokens=5)


def test_image_limit_is_independent(database):
    limiter = RateLimiter(database)
    limiter.check_cloud(estimated_tokens=0, request_kind="image")
    database.log_usage(
        provider="test",
        model="image-model",
        request_kind="image",
        dry_run=True,
    )
    with pytest.raises(LimitExceeded, match="Image-generations"):
        limiter.check_cloud(estimated_tokens=0, request_kind="image")


def test_reserve_cloud_writes_usage_before_provider_call(database):
    limiter = RateLimiter(database)

    usage_id = limiter.reserve_cloud(
        provider="test",
        model="cloud-model",
        request_kind="chat",
        input_tokens=10,
        output_tokens=20,
        estimated_cost_usd=0.25,
    )

    assert usage_id > 0
    usage = database.usage_since(datetime.now(UTC) - timedelta(minutes=5))
    assert usage["requests"] == 1
    assert usage["tokens"] == 30
    assert usage["cost"] == 0.25


def test_reserved_cloud_requests_count_against_next_request(database):
    limiter = RateLimiter(database)
    for _ in range(2):
        limiter.reserve_cloud(
            provider="test",
            model="cloud-model",
            request_kind="chat",
            input_tokens=1,
        )

    with pytest.raises(LimitExceeded, match="per-hour"):
        limiter.reserve_cloud(
            provider="test",
            model="cloud-model",
            request_kind="chat",
            input_tokens=1,
        )


def test_reserved_image_counts_against_image_limit(database):
    limiter = RateLimiter(database)
    limiter.reserve_cloud(
        provider="test",
        model="image-model",
        request_kind="image",
        dry_run=True,
    )

    with pytest.raises(LimitExceeded, match="Image-generations"):
        limiter.reserve_cloud(
            provider="test",
            model="image-model",
            request_kind="image",
            dry_run=True,
        )


def test_estimated_call_cost_cannot_cross_ceiling(database):
    limiter = RateLimiter(database)
    with pytest.raises(LimitExceeded, match="spend ceiling"):
        limiter.check_cloud(estimated_tokens=1, estimated_cost_usd=1.01)

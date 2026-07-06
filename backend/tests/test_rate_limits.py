"""Strict pre-call cloud budget coverage."""

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


def test_estimated_call_cost_cannot_cross_ceiling(database):
    limiter = RateLimiter(database)
    with pytest.raises(LimitExceeded, match="spend ceiling"):
        limiter.check_cloud(estimated_tokens=1, estimated_cost_usd=1.01)

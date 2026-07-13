"""Offline unit tests for the live-capture bounds/observability helpers.

These run in the default (offline) lane: every function under test is pure or
uses an injectable clock, so the batch bounds themselves are verified without
ever driving a browser or touching Mercari.
"""

from __future__ import annotations

import json
import logging

import pytest

from utils.live_capture_guard import (
    BOT_INTERSTITIAL,
    HTTP_ERROR,
    RATE_LIMITED,
    LiveDeadlineExceeded,
    RequestBudget,
    RequestBudgetExceeded,
    classify_capture_failure,
    log_live_event,
    should_abort_batch,
)


class _FakeClock:
    """Manually advanced monotonic clock for deadline tests."""

    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def test_request_budget_counts_navigations():
    budget = RequestBudget(max_requests=3, deadline_seconds=1000, clock=_FakeClock())
    budget.start()
    budget.register("profile", "https://example/1")
    budget.register("review", "https://example/1/reviews")
    assert budget.count == 2


def test_request_budget_raises_when_count_cap_exceeded():
    budget = RequestBudget(max_requests=2, deadline_seconds=1000, clock=_FakeClock())
    budget.start()
    budget.register("profile", "https://example/1")
    budget.register("review", "https://example/1/reviews")
    with pytest.raises(RequestBudgetExceeded):
        budget.register("profile", "https://example/2")
    # Rejected navigation must not have been counted.
    assert budget.count == 2


def test_request_budget_raises_when_deadline_exceeded():
    clock = _FakeClock()
    budget = RequestBudget(max_requests=100, deadline_seconds=30, clock=clock)
    budget.start()
    budget.register("profile", "https://example/1")
    clock.advance(31)
    with pytest.raises(LiveDeadlineExceeded):
        budget.register("review", "https://example/1/reviews")


def test_check_deadline_independent_of_count():
    clock = _FakeClock()
    budget = RequestBudget(max_requests=100, deadline_seconds=30, clock=clock)
    budget.start()
    budget.check_deadline()  # under deadline, no raise
    clock.advance(31)
    with pytest.raises(LiveDeadlineExceeded):
        budget.check_deadline()


def test_budget_requires_start_before_use():
    budget = RequestBudget(max_requests=1, deadline_seconds=1)
    with pytest.raises(RuntimeError):
        budget.register("profile", "https://example/1")
    with pytest.raises(RuntimeError):
        budget.check_deadline()


def test_classify_429_is_rate_limited():
    assert classify_capture_failure(429, "whatever body") == RATE_LIMITED


def test_classify_interstitial_wins_over_200():
    assert classify_capture_failure(200, "アクセスが集中しています") == BOT_INTERSTITIAL
    assert classify_capture_failure(200, "Please verify you are a human") == BOT_INTERSTITIAL


def test_classify_interstitial_wins_over_http_error():
    # A challenge body that returns 403 should still classify as the bot wall,
    # not a generic http_error, so the batch aborts.
    assert classify_capture_failure(403, "unusual traffic detected") == BOT_INTERSTITIAL


def test_classify_http_error_when_no_challenge():
    assert classify_capture_failure(500, "internal server error") == HTTP_ERROR
    assert classify_capture_failure(404, "not found") == HTTP_ERROR


def test_classify_healthy_returns_none():
    assert classify_capture_failure(200, "田中さんのプロフィール") is None
    assert classify_capture_failure(None, None) is None


def test_should_abort_only_on_backoff_classes():
    assert should_abort_batch(RATE_LIMITED) is True
    assert should_abort_batch(BOT_INTERSTITIAL) is True
    assert should_abort_batch(HTTP_ERROR) is False
    assert should_abort_batch(None) is False


def test_log_live_event_emits_parseable_json_without_body(caplog):
    logger = logging.getLogger("test.live_capture")
    body = "SENSITIVE PAGE CONTENT should never be logged"
    with caplog.at_level(logging.INFO, logger="test.live_capture"):
        record = log_live_event(
            logger,
            source_url="https://jp.mercari.com/user/profile/1",
            stage="profile_capture",
            elapsed_s=1.23456,
            failure_class=None,
            extra={"navigations": 2},
        )
    assert record["event"] == "live_capture"
    assert record["elapsed_s"] == 1.235
    assert record["navigations"] == 2
    # The emitted line must be valid JSON and must not carry page content.
    line = caplog.records[-1].getMessage()
    parsed = json.loads(line)
    assert parsed["source_url"] == "https://jp.mercari.com/user/profile/1"
    assert parsed["stage"] == "profile_capture"
    assert body not in line

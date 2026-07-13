from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

import pytest

from services.capture_service import (
    capture_profile,
    install_request_budget,
    resolve_profile_reference,
)
from services.parser_mercari import parse_profile, parse_review_entries
from services.proof_service import build_proof
from services.verify_service import verify_proof
from utils.live_capture_guard import (
    RequestBudget,
    classify_capture_failure,
    log_live_event,
    should_abort_batch,
)


logger = logging.getLogger("reputation_snapshot.live_capture")

# Off by default: a plain `pytest` run must stay offline/deterministic. Opt in
# explicitly with `RUN_LIVE_CAPTURE_TESTS=1 pytest -m live_capture` (see README).
RUN_LIVE_CAPTURE_TESTS = os.environ.get("RUN_LIVE_CAPTURE_TESTS", "0") == "1"
DEFAULT_LIVE_URLS = [
    "https://jp.mercari.com/user/profile/492792377",
    "https://jp.mercari.com/user/profile/839104844",
]
LIVE_URLS = [url.strip() for url in os.environ.get("MERCARI_LIVE_TEST_URLS", ",".join(DEFAULT_LIVE_URLS)).split(",") if url.strip()]
LIVE_ITEM_URLS = json.loads((Path(__file__).resolve().parent / "live_item_urls.json").read_text(encoding="utf-8"))

# Case caps (profiles/items bounded separately) and the batch-wide navigation +
# time budgets. All env-tunable so the scheduled CI lane can run conservatively.
MAX_PROFILE_CASES = int(os.environ.get("LIVE_CAPTURE_MAX_PROFILES", "3"))
MAX_ITEM_CASES = int(os.environ.get("LIVE_CAPTURE_MAX_ITEMS", "5"))
# Each capture_profile issues up to 2 navigations (profile + review page); the
# default cap leaves headroom for that across the capped case count.
MAX_REQUESTS = int(os.environ.get("LIVE_CAPTURE_MAX_REQUESTS", "20"))
BATCH_DEADLINE_SECONDS = float(os.environ.get("LIVE_CAPTURE_DEADLINE_SECONDS", "300"))

pytestmark = [
    pytest.mark.live_capture,
    pytest.mark.skipif(
        not RUN_LIVE_CAPTURE_TESTS,
        reason="Set RUN_LIVE_CAPTURE_TESTS=1 to enable live Playwright capture tests.",
    ),
]


class _BatchState:
    """Shared abort flag for the session. Once a rate-limit / bot-interstitial
    signal is seen, remaining live tests skip instead of hammering Mercari."""

    def __init__(self) -> None:
        self.aborted_reason: str | None = None

    def abort(self, reason: str) -> None:
        self.aborted_reason = reason


@pytest.fixture(scope="session")
def live_batch():
    # NOTE on session-scoped browser reuse: we intentionally do NOT share one
    # browser/context across tests. capture_profile() owns the full browser
    # lifecycle (launch → context with persisted storage_state → close) and that
    # per-call lifecycle IS the production path under test; reusing a context
    # here would stop the live tests from exercising real session/cookie setup
    # and teardown. Instead we bound the batch with a navigation budget + an
    # overall deadline (install_request_budget below) and abort on rate limits.
    budget = RequestBudget(max_requests=MAX_REQUESTS, deadline_seconds=BATCH_DEADLINE_SECONDS)
    budget.start()
    state = _BatchState()
    with install_request_budget(budget):
        yield budget, state


def _run_capture(budget, state, *, source_url: str, stage: str):
    """Guard wrapper: skip if the batch already aborted or is out of time,
    run the capture, then classify + structured-log the result and set the
    abort flag on rate-limit / bot-wall signals."""
    if state.aborted_reason:
        pytest.skip(f"live batch aborted earlier: {state.aborted_reason}")
    budget.check_deadline()
    started = time.monotonic()
    failure_class: str | None = None
    try:
        capture = capture_profile(source_url)
    finally:
        elapsed = time.monotonic() - started
    failure_class = classify_capture_failure(
        capture.get("http_status"), capture.get("visible_text")
    )
    log_live_event(
        logger,
        source_url=source_url,
        stage=stage,
        elapsed_s=elapsed,
        failure_class=failure_class,
        extra={"navigations": budget.count},
    )
    if should_abort_batch(failure_class):
        state.abort(f"{failure_class} at {stage}")
        pytest.skip(f"aborting live batch: {failure_class} for {source_url}")
    return capture


@pytest.mark.parametrize("profile_url", LIVE_URLS[:MAX_PROFILE_CASES])
def test_live_capture_smoke(profile_url: str, live_batch) -> None:
    budget, state = live_batch
    capture = _run_capture(budget, state, source_url=profile_url, stage="profile_capture")

    assert capture["http_status"] == 200
    assert capture["raw_html"]
    assert capture["visible_text"]
    assert capture["raw_html_sha256"]
    assert capture["visible_text_sha256"]
    assert capture["screenshot_sha256"]

    parsed = parse_profile(
        capture["raw_html"],
        capture["visible_text"],
        review_raw_html=capture.get("review_raw_html"),
        review_visible_text=capture.get("review_visible_text"),
    )
    review_entries = parse_review_entries(
        capture.get("review_raw_html"),
        capture.get("review_visible_text"),
        capture.get("review_bad_visible_text"),
        review_buyer_visible_text=capture.get("review_buyer_visible_text"),
        review_buyer_bad_visible_text=capture.get("review_buyer_bad_visible_text"),
    )
    assert parsed["display_name"] is not None or parsed["total_reviews"] is not None
    if profile_url.endswith("/492792377"):
        assert parsed["positive_reviews"] is not None
        assert parsed["negative_reviews"] is not None
        assert parsed["total_reviews"] is not None
        assert parsed["total_reviews"] >= parsed["positive_reviews"] + parsed["negative_reviews"]
        assert review_entries

    proof_bundle = build_proof(profile_url, capture, parsed, review_entries=review_entries)
    verify_result = verify_proof(proof_bundle["proof_payload"], proof_bundle["signature"])

    assert verify_result["valid"] is True


@pytest.mark.parametrize("item_url", LIVE_ITEM_URLS[:MAX_ITEM_CASES])
def test_live_item_url_generates_review_quality(item_url: str, live_batch) -> None:
    budget, state = live_batch
    resolution = resolve_profile_reference(item_url)
    assert resolution["query_kind"] == "item"
    assert resolution["profile_url"]

    capture = _run_capture(
        budget, state, source_url=resolution["profile_url"], stage="item_profile_capture"
    )
    review_entries = parse_review_entries(
        capture.get("review_raw_html"),
        capture.get("review_visible_text"),
        capture.get("review_bad_visible_text"),
        review_buyer_visible_text=capture.get("review_buyer_visible_text"),
        review_buyer_bad_visible_text=capture.get("review_buyer_bad_visible_text"),
    )
    parsed = parse_profile(
        capture["raw_html"],
        capture["visible_text"],
        review_raw_html=capture.get("review_raw_html"),
        review_visible_text=capture.get("review_visible_text"),
        item_raw_html=resolution.get("item_raw_html"),
        item_visible_text=resolution.get("item_visible_text"),
        item_total_reviews=resolution.get("seller_total_reviews"),
    )
    if parsed.get("display_name") is None and resolution.get("display_name"):
        parsed["display_name"] = resolution["display_name"]

    proof_bundle = build_proof(resolution["profile_url"], capture, parsed, review_entries=review_entries)
    proof = proof_bundle["proof_payload"]
    verify_result = verify_proof(proof, proof_bundle["signature"])

    assert verify_result["valid"] is True
    assert parsed["display_name"] is not None
    assert parsed["total_reviews"] is not None
    assert parsed["positive_reviews"] is not None
    assert parsed["negative_reviews"] is not None
    assert review_entries
    assert proof["quality"] is not None
    assert proof["quality"]["entry_count"] > 0
    assert proof["quality"]["as_seller"] or proof["quality"]["as_buyer"]

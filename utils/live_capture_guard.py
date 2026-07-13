"""Bounds and observability for opt-in live Mercari capture runs.

Live capture tests (and the scheduled live CI lane) drive a real browser
against a third-party host. Left unbounded, one run could fan out an
unlimited number of navigations or hang for minutes. These helpers make a
live batch *bounded* and *observable* without touching the production capture
path: the request budget is only installed by the live test harness, and all
classification/logging functions are pure so they are verified by the offline
suite (see tests/test_live_capture_guard.py).

Nothing here stores page content — only the source URL, pipeline stage,
elapsed time, and a coarse failure class, so logs are safe to keep as CI
artifacts.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

# Coarse failure classes. Kept as bare strings (not an enum) so they serialize
# straight into JSON log lines and test assertions stay readable.
RATE_LIMITED = "rate_limited"
BOT_INTERSTITIAL = "bot_interstitial"
HTTP_ERROR = "http_error"

# Substrings that signal Mercari served a challenge / bot wall rather than the
# real profile. Matched case-insensitively against captured visible text.
_INTERSTITIAL_MARKERS = (
    "アクセスが集中",           # "access is concentrated" throttle page
    "ロボットではないこと",       # "confirm you are not a robot"
    "unusual traffic",
    "are you a robot",
    "captcha",
    "px-captcha",
    "access denied",
    "please verify you are a human",
)


class LiveCaptureBudgetError(RuntimeError):
    """Base class for budget-exhaustion signals raised during a live batch."""


class RequestBudgetExceeded(LiveCaptureBudgetError):
    """Raised when the batch has issued more navigations than allowed."""


class LiveDeadlineExceeded(LiveCaptureBudgetError):
    """Raised when the batch has run longer than its overall wall-clock cap."""


@dataclass
class RequestBudget:
    """Hard caps for a single live batch: a maximum navigation count and an
    overall wall-clock deadline. ``clock`` is injectable so the offline tests
    can drive the deadline without real sleeps.

    Call ``start()`` once at the beginning of the batch, then ``register()``
    before every browser navigation. Both an over-count and an over-deadline
    raise, so a single run can never fan out or hang indefinitely.
    """

    max_requests: int
    deadline_seconds: float
    clock: Callable[[], float] = time.monotonic
    _count: int = field(default=0, init=False)
    _started_at: float | None = field(default=None, init=False)

    @property
    def count(self) -> int:
        return self._count

    def start(self) -> None:
        self._started_at = self.clock()
        self._count = 0

    def elapsed(self) -> float:
        if self._started_at is None:
            return 0.0
        return self.clock() - self._started_at

    def check_deadline(self) -> None:
        """Raise if the overall deadline has passed. Safe to call between
        tests to abort the remaining batch before starting more work."""
        if self._started_at is None:
            raise RuntimeError("RequestBudget.start() must be called before use")
        if self.elapsed() > self.deadline_seconds:
            raise LiveDeadlineExceeded(
                f"live batch exceeded {self.deadline_seconds}s deadline "
                f"(elapsed {self.elapsed():.1f}s)"
            )

    def register(self, stage: str, url: str) -> None:
        """Account for one navigation. Raises before the request would push the
        batch past either the count cap or the time deadline."""
        if self._started_at is None:
            raise RuntimeError("RequestBudget.start() must be called before use")
        self.check_deadline()
        if self._count + 1 > self.max_requests:
            raise RequestBudgetExceeded(
                f"live batch exceeded {self.max_requests} navigations "
                f"(stage={stage!r} url={url!r})"
            )
        self._count += 1


def classify_capture_failure(
    http_status: int | None, visible_text: str | None
) -> str | None:
    """Classify a capture result into a coarse failure class, or ``None`` when
    it looks healthy. Order matters: an explicit 429 is always rate-limited;
    otherwise an interstitial/challenge body wins over a generic HTTP error so
    the batch aborts on bot walls even when the wall returns 200."""
    if http_status == 429:
        return RATE_LIMITED
    text = (visible_text or "").lower()
    if any(marker.lower() in text for marker in _INTERSTITIAL_MARKERS):
        return BOT_INTERSTITIAL
    if http_status is not None and http_status >= 400:
        return HTTP_ERROR
    return None


def should_abort_batch(failure_class: str | None) -> bool:
    """Whether encountering ``failure_class`` should stop the remaining batch.
    Rate-limits and bot walls mean "back off now"; a one-off HTTP error on a
    single profile does not justify aborting the whole run."""
    return failure_class in (RATE_LIMITED, BOT_INTERSTITIAL)


def log_live_event(
    logger: Any,
    *,
    source_url: str,
    stage: str,
    elapsed_s: float,
    failure_class: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Emit one structured (JSON) log line for a live-capture stage and return
    the record. Deliberately records only non-sensitive metadata — never page
    content — so the log is safe as a CI artifact."""
    record: dict[str, Any] = {
        "event": "live_capture",
        "source_url": source_url,
        "stage": stage,
        "elapsed_s": round(elapsed_s, 3),
        "failure_class": failure_class,
    }
    if extra:
        record.update(extra)
    logger.info(json.dumps(record, ensure_ascii=False, sort_keys=True))
    return record

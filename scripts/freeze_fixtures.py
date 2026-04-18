from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.capture_service import capture_profile
from utils.json_utils import load_json


FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures"


def main() -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    cases = load_json(PROJECT_ROOT / "tests" / "test_cases.json")
    processed_fixtures: set[str] = set()

    for case in cases:
        fixture_name = case.get("fixture")
        profile_url = case.get("url")
        if not fixture_name or not profile_url or fixture_name in processed_fixtures:
            continue

        capture = capture_profile(profile_url)
        (FIXTURE_DIR / f"{fixture_name}.html").write_text(capture["raw_html"], encoding="utf-8")
        (FIXTURE_DIR / f"{fixture_name}.txt").write_text(capture["visible_text"], encoding="utf-8")
        processed_fixtures.add(fixture_name)
        print(f"Updated {fixture_name}")


if __name__ == "__main__":
    main()

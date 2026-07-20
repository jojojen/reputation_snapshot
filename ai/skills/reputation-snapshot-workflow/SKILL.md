---
name: reputation-snapshot-workflow
description: Work on the reputation_snapshot service. Use when modifying Mercari capture and parser logic, proof generation and verification, Flask API behavior, storage flow, or parser fixtures and tests. Preserve the proof contract, keep parsing deterministic where possible, and verify parser or proof changes with the existing test suite.
---

# Reputation Snapshot Workflow

## First Principle — General Correctness

1. **Correctness first means general correctness, not correctness for one case.**
   Never make the current example pass with hardcoded keywords, values, output
   text, or exception branches. Prefer a structural solution that removes
   special cases; a sound fix should normally reduce total code and branch
   count. If a proposed fix adds case-specific code, stop and redesign it.

2. **Research uncertainty before coding.** When the correct general solution
   is unclear, consult current primary sources and proven implementations before
   changing code. Use that evidence to define a general contract or design;
   never replace uncertainty with a case-specific hardcode.

3. **Use ASD-STE100 as the language principle for comments and documentation.**
   During development, write code comments, technical notes, and user-facing
   project documentation in ASD Simplified Technical English style: short direct
   sentences, active voice, one instruction per sentence where practical,
   consistent terms for the same concept, and concrete nouns instead of vague
   references. Avoid idioms, rhetorical phrasing, hidden assumptions, and
   unnecessary adjectives. When exact ASD-STE100 compliance is impractical,
   prefer clarity, consistency, and unambiguous technical meaning.

## Overview

Use this skill before changing Mercari reputation extraction, proof generation, or service behavior in this repository.
This project mixes capture, parsing, storage, proof, and verification concerns, so choose the owning module first and then keep the change narrow.

## Core Areas

Start in the module that truly owns the behavior:

- `services/parser_mercari.py`
  - Parse visible profile, review, and item context into the structured payload
- `services/capture_service.py`
  - Collect raw artifacts and capture inputs
- `services/proof_service.py` and `verify_service.py`
  - Build and validate proof bundles and signatures
- `services/storage_service.py`
  - Persist snapshot records and retrieval behavior
- `app.py`
  - Flask API routes and orchestration

## Required Reading

Read these before substantial changes:

- `README.md`
- `reputation_snapshot_mvp_spec.md`
- The relevant test file in `tests/`
- `tests/test_cases.json` and `tests/fixtures/` for parser work

## Common Task Map

Use these default paths:

- Parser fixes
  - Read `services/parser_mercari.py`
  - Update fixture-backed expectations in `tests/test_parser.py` and `tests/test_cases.json`
- Proof or verification changes
  - Read `services/proof_service.py`, `signing_service.py`, and `verify_service.py`
  - Verify with `tests/test_verify.py` and the proof assertions in `tests/test_parser.py`
- Capture or browser flow changes
  - Read `services/capture_service.py`
  - Verify with `tests/test_capture_service.py`
- API changes
  - Read `app.py`
  - Verify with `tests/test_app_api.py`

## Workflow

1. State assumptions about the source artifact and the expected output contract.
2. Read the target module and its tests before editing.
3. Prefer deterministic parsing logic over LLM-only repair paths.
4. Preserve proof payload compatibility unless the user explicitly requests a contract change.
5. Add or update regression coverage for parser bugs and malformed fixture cases.
6. Run the narrowest useful test set first, then widen if the change touched shared paths.

## Verification

Prefer targeted checks:

- `.\.venv\Scripts\python -m pytest tests/test_parser.py`
- `.\.venv\Scripts\python -m pytest tests/test_verify.py`
- `.\.venv\Scripts\python -m pytest tests/test_capture_service.py`
- `.\.venv\Scripts\python -m pytest tests/test_app_api.py`

Use repo scripts when they match the task:

- `scripts\run_all_tests.bat`
- `scripts\freeze_fixtures.bat` when intentionally refreshing stored fixture outputs

## Guardrails

- Do not weaken proof verification to make tests pass.
- Do not let parser heuristics silently overwrite required fields without evidence from source artifacts.
- Do not replace fixture-backed coverage with manual spot checks.
- Call out live-capture dependencies, timeouts, and environment assumptions explicitly.

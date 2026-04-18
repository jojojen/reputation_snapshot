@echo off
setlocal

call .venv\Scripts\activate
set RUN_LIVE_CAPTURE_TESTS=1
python -m pytest tests -s

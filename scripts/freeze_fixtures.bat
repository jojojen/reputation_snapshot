@echo off
setlocal

call .venv\Scripts\activate
python scripts\freeze_fixtures.py

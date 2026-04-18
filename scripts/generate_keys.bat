@echo off
setlocal

call .venv\Scripts\activate
python scripts\generate_keys.py

@echo off
setlocal

call .venv\Scripts\activate

if not exist instance (
    mkdir instance
)

where sqlite3 >nul 2>nul
if %errorlevel%==0 (
    sqlite3 instance\app.db < schema.sql
) else (
    python scripts\init_db.py
)

@echo off
if "%~1"=="go" goto :main
cmd /k ""%~f0" go"
exit /b

:main
cd /d "%~dp0"
echo ============================================
echo  Reputation Snapshot  ^|  Quick Start
echo ============================================
echo.

:: ---------- Python ----------
echo [CHECK] Python...
where python >nul 2>nul
if errorlevel 1 goto :err_python
echo [OK] Python found.

:: ---------- venv ----------
echo [CHECK] venv...
if exist .venv goto :venv_ok
echo [SETUP] Creating virtual environment...
python -m venv .venv
if errorlevel 1 goto :err_venv
echo [OK] venv created.
:venv_ok

:: ---------- packages ----------
echo [CHECK] Flask...
.venv\Scripts\python -c "import flask" >nul 2>nul
if not errorlevel 1 goto :flask_ok
echo [SETUP] Installing packages (~1 min)...
.venv\Scripts\pip install -r requirements.txt
if errorlevel 1 goto :err_pip
echo [OK] Packages installed.
:flask_ok
echo [OK] Flask ready.

:: ---------- Playwright Chromium ----------
echo [CHECK] Playwright Chromium...
.venv\Scripts\python -m playwright install chromium
if errorlevel 1 echo [WARN] Playwright chromium issue, continuing...
echo [OK] Playwright done.

:: ---------- DB ----------
echo [CHECK] Database...
if not exist instance mkdir instance
if exist instance\app.db goto :db_ok
echo [SETUP] Initialising database...
where sqlite3 >nul 2>nul
if not errorlevel 1 goto :db_sqlite3
.venv\Scripts\python scripts\init_db.py
if errorlevel 1 goto :err_db
goto :db_created
:db_sqlite3
sqlite3 instance\app.db < schema.sql
if errorlevel 1 goto :err_db
:db_created
echo [OK] Database created.
:db_ok
echo [OK] Database ready.

:: ---------- Keys ----------
echo [CHECK] Keys...
if exist keys\ed25519_private_key.pem goto :keys_ok
echo [SETUP] Generating Ed25519 keys...
.venv\Scripts\python scripts\generate_keys.py
if errorlevel 1 goto :err_keys
echo [OK] Keys generated.
:keys_ok
echo [OK] Keys ready.

:: ---------- Launch ----------
echo.
echo [OK] All checks passed. Starting server...
echo.
start "Reputation Snapshot - Server" .venv\Scripts\python app.py
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:5000"
echo [OK] Server started. Browser opening at http://127.0.0.1:5000
goto :done

:err_python
echo [ERROR] Python not found. Install Python 3.12+ and retry.
goto :done
:err_venv
echo [ERROR] Failed to create venv.
goto :done
:err_pip
echo [ERROR] pip install failed.
goto :done
:err_db
echo [ERROR] Database init failed.
goto :done
:err_keys
echo [ERROR] Key generation failed.
goto :done

:done
echo.
pause

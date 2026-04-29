@echo off
if "%~1"=="go" goto :main
cmd /k ""%~f0" go %*"
exit /b

:main
shift
cd /d "%~dp0"
echo ============================================
echo  Reputation Snapshot  ^|  Quick Start
echo ============================================
echo.

set NO_BROWSER=0
:parse_args
if "%~1"=="" goto :args_done
if /i "%~1"=="--no-browser" set NO_BROWSER=1
if /i "%~1"=="/no-browser" set NO_BROWSER=1
shift
goto :parse_args
:args_done

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

:: ---------- Read ADMIN_TOKEN from .env ----------
set ADMIN_TOKEN=dev_admin
if exist .env (
    for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
        if /i "%%A"=="ADMIN_TOKEN" set ADMIN_TOKEN=%%B
    )
)

:: ---------- Launch ----------
echo.
echo [OK] All checks passed. Starting server...
echo.
start "Reputation Snapshot - Server" .venv\Scripts\python app.py
if "%NO_BROWSER%"=="1" goto :browser_skipped
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:5000"
start "" "http://127.0.0.1:5000/admin?token=%ADMIN_TOKEN%"
:browser_skipped
echo [OK] Server started.
if "%NO_BROWSER%"=="1" (
echo [OK] Browser opening skipped.
) else (
echo [OK] Browser opening:
echo      Main : http://127.0.0.1:5000
echo      Admin: http://127.0.0.1:5000/admin?token=%ADMIN_TOKEN%
)
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

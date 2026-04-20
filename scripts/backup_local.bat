@echo off
:: 把 Fly.io 上的 DB 備份到本機
:: 需要先裝好 flyctl 並登入 (fly auth login)
:: 使用方式：直接雙擊執行

setlocal

set APP_NAME=reputation-snapshot
set BACKUP_DIR=%~dp0..\backups

if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set DT=%%I
set TIMESTAMP=%DT:~0,8%_%DT:~8,4%
set DEST=%BACKUP_DIR%\app_%TIMESTAMP%.db

echo [backup] 從 Fly.io 備份 DB...

:: 在 container 裡做 SQLite backup (safe dump，不怕寫入中途)
fly ssh console -a %APP_NAME% -C "sqlite3 /data/app.db '.backup /tmp/bak.db'"
if errorlevel 1 goto :err

:: 用 fly sftp 把檔案拉到本機
fly sftp get -a %APP_NAME% /tmp/bak.db "%DEST%"
if errorlevel 1 goto :err

echo [OK] 備份完成：%DEST%
goto :done

:err
echo [ERROR] 備份失敗。確認 flyctl 已登入，且 APP_NAME 正確。

:done
pause

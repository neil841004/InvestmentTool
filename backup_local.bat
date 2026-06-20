@echo off
setlocal

cd /d "%~dp0"

set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
)

echo Backing up Supabase data to local SQLite...
echo Project: %CD%
echo.

"%PYTHON_EXE%" backup_supabase_local.py
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
    echo Backup completed.
) else (
    echo Backup failed with exit code %EXIT_CODE%.
)

echo.
pause
exit /b %EXIT_CODE%

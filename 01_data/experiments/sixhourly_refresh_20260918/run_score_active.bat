@echo off
REM ASCII ONLY on purpose (Thai text in a .bat breaks cmd parsing).
REM Weekly progress report for the 6h shadow test (score_active.py).
REM Output: shadow_active_progress.txt + shadow_active_report.csv in this folder. Does not touch the prediction log.
REM
REM Task Scheduler (run once, cmd as Administrator) - every Monday 09:00:
REM   schtasks /create /tn "MaeNaRua_Shadow6h_ActiveScore" /tr "\"D:\maenaruea-water-web\01_data\experiments\sixhourly_refresh_20260918\run_score_active.bat\"" /sc WEEKLY /d MON /st 09:00 /rl LIMITED /f
REM Delete:  schtasks /delete /tn "MaeNaRua_Shadow6h_ActiveScore" /f
setlocal
set "SCRIPT_DIR=%~dp0"
set "VENV_PYTHON=%SCRIPT_DIR%..\..\..\.venv\Scripts\python.exe"
if not exist "%VENV_PYTHON%" set "VENV_PYTHON=python"
cd /d "%SCRIPT_DIR%"
"%VENV_PYTHON%" score_active.py > last_score_active.log 2>&1
exit /b %ERRORLEVEL%

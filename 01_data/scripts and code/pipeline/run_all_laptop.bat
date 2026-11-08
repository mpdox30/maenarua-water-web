@echo off
REM ASCII ONLY (Thai in .bat breaks cmd). 2026-11-07: ONE entry point for the laptop = everything Colab does.
REM Run this (or schedule it) INSTEAD of the separate tasks. Colab "run all" produces the same set of files.
REM Order: git pull both repos -> WMB refresh -> flood (09_live) -> data pipeline -> monitoring/6h/accuracy
REM        -> reservoir orchestration+ledger -> SAR -> 6h shadow -> state marker -> push
setlocal
set "SCRIPT_DIR=%~dp0"
set "WEB=D:\maenaruea-water-web"
set "WMB=D:\WMB_Phayao"
set "PYW=%SCRIPT_DIR%..\..\..\.venv\Scripts\python.exe"
if not exist "%PYW%" set "PYW=C:\Python314\python.exe"
set "PYM=%WMB%\.venv\Scripts\python.exe"
if not exist "%PYM%" set "PYM=%PYW%"
set "R_WMB=?" & set "R_FLOOD=?" & set "R_PIPE=?" & set "R_MON=?" & set "R_RES=?" & set "R_SAR=?" & set "R_6H=?"

cd /d "%WEB%" & "%PYW%" "%SCRIPT_DIR%mark_run.py" --check
git -C "%WEB%" pull --no-rebase --no-edit origin master
"%PYW%" "%SCRIPT_DIR%push_wmb_data.py" --wmb "%WMB%"

call "%WMB%\09_live\daily_wmb_refresh\run_daily_wmb_refresh.bat"
if errorlevel 1 (set "R_WMB=fail") else (set "R_WMB=ok")

cd /d "%WMB%" & python 09_live\daily_update.py >> 09_live\logs\daily.log 2>&1
if errorlevel 1 (set "R_FLOOD=fail") else (set "R_FLOOD=ok")

call "%SCRIPT_DIR%run_pipeline.bat"
if errorlevel 1 (set "R_PIPE=fail") else (set "R_PIPE=ok")

REM monitoring builder (every 15 min) and 6h shadow have their OWN scheduled tasks -> not called here (avoid concurrent git pushes)
set "R_MON=scheduler"

call "%SCRIPT_DIR%run_reservoir_daily_orchestration.bat"
if errorlevel 1 (set "R_RES=fail") else (set "R_RES=ok")

call "%SCRIPT_DIR%run_sar_background_job.bat"
if errorlevel 1 (set "R_SAR=fail") else (set "R_SAR=ok")

set "R_6H=scheduler"

"%PYW%" "%SCRIPT_DIR%push_wmb_data.py" --wmb "%WMB%"
"%PYW%" "%SCRIPT_DIR%push_web_data.py" --web "%WEB%" --wmb "%WMB%"
cd /d "%WEB%"
"%PYW%" "%SCRIPT_DIR%mark_run.py" --done wmb_daily_refresh=%R_WMB% flood_daily_update=%R_FLOOD% data_pipeline=%R_PIPE% reservoir_ledger=%R_RES% sar=%R_SAR%
git add "01_data/run_state/last_run.json"
git commit -m "Auto-update: run state (laptop) %DATE% %TIME%" >nul 2>&1
git pull --no-rebase --no-edit origin master
git push origin HEAD:master
echo [DONE] run_all_laptop finished. wmb=%R_WMB% flood=%R_FLOOD% pipe=%R_PIPE% mon=%R_MON% res=%R_RES% sar=%R_SAR% 6h=%R_6H%
endlocal
exit /b 0

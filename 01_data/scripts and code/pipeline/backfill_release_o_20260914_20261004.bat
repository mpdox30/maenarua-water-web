@echo off
chcp 65001 >nul
REM ============================================================================
REM One-off backfill 2026-10-06: re-run reservoir_daily_orchestration.py for 2026-09-14 .. 2026-10-04
REM
REM Why: valve-open events #3 (inlet 5572.8 m3/d) and #4 (spillway 9446.4 m3/d), open since
REM 2026-09-14 10:00 and not yet closed, were entered in the Google Form only on 2026-10-06.
REM The daily ledger rows for 14 Sep - 4 Oct were already written with O=0 (the event did not
REM exist in the release_log sheet at that time). Re-running each date picks up O=15019.2 m3/d
REM and recomputes Inflow = dS - R + O + Spill + E. Each run backs up the official xlsx first
REM (.bak_before_live_write_*), and replaces the existing row of that date (see run_and_append).
REM
REM After this finishes, run run_reservoir_daily_orchestration.bat once: it rebuilds the
REM corrected ledger + water_ledger.json and does git commit/push.
REM ============================================================================
setlocal
set "SCRIPT_DIR=%~dp0"
set "VENV_PYTHON=%SCRIPT_DIR%..\..\..\.venv\Scripts\python.exe"
cd /d "%SCRIPT_DIR%"

for /L %%D in (14,1,30) do (
    echo ===== 2026-09-%%D =====
    "%VENV_PYTHON%" reservoir_daily_orchestration.py --date 2026-09-%%D
)
for /L %%D in (1,1,4) do (
    echo ===== 2026-10-0%%D =====
    "%VENV_PYTHON%" reservoir_daily_orchestration.py --date 2026-10-0%%D
)

echo.
echo [DONE] backfill finished. Now run run_reservoir_daily_orchestration.bat once.
endlocal

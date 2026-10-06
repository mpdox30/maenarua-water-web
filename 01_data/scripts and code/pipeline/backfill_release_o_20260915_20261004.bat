@echo off
chcp 65001 >nul
REM ============================================================================
REM One-off backfill 2026-10-06: re-run reservoir_daily_orchestration.py for 2026-09-15 .. 2026-10-04
REM
REM Why: valve-open events #3 (inlet 5572.8 m3/d) and #4 (spillway 9446.4 m3/d), open since
REM 2026-09-14 10:00 and not yet closed, were entered in the Google Form only on 2026-10-06.
REM The daily ledger rows for 14 Sep - 4 Oct were already written with O=0 (the event did not
REM exist in the release_log sheet at that time). Re-running each date picks up O=15019.2 m3/d
REM and recomputes Inflow = dS - R + O + Spill + E. Each run backs up the official xlsx first
REM (.bak_before_live_write_*), and replaces the existing row of that date (see run_and_append).
REM
REM Telemetry: the live publish-to-web sheet no longer holds 07:00 readings for 14 Sep onward
REM (rows trimmed/archived), so a merged local CSV is used via --sheet-source:
REM   inflow_auto\telemetry_backfill_20260910_20261005.csv  (10-min RES002 level + rain)
REM   = uploaded Telemetry xlsx (until 2026-09-18) + shadow_gdrive_raw_store.csv (from 2026-09-19);
REM   the two sources were compared on 283 overlapping readings: identical.
REM Day 14 Sep is not re-run: the window 07:00(13)->07:00(14) ends before the 10:00 valve opening,
REM so O stays 0 for that day (verified: recomputed inflow equals the existing official value).
REM
REM After this finishes, run run_reservoir_daily_orchestration.bat once: it rebuilds the
REM corrected ledger + water_ledger.json and does git commit/push.
REM ============================================================================
setlocal
set "SCRIPT_DIR=%~dp0"
set "VENV_PYTHON=%SCRIPT_DIR%..\..\..\.venv\Scripts\python.exe"
set "TELEM=%SCRIPT_DIR%..\..\Reservoirs\inflow_auto\telemetry_backfill_20260910_20261005.csv"
cd /d "%SCRIPT_DIR%"

for /L %%D in (15,1,30) do (
    echo ===== 2026-09-%%D =====
    "%VENV_PYTHON%" reservoir_daily_orchestration.py --date 2026-09-%%D --sheet-source "%TELEM%"
)
for /L %%D in (1,1,4) do (
    echo ===== 2026-10-0%%D =====
    "%VENV_PYTHON%" reservoir_daily_orchestration.py --date 2026-10-0%%D --sheet-source "%TELEM%"
)

echo.
echo [DONE] backfill finished. Now run run_reservoir_daily_orchestration.bat once.
endlocal

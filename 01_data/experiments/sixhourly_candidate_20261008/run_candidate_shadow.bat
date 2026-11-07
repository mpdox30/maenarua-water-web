@echo off
REM Candidate 6h shadow runner: (1) fetch IMERG (2) predict + log (3) write heartbeat
REM ASCII ONLY on purpose: Thai text in a .bat + chcp 65001 makes cmd mis-parse lines
REM (it ran garbled fragments as commands and returned exit code 9009 = command not found).
REM
REM Uses the repo .venv (repo root = 3 levels above this file). Works on both machines.
REM
REM Google Drive mode (recommended): set once per machine, pointing at the Drive-synced folder
REM   setx CAND_SYNC_DIR "G:\My Drive\MaeNaRua_candidate_logs"
REM Each machine writes its own files (candidate_log_%COMPUTERNAME%.csv + heartbeat_%COMPUTERNAME%.csv)
REM If CAND_SYNC_DIR is not set, files are written in this folder.
REM
REM Exit code of this script = worst of fetch/shadow exit codes (0 = OK) so Task Scheduler
REM "Last Result" is meaningful. Full output of the last run: last_run_%COMPUTERNAME%.log
set "PY=%~dp0..\..\..\.venv\Scripts\python.exe"
cd /d "%~dp0"
set "RUNLOG=%~dp0last_run_%COMPUTERNAME%.log"
if defined CAND_SYNC_DIR (
  if not exist "%CAND_SYNC_DIR%" mkdir "%CAND_SYNC_DIR%"
  set "CAND_LOG=%CAND_SYNC_DIR%\candidate_log_%COMPUTERNAME%.csv"
  set "HB=%CAND_SYNC_DIR%\heartbeat_%COMPUTERNAME%.csv"
) else (
  set "HB=%~dp0heartbeat_%COMPUTERNAME%.csv"
)
set "PYTHONIOENCODING=utf-8"
>"%RUNLOG%" echo %DATE% %TIME% start, PY=%PY%
if not exist "%PY%" >>"%RUNLOG%" echo ERROR: python not found at %PY%
"%PY%" fetch_imerg_early_earthaccess.py >>"%RUNLOG%" 2>&1
set "E1=%ERRORLEVEL%"
"%PY%" shadow_candidate.py >>"%RUNLOG%" 2>&1
set "E2=%ERRORLEVEL%"
if not exist "%HB%" >"%HB%" echo run_at,machine,fetch_exit,shadow_exit
>>"%HB%" echo %DATE% %TIME%,%COMPUTERNAME%,%E1%,%E2%
>>"%RUNLOG%" echo %DATE% %TIME% done, fetch_exit=%E1% shadow_exit=%E2%
set "RC=0"
if not "%E1%"=="0" set "RC=%E1%"
if not "%E2%"=="0" set "RC=%E2%"
exit /b %RC%

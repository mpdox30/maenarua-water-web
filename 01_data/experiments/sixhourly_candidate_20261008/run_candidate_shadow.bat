@echo off
REM รันรุ่นผู้สมัคร shadow: (1) ดึง IMERG (2) ทำนาย+บันทึก log  (3) เขียน heartbeat
REM ใช้ .venv ของ repo ที่ไฟล์นี้อยู่ ใช้ได้ทั้ง 2 เครื่อง
REM
REM โหมด Google Drive (แนะนำ): ตั้ง env ครั้งเดียวต่อเครื่อง ชี้ไปโฟลเดอร์ที่ Google Drive for desktop ซิงก์
REM   setx CAND_SYNC_DIR "G:\My Drive\MaeNaRua_candidate_logs"
REM แต่ละเครื่องเขียนไฟล์ของตัวเอง (candidate_log_%COMPUTERNAME%.csv + heartbeat_%COMPUTERNAME%.csv) -> ไม่ชนกันบน Drive
REM ถ้าไม่ตั้ง CAND_SYNC_DIR จะเขียนในโฟลเดอร์นี้เหมือนเดิม
chcp 65001 >nul
set "PY=%~dp0..\..\..\.venv\Scripts\python.exe"
cd /d "%~dp0"
if defined CAND_SYNC_DIR (
  if not exist "%CAND_SYNC_DIR%" mkdir "%CAND_SYNC_DIR%"
  set "CAND_LOG=%CAND_SYNC_DIR%\candidate_log_%COMPUTERNAME%.csv"
  set "HB=%CAND_SYNC_DIR%\heartbeat_%COMPUTERNAME%.csv"
) else (
  set "HB=%~dp0heartbeat_%COMPUTERNAME%.csv"
)
"%PY%" fetch_imerg_early_earthaccess.py
set "E1=%ERRORLEVEL%"
"%PY%" shadow_candidate.py
set "E2=%ERRORLEVEL%"
if not exist "%HB%" echo run_at,machine,fetch_exit,shadow_exit>"%HB%"
echo %DATE% %TIME%,%COMPUTERNAME%,%E1%,%E2%>>"%HB%"

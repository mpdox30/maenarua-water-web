@echo off
REM ============================================================================
REM run_reservoir_daily_orchestration.bat
REM ----------------------------------------------------------------------------
REM Launcher สำหรับรัน reservoir_daily_orchestration.py บน Windows ผ่าน Task Scheduler
REM
REM 2026-07-18: สคริปต์นี้ไป LIVE แล้ว -- เขียนทับไฟล์ทางการจริง
REM (01_data/Reservoirs/inflow/<year>/<year>_<month>_MNR.xlsx) นอกเหนือจาก shadow CSV เดิม
REM ทุกครั้งที่รันจะ backup ไฟล์ทางการเดิมไว้อัตโนมัติก่อนเขียน (ดู reservoir_official_file_writer.py)
REM
REM ใช้ .venv เดียวกับ run_pipeline.bat ที่ D:\maenaruea-water-web\.venv
REM
REM ค่า default ของ reservoir_daily_orchestration.py คือคำนวณของ "เมื่อวาน" เสมอ (--date ไม่ระบุ)
REM เหมาะกับรันทุกเช้าหลังข้อมูล 07:00 เข้า Google Sheet log แล้ว (เช่น 07:30-08:00 น.)
REM
REM ต้องตั้ง env var RESERVOIR_TELEMETRY_SHEET_CSV_URL ไว้ก่อน (ไม่งั้นจะ fallback ไปใช้ค่า
REM DEFAULT_SHEET_CSV_URL ที่ฝังในโค้ด -- ใช้งานได้แต่แนะนำให้ตั้ง env var แยกต่างหากมากกว่า)
REM
REM วิธีตั้ง Windows Task Scheduler (ทำครั้งเดียว) -- เปิด Command Prompt "Run as Administrator":
REM
REM   schtasks /create /tn "MaeNaRua_Reservoir_Daily_Orchestration" ^
REM     /tr "\"D:\maenaruea-water-web\01_data\scripts and code\pipeline\run_reservoir_daily_orchestration.bat\"" ^
REM     /sc DAILY /st 07:30 /ru "%USERNAME%" /rl LIMITED /f
REM
REM   ลบ task ถ้าต้องการ:  schtasks /delete /tn "MaeNaRua_Reservoir_Daily_Orchestration" /f
REM   ดูสถานะ:            schtasks /query /tn "MaeNaRua_Reservoir_Daily_Orchestration" /v /fo LIST
REM   รันทดสอบทันที:        schtasks /run /tn "MaeNaRua_Reservoir_Daily_Orchestration"
REM
REM ⚠️ ถ้าอยากปิดการเขียนไฟล์ทางการชั่วคราว (กลับไปเขียนแค่ shadow CSV) แก้บรรทัดรันด้านล่างเพิ่ม
REM     --skip-official-write ต่อท้าย
REM ============================================================================

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "VENV_PYTHON=%SCRIPT_DIR%..\..\..\.venv\Scripts\python.exe"

echo ============================================================
echo   Mae Na Rua Reservoir Daily Orchestration - run_reservoir_daily_orchestration.bat
echo   %DATE% %TIME%
echo ============================================================

if not exist "%VENV_PYTHON%" (
    echo [WARN] ไม่พบ .venv ที่ %VENV_PYTHON%
    echo [WARN] จะใช้ system Python แทน - แนะนำให้สร้าง .venv ก่อน ดูวิธีใน run_pipeline.bat
    set "VENV_PYTHON=C:\Python314\python.exe"
)

echo [INFO] Using Python: %VENV_PYTHON%
echo [INFO] Running reservoir_daily_orchestration.py (target date = เมื่อวาน, เขียนทั้ง shadow CSV + ไฟล์ทางการ) ...
echo.

cd /d "%SCRIPT_DIR%"
"%VENV_PYTHON%" reservoir_daily_orchestration.py
set "ORCH_EXIT_CODE=%ERRORLEVEL%"

echo.
echo [INFO] reservoir_daily_orchestration.py exited with code %ORCH_EXIT_CODE%
echo   (0 = สำเร็จ, non-zero = error -- เช็ค log ด้านบน โดยเฉพาะถ้าเขียนไฟล์ทางการล้มเหลว
echo    shadow CSV จะยังเขียนสำเร็จแยกต่างหากเสมอถ้าคำนวณได้ ไม่ขึ้นกับไฟล์ทางการ)

endlocal
exit /b %ORCH_EXIT_CODE%

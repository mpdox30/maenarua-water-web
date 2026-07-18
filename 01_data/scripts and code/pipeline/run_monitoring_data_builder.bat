@echo off
REM ============================================================================
REM run_monitoring_data_builder.bat
REM ----------------------------------------------------------------------------
REM Launcher สำหรับรัน monitoring_data_builder.py บน Windows ผ่าน Task Scheduler
REM ดึงข้อมูลโทรมาตรสด 4 สถานี (RES002/RES004/RES005/RES006) เขียนทับ
REM 03_website/assets/data/monitoring.json -- หน้า monitoring.html และการ์ด %ความจุ
REM บนหน้า index.html อ่านไฟล์นี้
REM
REM ใช้ .venv เดียวกับ run_pipeline.bat ที่ D:\maenaruea-water-web\.venv
REM
REM ความถี่ที่แนะนำ: ทุก 10-15 นาที (ให้ใกล้เคียงรอบ poll ของสถานีโทรมาตรเอง ~10 นาที)
REM
REM วิธีตั้ง Windows Task Scheduler (ทำครั้งเดียว) -- เปิด Command Prompt "Run as Administrator":
REM
REM   schtasks /create /tn "MaeNaRua_Monitoring_Data_Builder" ^
REM     /tr "\"D:\maenaruea-water-web\01_data\scripts and code\pipeline\run_monitoring_data_builder.bat\"" ^
REM     /sc MINUTE /mo 15 /ru "%USERNAME%" /rl LIMITED /f
REM
REM   ลบ task ถ้าต้องการ:  schtasks /delete /tn "MaeNaRua_Monitoring_Data_Builder" /f
REM   ดูสถานะ:            schtasks /query /tn "MaeNaRua_Monitoring_Data_Builder" /v /fo LIST
REM   รันทดสอบทันที:        schtasks /run /tn "MaeNaRua_Monitoring_Data_Builder"
REM ============================================================================

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "VENV_PYTHON=%SCRIPT_DIR%..\..\..\.venv\Scripts\python.exe"

echo ============================================================
echo   Mae Na Rua Monitoring Data Builder - run_monitoring_data_builder.bat
echo   %DATE% %TIME%
echo ============================================================

if not exist "%VENV_PYTHON%" (
    echo [WARN] ไม่พบ .venv ที่ %VENV_PYTHON%
    echo [WARN] จะใช้ system Python แทน - แนะนำให้สร้าง .venv ก่อน ดูวิธีใน run_pipeline.bat
    set "VENV_PYTHON=C:\Python314\python.exe"
)

echo [INFO] Using Python: %VENV_PYTHON%
echo [INFO] Running monitoring_data_builder.py ...
echo.

cd /d "%SCRIPT_DIR%"
"%VENV_PYTHON%" monitoring_data_builder.py
set "BUILDER_EXIT_CODE=%ERRORLEVEL%"

echo.
echo [INFO] monitoring_data_builder.py exited with code %BUILDER_EXIT_CODE%
echo   (0 = สำเร็จ, non-zero = error -- เช็ค log ด้านบน เช่น เชื่อมต่อ Google Sheet ไม่ได้)

endlocal
exit /b %BUILDER_EXIT_CODE%

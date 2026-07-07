@echo off
REM ============================================================================
REM run_pipeline.bat
REM ----------------------------------------------------------------------------
REM Launcher สำหรับรัน data_pipeline.py บน Windows (เช่นผ่าน Task Scheduler)
REM ใช้ .venv ของโปรเจกต์ที่ D:\maenaruea-water-web\.venv (สร้างจาก C:\Python314\python.exe)
REM ถ้ายังไม่ได้สร้าง .venv ให้รัน:
REM   cd /d "D:\maenaruea-water-web"
REM   C:\Python314\python.exe -m venv .venv
REM   .venv\Scripts\python.exe -m pip install -r "01_data\scripts and code\pipeline\requirements.txt"
REM ============================================================================

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "VENV_PYTHON=%SCRIPT_DIR%..\..\..\.venv\Scripts\python.exe"

echo ============================================================
echo   Mae Na Rua Water Pipeline - run_pipeline.bat
echo   %DATE% %TIME%
echo ============================================================

REM ใช้ python จาก .venv ของโปรเจกต์ ถ้ายังไม่เจอ (ยังไม่ได้สร้าง .venv) ให้ fallback ไปใช้ system Python
if not exist "%VENV_PYTHON%" (
    echo [WARN] ไม่พบ .venv ที่ %VENV_PYTHON%
    echo [WARN] จะใช้ system Python แทน - แนะนำให้สร้าง .venv ก่อน ดูวิธีในคอมเมนต์ด้านบนของไฟล์นี้
    set "VENV_PYTHON=C:\Python314\python.exe"
)

echo [INFO] Using Python: %VENV_PYTHON%
echo [INFO] Running data_pipeline.py ...
echo.

REM รันสคริปต์หลัก (working directory = โฟลเดอร์ที่ .bat นี้อยู่ เพื่อให้ relative path ใน script ถูกต้อง)
cd /d "%SCRIPT_DIR%"
"%VENV_PYTHON%" data_pipeline.py
set "PIPELINE_EXIT_CODE=%ERRORLEVEL%"

echo.
echo [INFO] data_pipeline.py exited with code %PIPELINE_EXIT_CODE%
echo   (0 = สำเร็จทั้งหมด, 1 = สำเร็จบางส่วน ดู logs\pipeline_log.txt, 2 = ล้มเหลวรุนแรง)

endlocal
exit /b %PIPELINE_EXIT_CODE%

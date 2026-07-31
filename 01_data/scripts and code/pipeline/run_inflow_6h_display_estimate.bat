@echo off
REM ============================================================================
REM run_inflow_6h_display_estimate.bat
REM ----------------------------------------------------------------------------
REM Launcher สำหรับรัน inflow_6h_display_estimate.py -- **ใช้รันมือ/ทดสอบเท่านั้นตอนนี้**
REM
REM **2026-07-31 แก้**: ย้ายไปรวมเข้ากับ run_monitoring_data_builder.bat แล้ว (รันต่อท้าย
REM monitoring_data_builder.py ในรอบเดียวกัน + push git รวมกันทีเดียว) เพื่อเลี่ยงการมี 2 scheduled
REM task แยกกันที่ต่างก็ pull/push git ของตัวเอง (เสี่ยงชนกันตอน push ถ้า schedule ใกล้กัน) --
REM **อย่าเอาไฟล์นี้ไปตั้ง schtasks แยกอีก** ถ้าเคยตั้งไว้แล้วให้ลบ:
REM   schtasks /delete /tn "MaeNaRua_Inflow6h_Display_Estimate" /f
REM ไฟล์นี้ยังใช้รันมือได้ตามปกติสำหรับทดสอบ/backfill (ดู --now, --sheet-source ด้านล่าง)
REM
REM 2026-07-31 (เดิม): สคริปต์นี้เป็น DISPLAY-ONLY เท่านั้น -- เขียนแค่ไฟล์ใหม่
REM 03_website/assets/data/inflow_6h_display.json ไม่แตะ/ไม่แทนที่ไฟล์ทางการหรือ shadow CSV
REM ของ reservoir_daily_orchestration.py และไม่เกี่ยวกับโมเดล CatBoost พยากรณ์ใดๆ เลย
REM (ดู docstring หัวไฟล์ inflow_6h_display_estimate.py สำหรับรายละเอียดสูตร/ข้อจำกัด)
REM
REM ใช้ .venv เดียวกับ run_pipeline.bat / run_reservoir_daily_orchestration.bat ที่
REM D:\maenaruea-water-web\.venv
REM
REM ค่า default คือคำนวณ "ณ ตอนนี้" ย้อนหลัง 84 ชม. (--lookback-hours 84) -- เผื่อคลุมหน้าต่างของ
REM as_of_date ที่ latest.json รายงาน (ซึ่งเป็น "เมื่อวาน" เสมอ) เว็บฝั่ง JS จะกรองเอาเฉพาะช่วงที่ตรงกับ
REM as_of_date เองอีกที ไม่ใช้ peak_window ทั้งไฟล์ตรงๆ -- แนะนำรันทุก 1 ชม. (เร็วกว่านี้ไม่ได้ประโยชน์
REM เพิ่มเพราะหน้าต่างเลื่อนทีละ 1 ชม.อยู่แล้ว)
REM
REM ต้องตั้ง env var RESERVOIR_TELEMETRY_SHEET_CSV_URL ไว้ก่อน (ตัวเดียวกับที่
REM reservoir_daily_orchestration.py ใช้ -- ไม่งั้นจะ fallback ไปใช้ค่า DEFAULT_SHEET_CSV_URL
REM ที่ฝังในโค้ด ใช้งานได้แต่แนะนำให้ตั้ง env var แยกต่างหากมากกว่า)
REM
REM วิธีตั้ง Windows Task Scheduler (ทำครั้งเดียว) -- เปิด Command Prompt "Run as Administrator":
REM
REM   schtasks /create /tn "MaeNaRua_Inflow6h_Display_Estimate" ^
REM     /tr "\"D:\maenaruea-water-web\01_data\scripts and code\pipeline\run_inflow_6h_display_estimate.bat\"" ^
REM     /sc HOURLY /mo 1 /ru "%USERNAME%" /rl LIMITED /f
REM
REM   ลบ task ถ้าต้องการ:  schtasks /delete /tn "MaeNaRua_Inflow6h_Display_Estimate" /f
REM   ดูสถานะ:            schtasks /query /tn "MaeNaRua_Inflow6h_Display_Estimate" /v /fo LIST
REM   รันทดสอบทันที:        schtasks /run /tn "MaeNaRua_Inflow6h_Display_Estimate"
REM
REM ⚠️ ถ้าอยากเปลี่ยนช่วง lookback แก้บรรทัดรันด้านล่างเพิ่ม --lookback-hours <ชั่วโมง>
REM ============================================================================

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "VENV_PYTHON=%SCRIPT_DIR%..\..\..\.venv\Scripts\python.exe"

echo ============================================================
echo   Mae Na Rua Reservoir 6h Display Estimate (display-only) - run_inflow_6h_display_estimate.bat
echo   %DATE% %TIME%
echo ============================================================

if not exist "%VENV_PYTHON%" (
    echo [WARN] ไม่พบ .venv ที่ %VENV_PYTHON%
    echo [WARN] จะใช้ system Python แทน - แนะนำให้สร้าง .venv ก่อน ดูวิธีใน run_pipeline.bat
    set "VENV_PYTHON=C:\Python314\python.exe"
)

echo [INFO] Using Python: %VENV_PYTHON%
echo [INFO] Running inflow_6h_display_estimate.py (display-only, เขียน assets/data/inflow_6h_display.json) ...
echo.

cd /d "%SCRIPT_DIR%"
"%VENV_PYTHON%" inflow_6h_display_estimate.py
set "EST_EXIT_CODE=%ERRORLEVEL%"

echo.
echo [INFO] inflow_6h_display_estimate.py exited with code %EST_EXIT_CODE%
echo   (0 = สำเร็จ, non-zero = error -- เช็ค log ด้านบน; สคริปต์นี้ไม่แตะไฟล์ทางการ/shadow CSV เลย
echo    ถ้า error ไม่กระทบ pipeline รายวันหลัก)

endlocal
exit /b %EST_EXIT_CODE%

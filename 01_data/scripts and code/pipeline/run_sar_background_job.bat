@echo off
REM ============================================================================
REM run_sar_background_job.bat
REM ----------------------------------------------------------------------------
REM Launcher สำหรับรัน sar_background_job.py บน Windows ผ่าน Task Scheduler
REM แยกต่างหากจาก run_pipeline.bat (data_pipeline.py หลัก) โดยตั้งใจ — ดู docstring หัวไฟล์
REM sar_background_job.py: SAR ควรอัปเดตแค่ ~ทุก 7-10 วันตาม revisit cycle ของ Sentinel-1
REM (check_new_sar_image() มี min_days_between_runs=30 gate อยู่แล้วด้วย) และ
REM trigger_crop_classification() ใช้เวลานาน (นาทีถึงหลายนาทีต่อ zone เพราะต้อง export+download
REM GeoTIFF จาก GEE) ไม่เหมาะรันพร้อม pipeline หลักที่ต้องจบเร็วทุกสัปดาห์
REM
REM ใช้ .venv เดียวกับ run_pipeline.bat ที่ D:\maenaruea-water-web\.venv
REM
REM วิธีตั้ง Windows Task Scheduler (ทำครั้งเดียว) — 2 ทางเลือก:
REM
REM ทางที่ 1: schtasks.exe ผ่าน command line (เร็วที่สุด) — เปิด Command Prompt "Run as
REM   Administrator" แล้วรันคำสั่งนี้ (ปรับ path ให้ตรงกับที่ไฟล์นี้อยู่จริงถ้าย้ายตำแหน่ง):
REM
REM   schtasks /create /tn "MaeNaRua_SAR_Background_Job" ^
REM     /tr "\"D:\maenaruea-water-web\01_data\scripts and code\pipeline\run_sar_background_job.bat\"" ^
REM     /sc WEEKLY /d MON /st 03:00 /ru "%USERNAME%" /rl LIMITED /f
REM
REM   (รันทุกวันจันทร์ 03:00 น. — ปรับ /d และ /st ได้ตามสะดวก เพราะ min_days_between_runs=30
REM   ข้างในเป็นตัวคุมจริงว่าจะ classify จริงรอบไหน รันบ่อยกว่านี้ก็ไม่เสียหาย แค่จะเช็คแล้วข้ามเฉยๆ)
REM
REM   ลบ task ถ้าต้องการ:  schtasks /delete /tn "MaeNaRua_SAR_Background_Job" /f
REM   ดูสถานะ:            schtasks /query /tn "MaeNaRua_SAR_Background_Job" /v /fo LIST
REM   รันทดสอบทันที:        schtasks /run /tn "MaeNaRua_SAR_Background_Job"
REM
REM ทางที่ 2: ผ่าน Task Scheduler GUI (taskschd.msc)
REM   1. เปิด Task Scheduler -> Create Task... (ไม่ใช่ Create Basic Task เพื่อให้ตั้งค่าได้ครบ)
REM   2. General: ตั้งชื่อ "MaeNaRua_SAR_Background_Job", เลือก "Run whether user is logged on or not"
REM   3. Triggers: New... -> Weekly, เลือกวัน + เวลาที่ต้องการ (เช่น จันทร์ 03:00)
REM   4. Actions: New... -> Program/script ใส่ path เต็มของไฟล์ .bat นี้
REM      Start in (optional): ใส่ "D:\maenaruea-water-web\01_data\scripts and code\pipeline"
REM   5. Settings: ติ๊ก "Run task as soon as possible after a scheduled start is missed"
REM      (กันพลาดรอบถ้าเครื่องปิดอยู่ตอนถึงเวลา) และตั้ง "Stop the task if it runs longer than"
REM      เป็น 2 ชั่วโมง (กันค้างค้าง เพราะ export+download อาจนานหลายนาทีต่อ zone แต่ไม่ควรเกินนี้)
REM
REM ⚠️ สำคัญ: ต้องตั้งค่า Service Account credential ก่อนใช้กับ scheduled task จริง (ดู TODO ใน
REM sar_classification.py/chirps_feature.py หัวไฟล์ — personal ee.Authenticate() ไม่เหมาะกับการรัน
REM แบบไม่มีคนคอย login ซ้ำ token อาจหมดอายุกลางทาง) ดู get_ee_credentials() ใน gee_auth.py
REM ============================================================================

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "VENV_PYTHON=%SCRIPT_DIR%..\..\..\.venv\Scripts\python.exe"

echo ============================================================
echo   Mae Na Rua SAR Background Job - run_sar_background_job.bat
echo   %DATE% %TIME%
echo ============================================================

if not exist "%VENV_PYTHON%" (
    echo [WARN] ไม่พบ .venv ที่ %VENV_PYTHON%
    echo [WARN] จะใช้ system Python แทน - แนะนำให้สร้าง .venv ก่อน ดูวิธีใน run_pipeline.bat
    set "VENV_PYTHON=C:\Python314\python.exe"
)

echo [INFO] Using Python: %VENV_PYTHON%
echo [INFO] Running sar_background_job.py ...
echo.

cd /d "%SCRIPT_DIR%"
"%VENV_PYTHON%" sar_background_job.py
set "JOB_EXIT_CODE=%ERRORLEVEL%"

echo.
echo [INFO] sar_background_job.py exited with code %JOB_EXIT_CODE%
echo   (0 = ปกติ ไม่ว่าจะ classify จริงหรือแค่เช็คแล้วยังไม่ถึงรอบ, 1 = check_new_sar_image() ล้มเหลว)

endlocal
exit /b %JOB_EXIT_CODE%

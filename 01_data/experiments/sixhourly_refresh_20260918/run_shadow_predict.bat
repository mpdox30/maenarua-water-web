@echo off
REM ============================================================================
REM run_shadow_predict.bat
REM ----------------------------------------------------------------------------
REM Launcher สำหรับรัน shadow_predict.py บน Windows ผ่าน Task Scheduler
REM
REM 2026-09-18: shadow-test โมเดล inflow แบบ 6 ชั่วโมง (ผลจาก sixhourly_refresh_20260918/)
REM สคริปต์นี้แค่ "ทำนาย + บันทึกผล" เท่านั้น -- ไม่แตะ production pipeline / โมเดล daily ที่ deploy
REM จริงเลย และไม่ retrain โมเดลใหม่ทุกรอบ (โมเดลถูก freeze ไว้แล้วใน shadow_models/ ตอนตั้งค่า)
REM
REM ใช้ .venv เดียวกับ run_pipeline.bat ที่ D:\maenaruea-water-web\.venv
REM
REM ข้อมูลดิบ 6 ชั่วโมงมี mark ที่ 01:00 / 07:00 / 13:00 / 19:00 น. ทุกวัน -- ตั้ง schedule ให้รันหลัง
REM แต่ละ mark ~30 นาที (ให้เวลา telemetry sync เข้า api_snapshots.csv ก่อน)
REM
REM วิธีตั้ง Windows Task Scheduler (ทำครั้งเดียว) -- เปิด Command Prompt "Run as Administrator":
REM
REM   schtasks /create /tn "MaeNaRua_Inflow_ShadowTest_6h" ^
REM     /tr "\"D:\maenaruea-water-web\01_data\experiments\sixhourly_refresh_20260918\run_shadow_predict.bat\"" ^
REM     /sc DAILY /st 01:30 /ri 360 /du 23:59 /ru "%USERNAME%" /rl LIMITED /f
REM
REM   /st 01:30   = เริ่มรันครั้งแรกของวันตอน 01:30 (30 นาทีหลัง mark 01:00)
REM   /ri 360     = ทำซ้ำทุก 360 นาที (6 ชั่วโมง) หลังจากนั้น -> จะรันตอน 01:30, 07:30, 13:30, 19:30
REM   /du 23:59   = ทำซ้ำไปจนครบเกือบ 24 ชม. (กันชนกับรอบ 01:30 ของวันถัดไปที่ /sc DAILY จะสร้างให้เอง)
REM
REM   ลบ task ถ้าต้องการ (แนะนำให้ลบหลังครบ 1 เดือน shadow-test):
REM     schtasks /delete /tn "MaeNaRua_Inflow_ShadowTest_6h" /f
REM   ดูสถานะ:
REM     schtasks /query /tn "MaeNaRua_Inflow_ShadowTest_6h" /v /fo LIST
REM   รันทดสอบทันที (ไม่ต้องรอถึงรอบถัดไป):
REM     schtasks /run /tn "MaeNaRua_Inflow_ShadowTest_6h"
REM
REM หลังผ่านไป 1 เดือน ให้รัน score_shadow.py (ในโฟลเดอร์เดียวกัน) เพื่อดูผล NSE/MAE เทียบ persistence
REM   "D:\maenaruea-water-web\.venv\Scripts\python.exe" score_shadow.py
REM (รันได้เรื่อยๆ ระหว่างเดือนด้วยเพื่อดูความคืบหน้า horizon สั้นๆ จะมีผลให้ดูก่อน horizon ยาว)
REM ============================================================================

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "VENV_PYTHON=%SCRIPT_DIR%..\..\..\.venv\Scripts\python.exe"

echo ============================================================
echo   Mae Na Rua Inflow 6h Shadow-Test - run_shadow_predict.bat
echo   %DATE% %TIME%
echo ============================================================

if not exist "%VENV_PYTHON%" (
    echo [WARN] ไม่พบ .venv ที่ %VENV_PYTHON%
    echo [WARN] จะใช้ system Python แทน - แนะนำให้สร้าง .venv ก่อน ดูวิธีใน run_pipeline.bat
    set "VENV_PYTHON=C:\Python314\python.exe"
)

echo [INFO] Using Python: %VENV_PYTHON%
echo [INFO] Running shadow_predict.py (ทำนาย H1-H12, บันทึกลง shadow_predictions_log.csv) ...
echo.

cd /d "%SCRIPT_DIR%"
"%VENV_PYTHON%" shadow_predict.py
set "SHADOW_EXIT_CODE=%ERRORLEVEL%"

echo.
echo [INFO] shadow_predict.py exited with code %SHADOW_EXIT_CODE%
echo   (0 = สำเร็จหรือ skip เพราะยังไม่มี mark ใหม่, non-zero = error -- เช็ค log ด้านบน)

endlocal
exit /b %SHADOW_EXIT_CODE%

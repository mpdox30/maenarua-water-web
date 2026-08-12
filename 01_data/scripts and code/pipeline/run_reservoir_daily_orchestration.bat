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

REM ============================================================================
REM 2026-08-12 เพิ่ม -- push ไฟล์ทางการ + shadow CSV ขึ้น GitHub ทุกรอบที่รันสำเร็จ
REM
REM ก่อนหน้านี้สคริปต์นี้ไม่มีขั้นตอน git ใดๆ เลย -- ไฟล์ทางการรายเดือน (inflow/<year>/*.xlsx) และ
REM shadow CSV (RES002_daily_computed.csv) เขียนแค่บนดิสก์ทุกเช้า ไม่เคยขึ้น GitHub อัตโนมัติ ตรวจพบ
REM 2026-08-12 ว่า GitHub ค้างข้อมูลจริงถึง 26 วัน (shadow CSV) และ 10 วัน (ไฟล์ทางการเดือนปัจจุบัน)
REM ทั้งที่ดิสก์เครื่องนี้มีข้อมูลครบทุกวันปกติ -- แก้ด้วย pattern เดียวกับ run_pipeline.bat/
REM run_monitoring_data_builder.bat (pull --no-rebase ก่อน, add เฉพาะไฟล์ที่รู้จัก, commit/push
REM เฉพาะตอนมีอะไรเปลี่ยนจริง) ไฟล์ backup อัตโนมัติ (.bak_before_*) ถูก .gitignore กันไว้แล้ว จึง
REM git add ทั้งโฟลเดอร์ inflow/ ได้อย่างปลอดภัยโดยไม่ดึง backup ติดไปด้วย
REM ============================================================================
if not "%ORCH_EXIT_CODE%"=="0" (
    echo [WARN] reservoir_daily_orchestration.py ไม่สำเร็จ -- ข้ามขั้นตอน push git รอบนี้
    goto :SKIP_RESERVOIR_PUSH
)

pushd "%SCRIPT_DIR%..\..\..\"

if exist ".git\rebase-merge" goto :RESERVOIR_GIT_BUSY
if exist ".git\rebase-apply" goto :RESERVOIR_GIT_BUSY
if exist ".git\MERGE_HEAD" goto :RESERVOIR_GIT_BUSY

echo.
echo [INFO] sync กับ remote ก่อน push ไฟล์ทางการ + shadow CSV ...
git pull --no-rebase --no-edit origin master
if errorlevel 1 (
    echo [WARN] git pull --no-rebase ไม่สำเร็จ -- ข้ามขั้นตอน push รอบนี้ ^(ไม่ force/resolve เอง^)
    goto :RESERVOIR_GIT_DONE
)

git add "01_data/Reservoirs/inflow/"
git add "01_data/Reservoirs/inflow_auto/RES002_daily_computed.csv"
git diff --cached --quiet
if errorlevel 1 (
    git commit -m "Auto-update: reservoir official file + shadow CSV %DATE% %TIME%" >nul 2>&1
    git push origin master
    if errorlevel 1 (
        echo [WARN] push ไฟล์ทางการ/shadow CSV ไม่สำเร็จ -- จะลองใหม่รอบถัดไปอัตโนมัติ
    ) else (
        echo [OK] push ไฟล์ทางการ/shadow CSV สำเร็จ
    )
) else (
    echo [INFO] ไม่มีอะไรเปลี่ยนจากรอบก่อน -- ข้ามการ commit/push
)
goto :RESERVOIR_GIT_DONE

:RESERVOIR_GIT_BUSY
echo [WARN] เจอ rebase/merge ค้างอยู่ใน git -- ข้ามขั้นตอน push รอบนี้

:RESERVOIR_GIT_DONE
popd

:SKIP_RESERVOIR_PUSH

endlocal
exit /b %ORCH_EXIT_CODE%

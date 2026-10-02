@echo off
REM 2026-10-02 เพิ่ม -- บังคับ console code page เป็น UTF-8 (65001) ก่อนบรรทัดอื่นใด เพราะไฟล์นี้มี
REM path ที่มีอักษรไทย (D:\WMB_Phayao\...\บัญชีน้ำ\) ฝังอยู่ตรงๆ -- ถ้า cmd ยังใช้ code page เดิม
REM (OEM/ANSI เช่น 874) ตอนอ่านไฟล์ .bat นี้ (เซฟเป็น UTF-8 ไม่มี BOM) ตัวอักษรไทยในพาธจะถูกตีความ
REM ผิด กลายเป็น byte แปลกๆ ปนกับอักษรไทยบางตัว ทำให้ python หา path ไม่เจอ (No such file or
REM directory) ทั้งที่ path มีอยู่จริง -- เจอปัญหานี้จริงตอนรันครั้งแรก (2026-10-02) กับ
REM recompute_corrected_ledger.py ตั้ง chcp 65001 ให้ตรงกับ encoding ไฟล์ก่อน แก้ปัญหานี้ได้ทั้งหมด
chcp 65001 >nul
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

REM ============================================================================
REM 2026-09-08 เพิ่มชั่วคราว -- ปิด git pull/push (GIT_PUSH_ENABLED=0) ระหว่างทดสอบให้เว็บจริง
REM พึ่ง GitHub Actions (reservoir-orchestration.yml) เต็มตัว 1-2 วัน ตามที่ตกลงกับผู้ใช้
REM สคริปต์ยังคำนวณ + เขียนไฟล์ทางการ/shadow CSV ลงดิสก์ตามปกติทุกอย่าง แค่ไม่แตะ git เลย (ทั้ง
REM pull และ push) กันชนกับที่ GitHub Actions เขียน/push ไฟล์เดียวกันไปแล้ว (ปิด pull ด้วยเพราะถ้า
REM เปิด pull ทิ้งไว้แต่ไม่ commit ผลลัพธ์ตัวเอง ไฟล์ inflow/*.xlsx ที่เพิ่งเขียนสดจะชนกับ pull ได้
REM ถ้า Actions push ไฟล์เดือนเดียวกันมาก่อน)
REM
REM เปิดกลับ: เปลี่ยน GIT_PUSH_ENABLED เป็น 1 แล้วรันไฟล์นี้ใหม่ (จะ pull+push อัตโนมัติเหมือนเดิม)
REM หรือถ้า GitHub Actions มีปัญหาแล้วอยากดึงผลจากเครื่องนี้ไป push เองทันที (ไม่ต้องรอสคริปต์) เปิด
REM Command Prompt ที่ D:\maenaruea-water-web แล้วรัน:
REM   git add "01_data/Reservoirs/inflow/" "01_data/Reservoirs/inflow_auto/RES002_daily_computed.csv"
REM   git commit -m "Manual push from Windows (GitHub Actions issue)"
REM   git pull --no-rebase --no-edit origin master
REM   git push origin master
set "GIT_PUSH_ENABLED=1"
REM ============================================================================

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
REM 2026-10-01 เพิ่ม -- รี-เจน assets/data/water_ledger.json (หน้า water-balance.html) ทุกครั้งที่
REM เขียนไฟล์ทางการสำเร็จ เดิมต้องรัน build_water_ledger_json.py เองทุกวันแยกต่างหาก -- ย้ายมารวมที่นี่
REM เพราะ run_reservoir_daily_orchestration.bat เป็น job เดียวที่แก้ไฟล์ Excel บัญชีน้ำ (ต้นทางของ
REM water_ledger.json) ข้ามขั้นตอนนี้ถ้า orchestration ล้มเหลว (ไฟล์ Excel ไม่เปลี่ยน ไม่จำเป็นต้อง
REM รี-เจนซ้ำ) ความล้มเหลวของขั้นตอนนี้เองไม่ทำให้ ORCH_EXIT_CODE เปลี่ยน (ไม่ critical เท่าตัวเขียนไฟล์ทางการ)
REM
REM 2026-10-01 เพิ่ม (ต่อ) -- recompute_corrected_ledger.py ต้องรันก่อน build_water_ledger_json.py เสมอ
REM (สร้าง "ฉบับสูตรสปิลเวย์แก้ไข" ที่ D:\WMB_Phayao\01_raw_data\Reservoirs\บัญชีน้ำ\ จากไฟล์ทางการที่
REM เพิ่งเขียนด้านบน + telemetry รายชั่วโมงล่าสุด -- build_water_ledger_json.py เปลี่ยนมาอ่านโฟลเดอร์นี้
REM แทนไฟล์ทางการโดยตรงแล้ว ดู docstring ของ recompute_corrected_ledger.py สำหรับรายละเอียดสูตร/
REM การ sanity-check เต็มๆ -- อยู่คนละ drive (D:\WMB_Phayao) จึงเรียกด้วย full path ตรงๆ ไม่ cd ไปที่นั่น
REM (สคริปต์ hardcode path ของตัวเองไว้แล้วทั้งหมด ไม่ต้องพึ่ง cwd)
REM ============================================================================
if "%ORCH_EXIT_CODE%"=="0" (
    echo.
    echo [INFO] Rebuilding D:\WMB_Phayao\01_raw_data\Reservoirs\บัญชีน้ำ\ ^(สูตรสปิลเวย์แก้ไข^) ...
    "%VENV_PYTHON%" "D:\WMB_Phayao\01_raw_data\Reservoirs\บัญชีน้ำ\recompute_corrected_ledger.py"
    if errorlevel 1 (
        echo [WARN] recompute_corrected_ledger.py ล้มเหลว -- water_ledger.json รอบนี้จะใช้ผลลัพธ์เก่า
    ) else (
        echo [OK] ฉบับสูตรสปิลเวย์แก้ไขอัปเดตแล้ว
    )

    echo.
    echo [INFO] Rebuilding assets/data/water_ledger.json จากไฟล์บัญชีน้ำล่าสุด ...
    "%VENV_PYTHON%" build_water_ledger_json.py
    if errorlevel 1 (
        echo [WARN] build_water_ledger_json.py ล้มเหลว -- หน้า water-balance.html จะยังใช้ไฟล์ json เดิม
    ) else (
        echo [OK] water_ledger.json อัปเดตแล้ว
    )
) else (
    echo [INFO] ข้าม recompute_corrected_ledger.py / build_water_ledger_json.py รอบนี้ ^(orchestration
    echo   ไม่สำเร็จ, ไฟล์ Excel ไม่เปลี่ยน^)
)

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
if not "%GIT_PUSH_ENABLED%"=="1" (
    echo [INFO] Git pull/push ปิดอยู่ชั่วคราว ^(GIT_PUSH_ENABLED=0^) -- ข้ามขั้นตอน git ทั้งหมดรอบนี้
    echo   ^(ไฟล์ทางการ/shadow CSV ยังเขียนลงดิสก์ปกติ แค่ไม่ pull/push เฉยๆ^)
    goto :SKIP_RESERVOIR_PUSH
)

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
REM 2026-10-01 เพิ่ม -- commit/push water_ledger.json (หน้า water-balance.html) พร้อมกันไปเลย
REM เพราะสร้างมาจากไฟล์ทางการชุดเดียวกันด้านบน ไม่ต้องรอรอบ push แยก
git add "03_website/assets/data/water_ledger.json"
git diff --cached --quiet
if errorlevel 1 (
    git commit -m "Auto-update: reservoir official file + shadow CSV + water_ledger.json %DATE% %TIME%" >nul 2>&1
    git push origin master
    if errorlevel 1 (
        echo [WARN] push ไฟล์ทางการ/shadow CSV/water_ledger.json ไม่สำเร็จ -- จะลองใหม่รอบถัดไปอัตโนมัติ
    ) else (
        echo [OK] push ไฟล์ทางการ/shadow CSV/water_ledger.json สำเร็จ
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

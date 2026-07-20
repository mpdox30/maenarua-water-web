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

REM ============================================================================
REM 2026-07-20 เพิ่ม -- push monitoring.json ขึ้น GitHub ทุกรอบที่รันสำเร็จ
REM 2026-07-20 แก้ (รอบ 2) -- เอา "git pull --rebase --autostash" ออก เพราะเคยไปชนกับตอนที่แก้
REM history ของ repo ด้วยมือ (git filter-repo) พร้อมกัน จนเกิด rebase ค้างกลางคันแบบ conflict ใน
REM ไฟล์ข้อมูลอ่างเก็บน้ำทางการจริง (.xlsx) -- ตอนนี้แค่ "push เฉยๆ" ถ้าพลาด (เน็ตหลุด/remote ไปไกล
REM กว่าที่มี) ก็แค่ log เตือนแล้วปล่อยผ่าน รอบถัดไปอีก 10-15 นาทีจะ commit ทับ/push ใหม่เอง **ไม่มี
REM ขั้นตอนไหนที่แก้ history หรือ merge/rebase อัตโนมัติอีกต่อไป** ปลอดภัยกว่าเดิมแม้จะหมายความว่า
REM บางรอบอาจ push ไม่ทันถ้า remote เปลี่ยนบ่อย (ยอมรับได้ เพราะรอบถัดไปในไม่ช้าจะตามทัน)
REM
REM ก่อนหน้านี้ monitoring.json อัปเดตแค่บนดิสก์เครื่องนี้ ไม่เคยขึ้น git เลย ทำให้เว็บจริงบน
REM GitHub Pages (mpdox30.github.io) ค้างข้อมูลเก่า (ขึ้นป้าย "ข้อมูลหยุดนิ่ง" เพราะ freshness
REM check ในหน้า monitoring.html เทียบเวลาที่ห่างเกิน 2 ชม.) เพิ่มขั้นตอนนี้ให้ push ทุก 10-15 นาที
REM ตามรอบเดิมของ builder เอง (ต่างจากไฟล์อื่น เช่น reservoir_inflow.json ที่ push วันละครั้งผ่าน
REM Colab Cell 17 พอ เพราะ monitoring.json ตั้งใจให้ใกล้ real-time)
REM
REM ใช้ credential ที่ git บนเครื่องนี้ผูกไว้อยู่แล้ว (เครื่อง Windows จริง ไม่ใช่ Colab ที่ต้องใช้
REM Secret ต่างหาก) -- ถ้ายังไม่เคย push สำเร็จมาก่อนบนเครื่องนี้ ให้ลอง "git push" มือครั้งแรกก่อน
REM เพื่อให้ Windows Credential Manager จำ token ไว้ รอบถัดๆ ไปจากงานนี้จะไม่ถามซ้ำ
REM
REM เจตนา: git add เฉพาะไฟล์นี้ไฟล์เดียว (ไม่ใช้ git add -A) เพื่อไม่ให้ไปพ่วงไฟล์อื่นที่ scheduled
REM task อื่น (run_pipeline.bat, sync_to_drive.bat ฯลฯ) อาจกำลังแก้อยู่พร้อมกันโดยไม่ได้ตั้งใจ
REM ============================================================================
if not "%BUILDER_EXIT_CODE%"=="0" (
    echo [WARN] builder ไม่สำเร็จ ข้ามขั้นตอน push git รอบนี้
    goto :SKIP_GIT_PUSH
)

pushd "%SCRIPT_DIR%..\..\..\"

REM เช็คก่อนว่ามี rebase/merge ค้างอยู่จากรอบก่อนหรือคนกำลังแก้ conflict มืออยู่หรือไม่ -- ถ้ามี
REM ห้ามแตะ git เลยรอบนี้ (กันซ้ำเติมปัญหา) ปล่อยให้คนแก้ไขเองก่อน
if exist ".git\rebase-merge" goto :GIT_BUSY
if exist ".git\rebase-apply" goto :GIT_BUSY
if exist ".git\MERGE_HEAD" goto :GIT_BUSY

echo.
echo [INFO] กำลัง push monitoring.json ขึ้น GitHub ...

git add "03_website/assets/data/monitoring.json"
git diff --cached --quiet
if errorlevel 1 (
    git commit -m "Auto-update: monitoring.json %DATE% %TIME%" >nul 2>&1
    git push origin master
    if errorlevel 1 (
        echo [WARN] push monitoring.json ไม่สำเร็จ ^(เน็ตหลุด หรือ remote ไปไกลกว่าที่มี^) -- จะลองใหม่รอบถัดไปอัตโนมัติ ^(ไม่ pull/rebase เอง^)
    ) else (
        echo [OK] push monitoring.json สำเร็จ
    )
) else (
    echo [INFO] monitoring.json ไม่มีอะไรเปลี่ยนจากรอบก่อน ข้ามการ commit/push
)
goto :GIT_DONE

:GIT_BUSY
echo [WARN] เจอ rebase/merge ค้างอยู่ใน git -- ข้ามขั้นตอน push รอบนี้ทั้งหมด ^(ไปแก้ conflict มือก่อน แล้วรอบถัดไปจะกลับมา push ปกติเอง^)

:GIT_DONE
popd

:SKIP_GIT_PUSH

endlocal
exit /b %BUILDER_EXIT_CODE%

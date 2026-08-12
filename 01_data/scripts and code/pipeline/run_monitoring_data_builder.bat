@echo off
REM ============================================================================
REM run_monitoring_data_builder.bat
REM ----------------------------------------------------------------------------
REM Launcher สำหรับรัน monitoring_data_builder.py บน Windows ผ่าน Task Scheduler
REM ดึงข้อมูลโทรมาตรสด 4 สถานี (RES002/RES004/RES005/RES006) เขียนทับ
REM 03_website/assets/data/monitoring.json -- หน้า monitoring.html และการ์ด %ความจุ
REM บนหน้า index.html อ่านไฟล์นี้
REM
REM **2026-07-31 เพิ่ม**: รวม inflow_6h_display_estimate.py (Item 4 -- ประมาณการน้ำไหลเข้าสูงสุด 6 ชม.
REM แบบ display-only) เข้ามารันต่อท้ายในรอบเดียวกัน แทนที่จะแยกเป็น scheduled task ของตัวเอง เหตุผล:
REM   1) ทั้งสองสคริปต์ดึงข้อมูลจาก wide_log Google Sheet เดียวกัน -- รวมกันไม่ได้เสียอะไรเพิ่ม
REM      (แค่ HTTP GET ซ้อนกันสองรอบต่อเนื่องกัน ไม่ชนกัน)
REM   2) **ข้อสำคัญที่สุด**: ถ้าแยก task กัน แต่ละ task จะ pull/push git เป็นของตัวเองอิสระกัน --
REM      ถ้า schedule ใกล้กันโดยบังเอิญ (เช่นตั้งทุก 15 นาทีเหมือนกันทั้งคู่) จะมีโอกาสชนกันตอน push
REM      (task หนึ่ง push แล้วอีก task หนึ่งที่ pull ไปก่อนหน้าจะกลาย "behind" ทันที ต้อง pull ใหม่
REM      ถึงจะ push ได้ -- ไม่ error ร้ายแรงแต่ทำให้บางรอบ push ไม่ทันบ่อยขึ้นโดยไม่จำเป็น) รวมเป็น
REM      task เดียว = pull ครั้งเดียว + push ครั้งเดียวต่อรอบ ตัดความเสี่ยงนี้ไปเลย
REM   3) inflow_6h_display_estimate.py คำนวณหน้าต่างแบบปัดชั่วโมง -- รันถี่กว่า 1 ครั้ง/ชม. จะได้ผลลัพธ์
REM      เหมือนเดิมซ้ำๆ ภายในชั่วโมงเดียวกัน (ไม่ผิดอะไร แค่คำนวณซ้ำ คุ้มกว่าแยก task ต่างหาก)
REM ผลคือ: ไม่ต้องสร้าง scheduled task "MaeNaRua_Inflow6h_Display_Estimate" แยกอีกต่อไป --
REM run_inflow_6h_display_estimate.bat ยังใช้รันมือ/ทดสอบเดี่ยวๆ ได้ปกติ แค่ไม่ต้องเอาไปตั้ง schtasks เอง
REM
REM **2026-07-31 เพิ่มอีกตัว**: รวม forecast_accuracy_logger.py เข้ามาด้วย (บันทึก log เปรียบเทียบ
REM ค่าพยากรณ์ Q_in (h1-h7 จาก latest.json) กับค่าจริงที่คำนวณได้ภายหลัง (จาก
REM RES002_daily_computed.csv) ไว้ที่ 01_data/forecasting_results/Reservoir_inflow/
REM forecast_accuracy_log.csv สำหรับปรับจูนโมเดลในอนาคต) -- idempotent เหมือนกัน รันถี่กี่รอบก็ไม่มี
REM ผลข้างเคียง (แค่ no-op ถ้าไม่มีอะไรใหม่) เหตุผลที่รวมเข้ามาแทนแยก task เหมือนกับเหตุผลข้อ 2) ด้านบน
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
REM
REM ⚠️ ถ้าเคยสร้าง task "MaeNaRua_Inflow6h_Display_Estimate" แยกไว้ก่อนหน้านี้แล้ว ให้ลบทิ้งด้วย:
REM   schtasks /delete /tn "MaeNaRua_Inflow6h_Display_Estimate" /f
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

echo.
echo [INFO] Running inflow_6h_display_estimate.py (Item 4, display-only) ...
echo.

"%VENV_PYTHON%" inflow_6h_display_estimate.py
set "INFLOW_EXIT_CODE=%ERRORLEVEL%"

echo.
echo [INFO] inflow_6h_display_estimate.py exited with code %INFLOW_EXIT_CODE%
echo   (รันอิสระจาก monitoring_data_builder.py ด้านบน -- ตัวหนึ่งพังไม่บล็อกอีกตัว เพราะเขียนคนละไฟล์
echo    output กันคนละไฟล์ ไม่พึ่งพากัน)

echo.
echo [INFO] Running forecast_accuracy_logger.py (log predicted vs actual, display/tuning only) ...
echo.

"%VENV_PYTHON%" forecast_accuracy_logger.py
set "LOGGER_EXIT_CODE=%ERRORLEVEL%"

echo.
echo [INFO] forecast_accuracy_logger.py exited with code %LOGGER_EXIT_CODE%
echo   (อ่าน latest.json + RES002_daily_computed.csv อย่างเดียว เขียนแค่ forecast_accuracy_log.csv --
echo    ไม่แตะ/ไม่พึ่งพา 2 สคริปต์ด้านบน)

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
REM เจตนา: git add เฉพาะไฟล์ที่รู้จักตรงๆ (ไม่ใช้ git add -A) เพื่อไม่ให้ไปพ่วงไฟล์อื่นที่ scheduled
REM task อื่น (run_pipeline.bat, sync_to_drive.bat ฯลฯ) อาจกำลังแก้อยู่พร้อมกันโดยไม่ได้ตั้งใจ
REM
REM **2026-07-31**: ตอนนี้ push 3 ไฟล์ต่อรอบ (monitoring.json + inflow_6h_display.json +
REM forecast_accuracy_log.csv) ในรอบ pull/push เดียวกัน -- แต่ละไฟล์ add เฉพาะตอนที่สคริปต์ของมันสำเร็จ
REM (BUILDER_EXIT_CODE / INFLOW_EXIT_CODE / LOGGER_EXIT_CODE แยกกัน) ถ้าสำเร็จแค่บางตัวก็ยัง push
REM ตัวที่สำเร็จได้ตามปกติ ไม่ต้องรอให้ทั้งหมดสำเร็จพร้อมกัน
REM **2026-08-12 เพิ่ม**: forecast_accuracy_logger.py เขียนไฟล์ที่ 4 เพิ่ม (สำเนา log ไว้ที่
REM 03_website/assets/data/ ให้หน้า forecast-accuracy.html fetch() ได้) รวมเป็น 4 ไฟล์ต่อรอบ
REM ============================================================================
if not "%BUILDER_EXIT_CODE%"=="0" if not "%INFLOW_EXIT_CODE%"=="0" if not "%LOGGER_EXIT_CODE%"=="0" (
    echo [WARN] ทั้งสามสคริปต์ไม่สำเร็จเลย ข้ามขั้นตอน push git รอบนี้
    goto :SKIP_GIT_PUSH
)

pushd "%SCRIPT_DIR%..\..\..\"

REM เช็คก่อนว่ามี rebase/merge ค้างอยู่จากรอบก่อนหรือคนกำลังแก้ conflict มืออยู่หรือไม่ -- ถ้ามี
REM ห้ามแตะ git เลยรอบนี้ (กันซ้ำเติมปัญหา) ปล่อยให้คนแก้ไขเองก่อน
if exist ".git\rebase-merge" goto :GIT_BUSY
if exist ".git\rebase-apply" goto :GIT_BUSY
if exist ".git\MERGE_HEAD" goto :GIT_BUSY

REM ============================================================================
REM 2026-07-22 แก้ (รอบ 5 -- แก้จริง ไม่ใช่แค่ถอดออก): "git pull --ff-only" ที่เพิ่มไปตอนแรกเป็น
REM ต้นเหตุ outage จริง (monitoring.json หยุด push กว่า 1 ชม. ทั้งที่ monitoring_data_builder.py
REM ดึงข้อมูลสำเร็จปกติทุกรอบ) สาเหตุ: latest.json/flood_latest.json/reservoir_inflow.json ใน
REM 03_website/assets/data/ (+ 01_data/forecasting_results/latest.json) เป็นไฟล์ที่ Colab เท่านั้น
REM เป็นคน commit/push เอง (ผ่าน "Auto-update: pipeline data" แยกต่างหาก) แต่บนเครื่อง Windows นี้
REM ไฟล์พวกนี้ขึ้น "M" ค้างตลอดเวลา (Google Drive Desktop sync ดึงสิ่งที่ Colab เขียนลง Drive ลงมา
REM โดยไม่มีอะไรฝั่ง Windows คอย commit ให้ -- ปกติ ไม่ใช่บั๊ก) ทำให้ pull ชนกับไฟล์พวกนี้ทุกครั้งที่
REM Colab push ใหม่ (บ่อยมาก)
REM
REM ลองแค่ "ถอด pull ออก เอาแบบ push เฉยๆ" ก่อน (รอบ 4) แต่พบว่า**ไม่ self-heal จริงตามที่คิด**:
REM ถ้า remote เคยขยับไปครั้งหนึ่งแล้วไม่เคย pull ตามเลย local จะค้าง "behind" ถาวร แล้ว push จะ
REM ถูก reject ซ้ำทุกรอบไปเรื่อยๆ ไม่มีทางหลุดเองได้ (ยืนยันจากการทดสอบจริง 2026-07-22 09:25 --
REM ต้องแก้มือจึงจะหลุด) จึงกลับมาต้อง pull อยู่ดี แต่แก้ให้ปลอดภัยกับไฟล์ 4 ไฟล์ที่รู้แน่ชัดแล้วว่า
REM ไม่ใช่ของ task นี้แทน (ไม่ใช้ --ff-only ด้วย เพราะ true divergence จริงๆ ก็ยังพบว่า ff-only
REM ทำอะไรไม่ได้ ต้อง merge จริง — ใช้ "git pull --no-rebase" ปลอดภัยคนละแบบกับ --rebase ที่เคย
REM ทำให้ค้างกลางคันจากอุบัติเหตุครั้งก่อน: merge ที่ conflict จริงจะ fail แบบ non-interactive
REM ทันที ทิ้ง .git/MERGE_HEAD ไว้ให้ guard ด้านบนจับได้ในรอบถัดไป ไม่ค้างกลางคันแบบ rebase)
REM
REM ขั้นตอน: 1) เลิกไฟล์ 4 ไฟล์ที่รู้ว่าไม่ใช่ของ task นี้ก่อน (เสีย local copy ไปก็ไม่กระทบอะไร --
REM Colab เขียนใหม่ผ่าน Drive sync ซ้ำอยู่แล้ว) 2) pull --no-rebase (merge จริง ไม่ใช่ ff-only)
REM 3) ถ้า pull ยัง fail อยู่ (เช่นเจอไฟล์ที่ไม่รู้จักอีกตัวที่ dirty+conflict) แค่ warn แล้วข้าม push
REM รอบนี้ไป (ปลอดภัย ไม่ force อะไร)
REM ============================================================================
git checkout -- "03_website/assets/data/latest.json" "03_website/assets/data/flood_latest.json" "03_website/assets/data/reservoir_inflow.json" "01_data/forecasting_results/latest.json" 2>nul

echo.
echo [INFO] sync กับ remote ก่อน push (merge จริง ไม่ใช่ ff-only -- ปลอดภัยคนละแบบกับ rebase) ...
git pull --no-rebase --no-edit origin master
if errorlevel 1 (
    echo [WARN] git pull --no-rebase ไม่สำเร็จ ^(อาจเจอ conflict จริงในไฟล์อื่นที่ไม่รู้จัก^) -- ข้ามขั้นตอน push รอบนี้ทั้งหมด ^(ไม่ force/resolve เอง^) ถ้าเจอ .git/MERGE_HEAD ค้าง guard ด้านบนจะจับได้เองรอบถัดไป
    goto :GIT_DONE
)

echo.
echo [INFO] กำลัง add ไฟล์ที่อัปเดตสำเร็จขึ้น git (monitoring.json / inflow_6h_display.json / forecast_accuracy_log.csv แล้วแต่ตัวไหนสำเร็จ) ...

if "%BUILDER_EXIT_CODE%"=="0" git add "03_website/assets/data/monitoring.json"
if "%INFLOW_EXIT_CODE%"=="0" git add "03_website/assets/data/inflow_6h_display.json"
REM 2026-08-12 เพิ่ม -- forecast_accuracy_logger.py ตอนนี้เขียน 2 ไฟล์ (log หลัก + สำเนาให้เว็บ
REM forecast-accuracy.html fetch() ได้ตรงๆ ดู WEBSITE_LOG_CSV ในสคริปต์) ต้อง git add ทั้งคู่ ไม่งั้น
REM หน้าเว็บจะค้างข้อมูลเก่าถาวรเพราะสำเนาไม่เคยถูก push
if "%LOGGER_EXIT_CODE%"=="0" git add "01_data/forecasting_results/Reservoir_inflow/forecast_accuracy_log.csv"
if "%LOGGER_EXIT_CODE%"=="0" git add "03_website/assets/data/forecast_accuracy_log.csv"

git diff --cached --quiet
if errorlevel 1 (
    git commit -m "Auto-update: monitoring.json + inflow_6h_display.json + forecast_accuracy_log.csv %DATE% %TIME%" >nul 2>&1
    git push origin master
    if errorlevel 1 (
        echo [WARN] push ไม่สำเร็จ ^(เน็ตหลุด หรือ remote ไปไกลกว่าที่มี^) -- จะลองใหม่รอบถัดไปอัตโนมัติ ^(ไม่ pull/rebase เอง^)
    ) else (
        echo [OK] push สำเร็จ
    )
) else (
    echo [INFO] ไม่มีอะไรเปลี่ยนจากรอบก่อนในทุกไฟล์ ข้ามการ commit/push
)
goto :GIT_DONE

:GIT_BUSY
echo [WARN] เจอ rebase/merge ค้างอยู่ใน git -- ข้ามขั้นตอน push รอบนี้ทั้งหมด ^(ไปแก้ conflict มือก่อน แล้วรอบถัดไปจะกลับมา push ปกติเอง^)

:GIT_DONE
popd

:SKIP_GIT_PUSH

REM exit code รวม: 0 เฉพาะตอนที่ทั้งสามสคริปต์สำเร็จ -- ถ้าอย่างใดอย่างหนึ่งพัง ให้ non-zero เพื่อให้
REM Task Scheduler เห็นว่ารอบนี้ "ไม่สมบูรณ์" แม้ git จะ push ไฟล์ที่สำเร็จไปแล้วก็ตาม
set "COMBINED_EXIT_CODE=%BUILDER_EXIT_CODE%"
if not "%INFLOW_EXIT_CODE%"=="0" set "COMBINED_EXIT_CODE=%INFLOW_EXIT_CODE%"
if not "%LOGGER_EXIT_CODE%"=="0" set "COMBINED_EXIT_CODE=%LOGGER_EXIT_CODE%"

endlocal & exit /b %COMBINED_EXIT_CODE%

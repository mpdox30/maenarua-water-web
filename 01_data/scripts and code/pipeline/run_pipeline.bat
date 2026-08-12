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

REM ============================================================================
REM 2026-08-12 เพิ่ม -- push ml_features_live.csv ขึ้น GitHub ทุกรอบที่มีแถวใหม่จริง
REM
REM ก่อนหน้านี้ไฟล์นี้ไม่เคยถูก push อัตโนมัติเลย (เขียนแค่บนดิสก์ + sync ขึ้น Google Drive ผ่าน
REM sync_to_drive.bat เท่านั้น) ทำให้ประวัติสัปดาห์จริงบน git ตกหล่นได้ง่ายและไม่มีใครรู้จนกว่าจะมาเช็ค
REM มือ (เกิดขึ้นจริง 2 ครั้ง: สัปดาห์ 27-29 หายไปเงียบๆ ตั้งแต่ ก.ค. จนกระทั่งเจอ 12 ส.ค., แล้วยังเกือบ
REM ซ้ำอีกรอบตอนแก้ปัญหานั้นเพราะสคริปต์ backfill ฝั่ง Colab เขียนจากไฟล์คนละชุดกันแล้ว push ทับของจริง)
REM เพิ่มขั้นตอนนี้ให้ไฟล์นี้เข้า git ทุกรอบที่ data_pipeline.py รันสำเร็จ (เหมือน monitoring.json/
REM forecast_accuracy_log.csv ใน run_monitoring_data_builder.bat) ตัดการพึ่งพา manual sync ทิ้งไปเลย
REM
REM ใช้ pattern เดียวกับ run_monitoring_data_builder.bat: เช็ค rebase/merge ค้างก่อน, pull --no-rebase
REM (merge จริง ไม่ force), add เฉพาะไฟล์นี้ไฟล์เดียว, commit+push เฉพาะตอนมีอะไรเปลี่ยนจริง
REM ============================================================================
if not "%PIPELINE_EXIT_CODE%"=="0" if not "%PIPELINE_EXIT_CODE%"=="1" (
    echo [WARN] data_pipeline.py ล้มเหลวรุนแรง ^(exit code %PIPELINE_EXIT_CODE%^) -- ข้ามขั้นตอน push git
    goto :SKIP_ML_FEATURES_PUSH
)

pushd "%SCRIPT_DIR%..\..\..\"

if exist ".git\rebase-merge" goto :ML_FEATURES_GIT_BUSY
if exist ".git\rebase-apply" goto :ML_FEATURES_GIT_BUSY
if exist ".git\MERGE_HEAD" goto :ML_FEATURES_GIT_BUSY

echo.
echo [INFO] sync กับ remote ก่อน push ml_features_live.csv ...
git pull --no-rebase --no-edit origin master
if errorlevel 1 (
    echo [WARN] git pull --no-rebase ไม่สำเร็จ -- ข้ามขั้นตอน push รอบนี้ ^(ไม่ force/resolve เอง^)
    goto :ML_FEATURES_GIT_DONE
)

git add "01_data/scripts and code/pipeline/ml_features_live.csv"
git diff --cached --quiet
if errorlevel 1 (
    git commit -m "Auto-update: ml_features_live.csv %DATE% %TIME%" >nul 2>&1
    git push origin master
    if errorlevel 1 (
        echo [WARN] push ml_features_live.csv ไม่สำเร็จ -- จะลองใหม่รอบถัดไปอัตโนมัติ
    ) else (
        echo [OK] push ml_features_live.csv สำเร็จ
    )
) else (
    echo [INFO] ml_features_live.csv ไม่มีอะไรเปลี่ยนจากรอบก่อน -- ข้ามการ commit/push
)
goto :ML_FEATURES_GIT_DONE

:ML_FEATURES_GIT_BUSY
echo [WARN] เจอ rebase/merge ค้างอยู่ใน git -- ข้ามขั้นตอน push ml_features_live.csv รอบนี้

:ML_FEATURES_GIT_DONE
popd

:SKIP_ML_FEATURES_PUSH

endlocal
exit /b %PIPELINE_EXIT_CODE%

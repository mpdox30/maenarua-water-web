@echo off
REM ============================================================
REM sync_to_drive.bat
REM ============================================================
REM Mirror โฟลเดอร์โปรเจกต์ 2 ตัว (maenaruea-water-web, WMB_Phayao) จาก D:\ ไปยัง
REM Google Drive for Desktop (G:\My Drive\...) ให้ Colab อ่านข้อมูล/โมเดล/reference file
REM ล่าสุดได้เสมอ โดยไม่ต้อง copy มือซ้ำทุกครั้ง
REM
REM ทำไมใช้ robocopy /MIR แทนการ sync ทั้งโฟลเดอร์แบบ live ต่อเนื่อง (Google Drive for Desktop
REM sync client ตรงๆ): เพราะ .git ที่ sync ต่อเนื่องด้วย client ทั่วไปเสี่ยง repo พัง และ Task
REM Scheduler งานอื่นเขียนไฟล์รัวๆ พร้อมกับ sync client อ่านไฟล์เดียวกันเสี่ยงข้อมูลไม่ครบ — ใช้
REM copy แบบ batch (รันจบเป็นรอบๆ ไม่ใช่ watch ต่อเนื่อง) ปลอดภัยกว่า (ดู
REM COLAB_MIGRATION_PLAN.md หัวข้อ 2.4 สำหรับเหตุผลเต็ม)
REM
REM /XD .git .venv __pycache__  -> ไม่แตะโฟลเดอร์เหล่านี้เลย (ไม่ copy ไป ไม่ลบปลายทางถ้ามีอยู่แล้ว)
REM   เพราะ .venv เป็น Windows-only binary ไม่มีประโยชน์บน Colab, .git ไม่ควร sync ผ่าน client ทั่วไป
REM /MIR -> ทำให้ปลายทางตรงกับต้นทางเป๊ะ (ไฟล์ที่ลบจากต้นทางจะถูกลบจากปลายทางด้วย ไม่ใช่แค่เพิ่มไฟล์ใหม่)
REM
REM วิธีใช้ 2 แบบ (เลือกอย่างใดอย่างหนึ่ง ไม่ต้องทำทั้งคู่):
REM   (ก) รันมือ: ดับเบิลคลิกไฟล์นี้ก่อนเปิด Colab ทุกครั้งที่อยากได้ข้อมูลล่าสุดแน่ๆ
REM   (ข) ตั้ง Task Scheduler อัตโนมัติ (ดูคำสั่ง schtasks ท้ายไฟล์นี้ในคอมเมนต์)
REM
REM ข้อควรระวัง: ถ้าตั้งเป็น Task Scheduler ให้รันช่วงเช้าวันจันทร์ (ตรงกับ
REM MaeNaRua_Pipeline_Weekly 02:00 / MaeNaRua_SAR_Background_Job 03:00) sync อาจไปชนกับตอนที่
REM งานเหล่านั้นกำลังเขียนไฟล์อยู่พอดี (โอกาสต่ำ แต่ถ้าเกิดขึ้นได้แค่ snapshot ไม่ครบรอบเดียว ไม่ทำให้
REM ไฟล์ต้นทางบน D:\ เสียหาย) แนะนำตั้งเวลารันหลัง 08:00 ทุกวันเป็นอย่างน้อย (เผื่อ
REM MaeNaRua_Reservoir_Daily_Orchestration ที่รัน 07:30 ทุกวันให้เสร็จก่อน)
REM ============================================================

setlocal enabledelayedexpansion

set "SRC_WEB=D:\maenaruea-water-web"
set "DST_WEB=G:\My Drive\Colab Notebooks\Mae_Na_Rua\maenaruea-water-web"
set "SRC_WMB=D:\WMB_Phayao"
set "DST_WMB=G:\My Drive\Colab Notebooks\Mae_Na_Rua\WMB_Phayao"
set "LOG=%~dp0sync_to_drive.log"

echo ===== sync_to_drive.bat เริ่มรัน %date% %time% ===== > "%LOG%"

echo กำลัง sync maenaruea-water-web ...
robocopy "%SRC_WEB%" "%DST_WEB%" /MIR /XD .git .venv __pycache__ /R:2 /W:5 /NP /LOG+:"%LOG%"
set RC_WEB=%ERRORLEVEL%

echo กำลัง sync WMB_Phayao ...
robocopy "%SRC_WMB%" "%DST_WMB%" /MIR /XD .git .venv __pycache__ /R:2 /W:5 /NP /LOG+:"%LOG%"
set RC_WMB=%ERRORLEVEL%

echo ===== sync_to_drive.bat จบ %date% %time% (RC_WEB=%RC_WEB% RC_WMB=%RC_WMB%) ===== >> "%LOG%"

REM robocopy exit code: 0-7 = สำเร็จ (รวม "มีการเปลี่ยนแปลง"/"มีไฟล์เกิน" ซึ่งเป็นปกติ)
REM                     8 ขึ้นไป = มีไฟล์/โฟลเดอร์ที่ copy ไม่สำเร็จจริง (error)
set FAILED=0
if %RC_WEB% GEQ 8 set FAILED=1
if %RC_WMB% GEQ 8 set FAILED=1

if %FAILED%==1 (
    echo [ERROR] sync ล้มเหลวบางส่วน — ดู %LOG% สำหรับรายละเอียด (RC_WEB=%RC_WEB% RC_WMB=%RC_WMB%^)
    exit /b 1
) else (
    echo [OK] sync เสร็จแล้ว ^(RC_WEB=%RC_WEB% RC_WMB=%RC_WMB%^) ดูรายละเอียดที่ %LOG%
    exit /b 0
)

REM ============================================================
REM ตั้ง Task Scheduler อัตโนมัติ (ทำครั้งเดียว) — เปิด Command Prompt "Run as Administrator"
REM แล้ววางคำสั่งนี้ (รันทุกวัน 08:15 — หลัง MaeNaRua_Reservoir_Daily_Orchestration 07:30 เสร็จแน่ๆ):
REM
REM schtasks /create /tn "MaeNaRua_Sync_To_Drive" ^
REM   /tr "\"D:\maenaruea-water-web\01_data\scripts and code\colab_migration\sync_to_drive.bat\"" ^
REM   /sc DAILY /st 08:15 /ru "%USERNAME%" /rl LIMITED /f
REM
REM ดูสถานะ:  schtasks /query /tn "MaeNaRua_Sync_To_Drive" /fo LIST /v
REM รันทดสอบทันที:  schtasks /run /tn "MaeNaRua_Sync_To_Drive"
REM ลบ task:  schtasks /delete /tn "MaeNaRua_Sync_To_Drive" /f
REM ============================================================

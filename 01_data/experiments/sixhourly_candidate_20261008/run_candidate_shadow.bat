@echo off
REM รันรุ่นผู้สมัคร shadow: (1) ดึง IMERG Late/Early (2) ทำนาย+บันทึก candidate_predictions_log.csv
REM ใช้ .venv ของ repo ที่ไฟล์นี้อยู่ (ไม่ผูกชื่อโฟลเดอร์) -- ใช้ได้ทั้ง D:\maenaruea-water-web และ D:\maenarua-water-web
REM รันบนเครื่องเดียวเท่านั้น (เครื่อง 2 ที่เปิดช่วงเย็น-เช้า) เพื่อให้ log อยู่ไฟล์เดียว:
REM   schtasks /create /tn "MaeNaRua_Candidate6h_Shadow" /tr "\"D:\maenarua-water-web\01_data\experiments\sixhourly_candidate_20261008\run_candidate_shadow.bat\"" /sc DAILY /st 18:30 /ri 360 /du 12:30 /ru "%USERNAME%" /rl LIMITED /f
REM   (18:30, 00:30, 06:30 -- ครอบคลุมทั้ง 4 mark/วัน: mark 07:00 และ 13:00 ถูกบันทึกรอบ 18:30, mark 19:00 รอบ 00:30, mark 01:00 รอบ 06:30)
chcp 65001 >nul
set "PY=%~dp0..\..\..\.venv\Scripts\python.exe"
cd /d "%~dp0"
"%PY%" fetch_imerg_early_earthaccess.py
"%PY%" shadow_candidate.py

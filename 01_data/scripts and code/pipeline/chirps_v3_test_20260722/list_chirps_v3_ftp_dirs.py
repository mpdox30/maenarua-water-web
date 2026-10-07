# -*- coding: utf-8 -*-
"""
list_chirps_v3_ftp_dirs.py — chirps_v3_test_20260722 (สคริปต์วินิจฉัยเฉพาะกิจ, รอบ 2 — แก้บั๊ก)

รอบแรกพบว่าใต้ .../v3.0/daily/ มี "prelim" คู่กับ "final" จริง (ทั้งคู่มีแค่ subfolder "sat" ข้างใน
อีกที ไม่ใช่ปีตรงๆ) แต่สคริปต์รอบแรกมี 2 บั๊ก: (1) เช็ค path "prelim" เฉยๆ ไม่ได้ต่อ "/sat" เข้าไป
เหมือน final (2) หยิบโฟลเดอร์ปีที่ชื่อมากสุดตามลำดับตัวอักษร (sorted()[-1]) โดยไม่เช็คว่ามีไฟล์จริง
ไหม ไปเจอโฟลเดอร์ปีอนาคตที่ว่างเปล่า (เช่น "2030") ก่อน — รอบนี้แก้เป็นไล่จากปีมากสุดถอยหลังจนกว่า
จะเจอปีที่มีไฟล์ .tif จริงอย่างน้อย 1 ไฟล์

ใช้งาน (จากโฟลเดอร์นี้): python list_chirps_v3_ftp_dirs.py
"""
from ftplib import FTP

FTP_HOST = "ftp.chc.ucsb.edu"
BASE = "/pub/org/chc/products/CHIRPS/v3.0"


def connect():
    ftp = FTP(FTP_HOST, timeout=60)
    ftp.login()
    ftp.set_pasv(True)
    return ftp


def latest_nonempty_year_files(ftp: FTP, path: str):
    """ไล่โฟลเดอร์ปีจากมากสุดถอยหลัง จนเจอปีแรกที่มีไฟล์ .tif อย่างน้อย 1 ไฟล์ คืน (ปี, ไฟล์ที่เรียงแล้ว)"""
    ftp.cwd(path)
    years = sorted((y for y in ftp.nlst() if y.isdigit()), reverse=True)
    for y in years:
        ftp.cwd(f"{path}/{y}")
        files = sorted(f for f in ftp.nlst() if f.lower().endswith(".tif"))
        if files:
            return y, files
    return None, []


ftp = connect()

for label, path in [("FINAL/sat", f"{BASE}/daily/final/sat"), ("PRELIM/sat", f"{BASE}/daily/prelim/sat")]:
    try:
        year, files = latest_nonempty_year_files(ftp, path)
        if year is None:
            print(f"{label}: ไม่เจอปีไหนที่มีไฟล์เลย (เช็ค path: {path})")
            continue
        print(f"{label}: ปีล่าสุดที่มีไฟล์จริง = {year} | จำนวนไฟล์ = {len(files)}")
        print("  ไฟล์ล่าสุด 8 ไฟล์:")
        for f in files[-8:]:
            print("   ", f)
        print()
    except Exception as exc:
        print(f"{label}: error ({exc})\n")

ftp.quit()

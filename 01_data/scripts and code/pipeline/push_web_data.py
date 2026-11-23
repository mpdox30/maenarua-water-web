# -*- coding: utf-8 -*-
"""push_web_data.py -- ฝั่งโน๊ตบุ๊ค: คัดลอก flood_latest.json (จาก WMB) ลงเว็บ แล้ว commit+push ไฟล์ข้อมูลเว็บใน allowlist
(ชุดเดียวกับที่ Colab push) -- เดิม run_all_laptop.bat push เฉพาะ last_run/latest/ml_features ทำให้ flood_latest.json,
reservoir_inflow.json, water_ledger.json ฯลฯ ที่เครื่องสร้างไม่ขึ้นเว็บ (พบ 2026-11-08)
ใช้: python push_web_data.py [--web D:\\maenaruea-water-web] [--wmb D:\\WMB_Phayao]"""
import argparse, json, shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "colab_migration"))
import run_extras_colab as rx
ap = argparse.ArgumentParser()
ap.add_argument("--web", default=r"D:\maenaruea-water-web"); ap.add_argument("--wmb", default=r"D:\WMB_Phayao")
a = ap.parse_args()
src = Path(a.wmb) / "09_live" / "output" / "flood_latest.json"
dst = Path(a.web) / "03_website" / "assets" / "data" / "flood_latest.json"
try:
    g = lambda p: json.load(open(p, encoding="utf-8")).get("generated_at", "")
    if src.exists() and (not dst.exists() or g(src) >= g(dst)):
        shutil.copy(src, dst); print("flood_latest.json: copy จาก WMB", g(src))
except Exception as e:
    print("copy flood_latest.json ไม่สำเร็จ:", e)
ok = rx.push_repo(a.web, rx.WEB_PREFIXES, "master", None, f"Auto-update: web data {rx._now():%Y-%m-%d %H:%M} (laptop)")
sys.exit(0 if ok else 1)

# -*- coding: utf-8 -*-
"""push_wmb_data.py -- ฝั่งโน๊ตบุ๊ค: commit+push ข้อมูลสะสมของ WMB_Phayao (ชุดเดียวกับที่ Colab push) แล้ว sync กับ remote
เดิม run_all_laptop.bat ทำแค่ git pull WMB ซึ่งพังเมื่อมีไฟล์ข้อมูลแก้ค้างในเครื่อง และเครื่องไม่เคย push ข้อมูลสะสม WMB เลย
ทำให้ Colab เริ่มจากข้อมูล WMB เก่า  ใช้: python push_wmb_data.py [--wmb D:\\WMB_Phayao]   (ไม่ใช้ token: ใช้ credential ของ git บนเครื่อง)
ลำดับ: commit ไฟล์ข้อมูลใน allowlist -> pull (ไฟล์ที่ชนกัน ฝั่งเครื่องชนะ) -> push   ไม่แตะไฟล์ที่อยู่นอก allowlist
"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "colab_migration"))
import run_extras_colab as rx
ap = argparse.ArgumentParser(); ap.add_argument("--wmb", default=r"D:\WMB_Phayao"); a = ap.parse_args()
ok = rx.push_repo(a.wmb, rx.WMB_PREFIXES, "main", None, f"Auto-update: WMB live data {rx._now():%Y-%m-%d %H:%M} (laptop)")
sys.exit(0 if ok else 1)

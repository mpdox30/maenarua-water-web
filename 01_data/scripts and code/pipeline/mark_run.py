# -*- coding: utf-8 -*-
"""mark_run.py -- ฝั่งโน๊ตบุ๊ค: เขียน/ตรวจ 01_data/run_state/last_run.json (ตัวเดียวกับที่ Colab ใช้)
  python mark_run.py --check      เตือนถ้า Colab เพิ่งอัปเดตครบภายใน 5 ชม. (ไม่บล็อก -- โน๊ตบุ๊คมีสิทธิ์รันทับเสมอ)
  python mark_run.py --done STEP=ok STEP2=exit1 ...   บันทึกผลรอบนี้ (host=laptop)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "colab_migration"))
import run_extras_colab as rx
WEB = Path(__file__).resolve().parents[3]
if "--check" in sys.argv:
    st = rx.read_state(str(WEB))
    print("[state] ล่าสุด:", st.get("host"), st.get("finished_bkk"), "complete=", st.get("complete"),
          "| ครบล่าสุด:", st.get("last_complete_host"), st.get("last_complete_bkk"))
    if not rx.guard(str(WEB), host="laptop"):
        print("[WARN] Colab เพิ่งรันครบ -- โน๊ตบุ๊คจะรันทับต่อ (ผลใหม่กว่าจะชนะ)")
elif "--done" in sys.argv:
    steps = dict(a.split("=", 1) for a in sys.argv[sys.argv.index("--done") + 1:] if "=" in a)
    rx.write_state(str(WEB), "laptop", steps, all(v == "ok" for v in steps.values()))
    print("[state] บันทึกแล้ว:", steps)

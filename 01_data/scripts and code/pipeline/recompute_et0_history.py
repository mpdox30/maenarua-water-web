# -*- coding: utf-8 -*-
"""
recompute_et0_history.py  (2026-10-08)
คำนวณ ET0/T/RH/VPD/u2/Rn ย้อนหลังใหม่ด้วย era5t_worker.py ที่แก้แล้ว (ssr/str = sum ชั่วโมง 01..12 UTC)
แล้ว (ตัวเลือก) แก้ค่าในคอลัมน์ ET0_mm_week,T_mean,RH_pct,VPD_kPa,u2_ms,Rn_MJ ของ ml_features_live.csv

ขั้น 1  ดึง+คำนวณ (resume ได้ ข้ามสัปดาห์ที่มี json แล้ว; ใช้ Python ที่มี cdsapi+cfgrib เช่น env era5-grib ของ ArcGIS Pro):
    python recompute_et0_history.py --start 2025-01-05 --end 2026-10-04
ขั้น 2  ตรวจ summary (พิมพ์ท้ายขั้น 1 และเก็บที่ era5t_output_fixed/summary.csv) ว่า ET0 ~15-30 mm/สัปดาห์ และ Rn ~5-12 MJ
ขั้น 3  ใช้ค่าใหม่กับ ml_features_live.csv (สำรองไฟล์เดิมให้):
    python recompute_et0_history.py --apply
"""
import argparse, csv, json, os, shutil, subprocess, sys
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "era5t_output_fixed"
CSV = HERE / "ml_features_live.csv"
COLS = ["ET0_mm_week", "T_mean", "RH_pct", "VPD_kPa", "u2_ms", "Rn_MJ"]


def sundays(a, b):
    d = a + timedelta(days=(6 - a.weekday()) % 7)  # อาทิตย์แรก >= a
    while d <= b:
        yield d
        d += timedelta(days=7)


def _env():
    # เหมือน data_pipeline._fetch_era5t_via_subprocess(): ให้ eccodes หา DLL ของ conda env เจอ
    root = Path(sys.executable).parent
    e = os.environ.copy()
    e["CONDA_PREFIX"] = str(root); e["ECCODES_DIR"] = str(root)
    e["PATH"] = f"{root / 'Library' / 'bin'}{os.pathsep}{e.get('PATH', '')}"
    return e


def run_fetch(a, b):
    OUT.mkdir(exist_ok=True)
    for s in sundays(a, b):
        j = OUT / f"era5t_week_{s.isoformat()}.json"
        if j.exists():
            try:
                if json.loads(j.read_text(encoding="utf-8")).get("n_days_in_week") == 7:
                    continue
            except Exception:
                pass
        print(f"[fetch] {s} ...", flush=True)
        subprocess.run([sys.executable, str(HERE / "era5t_worker.py"), "--as-of-date", s.isoformat(),
                        "--out-json", str(j)], check=False, env=_env())
    rows = []
    for j in sorted(OUT.glob("era5t_week_*.json")):
        w = json.loads(j.read_text(encoding="utf-8"))
        rows.append({"as_of_date": j.stem.replace("era5t_week_", ""), "n_days": w.get("n_days_in_week"),
                     **{c: w.get(c) for c in COLS}})
    with open(OUT / "summary.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys())); wr.writeheader(); wr.writerows(rows)
    ok = [r for r in rows if r["n_days"] == 7 and r["ET0_mm_week"] is not None]
    print(f"\nสัปดาห์ครบ 7 วัน {len(ok)}/{len(rows)}")
    if ok:
        et = [r["ET0_mm_week"] for r in ok]; rn = [r["Rn_MJ"] for r in ok]
        print(f"ET0 mm/wk: min {min(et):.1f} mean {sum(et)/len(et):.1f} max {max(et):.1f}")
        print(f"Rn MJ/day: min {min(rn):.1f} mean {sum(rn)/len(rn):.1f} max {max(rn):.1f}")


def apply_fix():
    """แก้ทุกแถวที่ ISO week ตรงกับสัปดาห์ที่มี json ครบ 7 วัน (รวมแถวรายวันที่ as_of ไม่ใช่วันอาทิตย์ — ใช้ค่าทั้งสัปดาห์แทนค่า partial เดิม)"""
    new = {}
    for j in OUT.glob("era5t_week_*.json"):
        w = json.loads(j.read_text(encoding="utf-8"))
        if w.get("n_days_in_week") == 7 and w.get("ET0_mm_week") is not None and not w.get("is_rolling_estimate"):
            d = date.fromisoformat(j.stem.replace("era5t_week_", ""))
            new[d.isocalendar()[:2]] = w
    if not new:
        sys.exit("ไม่มี json ครบ 7 วันให้ใช้")
    bak = CSV.with_name(CSV.stem + f".bak_before_et0fix_{datetime.now():%Y%m%d%H%M%S}.csv")
    shutil.copy(CSV, bak); print("สำรอง ->", bak.name)
    with open(CSV, newline="", encoding="utf-8") as f:
        rd = csv.DictReader(f); fields = rd.fieldnames; rows = list(rd)
    n = 0; left = set()
    for r in rows:
        try:
            k = date.fromisoformat(r["as_of_date"]).isocalendar()[:2]
        except Exception:
            continue
        w = new.get(k)
        if w:
            for c in COLS:
                r[c] = w[c]
            if "era5t_n_days_in_week" in r: r["era5t_n_days_in_week"] = 7
            if "era5t_is_rolling_estimate" in r: r["era5t_is_rolling_estimate"] = False
            if "era5t_fetch_error" in r: r["era5t_fetch_error"] = ""
            n += 1
        elif r["as_of_date"] >= "2025-01-01":
            left.add(r["as_of_date"])
    with open(CSV, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=fields); wr.writeheader(); wr.writerows(rows)
    print(f"แก้ {n} แถว จาก {len(rows)}")
    print("as_of_date ที่ยังเป็นค่าเก่า (สัปดาห์ไม่ครบ/ปัจจุบัน):", sorted(left))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start"); ap.add_argument("--end"); ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if a.apply:
        apply_fix()
    else:
        if not (a.start and a.end):
            ap.error("ต้องระบุ --start และ --end (YYYY-MM-DD) หรือใช้ --apply")
        run_fetch(date.fromisoformat(a.start), date.fromisoformat(a.end))

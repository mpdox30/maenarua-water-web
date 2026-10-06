r"""
pull_weathernext_hindcast.py
============================
ดึง hindcast ฝนจาก Google WeatherNext 2 (Earth Engine) ที่จุดอ่างแม่นาเรือ
เพื่อใช้ทำ bias correction + เป็นฟีเจอร์ฝนล่วงหน้าของโมเดล 6 ชม.
(การทดลองเท่านั้น -- ไม่ยุ่งกับ production / shadow model)

Asset : projects/gcp-public-data-weathernext/assets/weathernext_2_0_0
Band  : total_precipitation_6hr (เมตร ต่อ 6 ชม.)  -> คูณ 1000 เป็น มม.
Init  : 00/06/12/18Z   Lead: 6 ชม. ถึง 15 วัน   64 ensemble members, 0.25 deg (~27.8 กม.)
จุด   : TARGET_LAT/LON = (19.05, 99.80) เดียวกับ chirps_feature.py (ตรวจพิกัดอ่างจริงอีกครั้งก่อนใช้จริง)

วิธีรัน (บนเครื่องที่ ee.Authenticate() ด้วยบัญชี Google ที่กรอกฟอร์ม WeatherNext แล้ว):

  1) ตรวจสิทธิ์ก่อน (ไม่ดึงข้อมูลจริง):
       python pull_weathernext_hindcast.py --probe
  2) ทดสอบพายุ 5 ต.ค. 2569 (init 4-5 ต.ค.):
       python pull_weathernext_hindcast.py --start 2026-10-04 --end 2026-10-06 --out wn_storm_test.csv
  3) ดึงช่วงเทรน (ต่อจากไฟล์เดิมได้เอง resume):
       python pull_weathernext_hindcast.py --start 2025-08-01 --end 2026-10-06 --out wn_hindcast_2025-08_2026-10.csv

ผลลัพธ์ต่อแถว = 1 init x 1 lead: ค่าสถิติข้าม 64 members (mean, std, p10, p50, p90, max, prob>=1/5/10 มม./6ชม.)
ทั้งจุด pixel เดียว (pt_) และค่าเฉลี่ย 3x3 pixel (bx_)
ข้อมูล Historic (>48 ชม.) = CC BY 4.0 / Real-time (<=48 ชม.) = GDM Real-Time Terms of Use
ผลที่เผยแพร่ต้องอ้างอิงตามเงื่อนไขในหน้า catalog
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import sys
import time
from pathlib import Path

ASSET = "projects/gcp-public-data-weathernext/assets/weathernext_2_0_0"
BAND = "total_precipitation_6hr"
GEE_PROJECT = "maenaruea-water-pipeline"
TARGET_LAT, TARGET_LON = 19.05, 99.80
PIXEL_M = 27830
DEFAULT_LEADS = list(range(6, 6 * 13, 6))  # 6..72 ชม. (12 leads) -- เพิ่มได้ด้วย --max-lead
INITS_HOURS = (0, 6, 12, 18)

COLS = ["init_utc", "lead_h", "valid_end_utc", "n_members"]
for p in ("pt", "bx"):
    COLS += [f"{p}_mean_mm", f"{p}_std_mm", f"{p}_p10_mm", f"{p}_p50_mm", f"{p}_p90_mm", f"{p}_max_mm",
             f"{p}_prob_ge1", f"{p}_prob_ge5", f"{p}_prob_ge10"]


def init_ee(personal: bool = False):
    import ee
    if personal:
        # ใช้บัญชีส่วนตัวที่ผ่าน allowlist (ไม่ใช้ service account ของ pipeline)
        try:
            ee.Initialize(project=GEE_PROJECT)
        except Exception as exc:
            print(f"[auth] ยังไม่ได้ login ({exc}) -> เปิด browser ให้ login ด้วยบัญชีที่กรอกฟอร์ม WeatherNext")
            ee.Authenticate()
            ee.Initialize(project=GEE_PROJECT)
        print("[auth] personal_credential")
        return ee
    here = Path(__file__).resolve().parent
    pipe = here.parents[1] / "scripts and code" / "pipeline"
    sys.path.insert(0, str(pipe))
    try:
        from gee_auth import init_ee as _init
        mode = _init(GEE_PROJECT)
        print(f"[auth] {mode}")
    except Exception as exc:  # fallback เรียกตรง
        print(f"[auth] gee_auth ใช้ไม่ได้ ({exc}) -> ee.Initialize ตรงๆ")
        ee.Initialize(project=GEE_PROJECT)
    return ee


def probe(ee) -> int:
    print(f"[probe] asset = {ASSET}")
    try:
        coll = ee.ImageCollection(ASSET)
        last = coll.sort("system:time_start", False).first()
        props = last.toDictionary(["start_time", "end_time", "forecast_hour", "ensemble_member"]).getInfo()
        print("[probe] OK เข้าถึง collection ได้; image ล่าสุด:", props)
    except Exception as exc:
        print("[probe] FAIL:", exc)
        print("  -> ถ้าเป็น 'permission' / 'not found' แปลว่าบัญชีที่ใช้ยังไม่ได้อยู่ใน allowlist\n"
              "     (สิทธิ์ผูกกับบัญชีที่กรอกฟอร์ม; service account ต้องได้รับเพิ่มแยกต่างหาก)")
        return 1
    # ทดสอบ query ฝนจุดเดียว
    init = dt.datetime(2026, 10, 5, 0)
    rows = pull_one(ee, init, [6, 12, 18, 24])
    for r in rows:
        print(f"[probe] init {r['init_utc']} +{r['lead_h']}h  pt_mean={r['pt_mean_mm']:.2f} mm "
              f"p90={r['pt_p90_mm']:.2f}  members={r['n_members']}")
    return 0


def _iso(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def pull_one(ee, init: dt.datetime, leads: list[int]) -> list[dict]:
    """ดึงสถิติ ensemble ของฝน 6 ชม. ที่จุดสำหรับ init เดียว (หลาย lead) ด้วยการเรียก EE ครั้งเดียว"""
    pt = ee.Geometry.Point([TARGET_LON, TARGET_LAT])
    box = pt.buffer(PIXEL_M * 1.5).bounds()
    coll = (ee.ImageCollection(ASSET)
            .filter(ee.Filter.eq("start_time", _iso(init)))
            .select(BAND))

    reducer = (ee.Reducer.mean().combine(ee.Reducer.stdDev(), sharedInputs=True)
               .combine(ee.Reducer.percentile([10, 50, 90]), sharedInputs=True)
               .combine(ee.Reducer.max(), sharedInputs=True))

    def per_lead(h):
        h = ee.Number(h)
        members = coll.filter(ee.Filter.eq("forecast_hour", h)).map(lambda im: im.multiply(1000.0))  # mm
        stat = members.reduce(reducer)
        # ความน่าจะเป็นเกินเกณฑ์ ต่อ pixel = สัดส่วน members
        def thr(t):
            return members.map(lambda im: im.gte(t)).mean().rename(f"prob_ge{t}")
        probs = ee.Image.cat([thr(1), thr(5), thr(10)])
        img = ee.Image.cat([stat, probs])
        f_pt = img.reduceRegion(ee.Reducer.first(), pt, PIXEL_M)
        f_bx = img.reduceRegion(ee.Reducer.mean(), box, PIXEL_M)
        return ee.Feature(None, {"h": h, "n": members.size(), "pt": f_pt, "bx": f_bx})

    fc = ee.FeatureCollection(ee.List(leads).map(per_lead)).getInfo()
    out = []
    for f in fc["features"]:
        p = f["properties"]
        h = int(p["h"])
        row = {"init_utc": _iso(init), "lead_h": h,
               "valid_end_utc": _iso(init + dt.timedelta(hours=h)), "n_members": p["n"]}
        for tag in ("pt", "bx"):
            d = p[tag] or {}
            g = lambda k: d.get(f"{BAND}_{k}", d.get(k))
            row.update({
                f"{tag}_mean_mm": g("mean"), f"{tag}_std_mm": g("stdDev"),
                f"{tag}_p10_mm": g("p10"), f"{tag}_p50_mm": g("p50"), f"{tag}_p90_mm": g("p90"),
                f"{tag}_max_mm": g("max"),
                f"{tag}_prob_ge1": d.get("prob_ge1"), f"{tag}_prob_ge5": d.get("prob_ge5"),
                f"{tag}_prob_ge10": d.get("prob_ge10"),
            })
        out.append(row)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--personal", action="store_true",
                    help="ใช้ personal credential (บัญชีที่ผ่าน allowlist) แทน service account")
    ap.add_argument("--start", help="วันแรกของ init (UTC) YYYY-MM-DD")
    ap.add_argument("--end", help="วันสุดท้าย (ไม่รวม) YYYY-MM-DD")
    ap.add_argument("--out", default="wn_hindcast.csv")
    ap.add_argument("--max-lead", type=int, default=72, help="lead สูงสุด (ชม.) ทีละ 6")
    ap.add_argument("--inits", default="0,6,12,18", help="ชั่วโมง init ที่ต้องการ เช่น 0,12")
    ap.add_argument("--sleep", type=float, default=0.2)
    a = ap.parse_args()

    ee = init_ee(a.personal)
    if a.probe:
        return probe(ee)
    if not (a.start and a.end):
        ap.error("ต้องระบุ --start และ --end (หรือใช้ --probe)")

    leads = list(range(6, a.max_lead + 1, 6))
    hours = [int(x) for x in a.inits.split(",")]
    out = Path(a.out)
    if not out.is_absolute():
        out = Path(__file__).resolve().parent / out

    done = set()
    if out.exists():
        with out.open(encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                done.add(r["init_utc"])
    new_file = not out.exists()

    d0 = dt.datetime.strptime(a.start, "%Y-%m-%d")
    d1 = dt.datetime.strptime(a.end, "%Y-%m-%d")
    inits = [d0 + dt.timedelta(days=i, hours=h) for i in range((d1 - d0).days) for h in hours]
    todo = [t for t in inits if _iso(t) not in done]
    print(f"[plan] init ทั้งหมด {len(inits)} | เสร็จแล้ว {len(inits) - len(todo)} | ที่เหลือ {len(todo)} "
          f"| leads {leads[0]}-{leads[-1]}h")

    fails = 0
    with out.open("a", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        if new_file:
            w.writeheader()
        for i, t in enumerate(todo, 1):
            for attempt in range(3):
                try:
                    rows = pull_one(ee, t, leads)
                    break
                except Exception as exc:
                    rows = None
                    print(f"  ! {_iso(t)} ครั้งที่ {attempt + 1}: {exc}")
                    time.sleep(3 * (attempt + 1))
            if not rows:
                fails += 1
                continue
            w.writerows(rows)
            fh.flush()
            if i % 20 == 0 or i == len(todo):
                print(f"  [{i}/{len(todo)}] {_iso(t)} ok (fail {fails})")
            time.sleep(a.sleep)
    print(f"[done] {out} | fail={fails} (รันซ้ำได้ ระบบข้าม init ที่เสร็จแล้ว)")
    return 0 if fails == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

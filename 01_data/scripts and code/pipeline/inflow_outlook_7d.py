"""inflow_outlook_7d.py -- พยากรณ์น้ำไหลเข้าอ่างแม่นาเรือ 7 วันข้างหน้า (production)

  3 วันแรก  = โมเดล 6 ชม. (GBM, 12 horizon x 6 ชม.)  จาก shadow_predictions_log.csv
  4 วันที่เหลือ = โมเดลรายวันเดิม (CatBoost h4-h7)         จาก latest.json -> forecasts.inflow.forecast.horizons
  ผลลัพธ์ -> 03_website/assets/data/inflow_outlook_7d.json   (หน้าเว็บ ukm.js อ่านไฟล์นี้ ถ้าไม่มี/เก่าเกิน -> ใช้กราฟรายวันเดิม)

ใช้:  python inflow_outlook_7d.py [--run-model-if-due] [--out PATH]
  --run-model-if-due  ถ้า mark 6 ชม. ล่าสุด (01/07/13/19 น. + 30 นาที) ยังไม่มีในล็อก ให้รัน shadow_predict.py ก่อน
                      (ใช้ตอนเรียกจาก run_monitoring_data_builder.bat ทุก 15 นาที -- ไม่ต้องตั้ง Scheduled Task เพิ่ม)
exit code: 0 = เขียนไฟล์ใหม่ หรือไม่มีอะไรต้องเปลี่ยน ; 1 = ข้าม (ไม่มีล็อก/ล็อกเก่าเกิน/ข้อมูลไม่ครบ) -- ไม่ทับไฟล์เดิม
หน่วย: ลบ.ม./6 ชม. (โมเดลรายวัน ลบ.ม./วัน ส่งออกทั้งสองหน่วย)
"""
import argparse, csv, json, os, subprocess, sys, time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EXP = ROOT / "01_data" / "experiments" / "sixhourly_refresh_20260918"
LOG = EXP / "shadow_predictions_log.csv"
LATEST = ROOT / "03_website" / "assets" / "data" / "latest.json"
OUT_DEFAULT = ROOT / "03_website" / "assets" / "data" / "inflow_outlook_7d.json"
ATTEMPT_FILE = Path(__file__).resolve().parent / "logs" / "outlook_last_model_attempt.txt"
MARKS = [1, 7, 13, 19]
MAX_AGE_H = 18          # ล็อกเก่ากว่านี้ = ไม่ส่งออก (หน้าเว็บจะ fallback)
LOW_CONF_FROM_H = 9     # H9-H12 NSE ต่ำ/ไม่นิ่ง (ดู candidate/active scoring) -> ติดป้ายความเชื่อมั่นต่ำ


def last_logged_issued():
    if not LOG.exists():
        return None
    last = None
    with open(LOG, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            last = r
    return last


def latest_due_mark(now):
    """mark ล่าสุดที่ผ่านมาแล้วอย่างน้อย 30 นาที (ให้ telemetry sync ทัน)"""
    t = now - timedelta(minutes=30)
    for back in range(0, 30):
        c = (t - timedelta(hours=back)).replace(minute=0, second=0, microsecond=0)
        if c.hour in MARKS and c <= t:
            return c
    return None


def maybe_run_model():
    now = datetime.now()
    due = latest_due_mark(now)
    last = last_logged_issued()
    have = datetime.fromisoformat(last["issued_at"]) if last else None
    if due is None or (have is not None and have >= due):
        return
    try:  # อย่ารันซ้ำถี่ ๆ ถ้าเพิ่งลองไป (ล้ม/ข้อมูลยังไม่เข้า)
        if ATTEMPT_FILE.exists() and time.time() - ATTEMPT_FILE.stat().st_mtime < 20 * 60:
            print("[outlook] เพิ่งลองรันโมเดลไปไม่ถึง 20 นาที -- ข้ามรอบนี้")
            return
        ATTEMPT_FILE.parent.mkdir(parents=True, exist_ok=True)
        ATTEMPT_FILE.write_text(now.isoformat(), encoding="utf-8")
    except Exception:
        pass
    print(f"[outlook] mark {due:%Y-%m-%d %H:%M} ยังไม่มีในล็อก -> รัน shadow_predict.py")
    try:
        r = subprocess.run([sys.executable, "shadow_predict.py"], cwd=str(EXP), timeout=900,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        tail = (r.stdout or "").strip().splitlines()[-3:] + (r.stderr or "").strip().splitlines()[-3:]
        print("[outlook] shadow_predict exit", r.returncode, "|", " / ".join(tail)[:300])
    except Exception as e:
        print("[outlook] รัน shadow_predict ไม่สำเร็จ:", e)


def build():
    last = last_logged_issued()
    if not last:
        print("[outlook] ไม่มีล็อก 6 ชม. -- ข้าม"); return None
    issued = datetime.fromisoformat(last["issued_at"])
    age_h = (datetime.now() - issued).total_seconds() / 3600
    if age_h > MAX_AGE_H:
        print(f"[outlook] ล็อกล่าสุด {issued} เก่า {age_h:.1f} ชม. (> {MAX_AGE_H}) -- ข้าม ไม่ทับไฟล์เดิม"); return None
    gbm = []
    for h in range(1, 13):
        tgt, q = last.get(f"h{h}_target_datetime"), last.get(f"h{h}_pred_qin")
        if not tgt or q in (None, ""):
            print(f"[outlook] ล็อกขาด h{h} -- ข้าม"); return None
        te = datetime.fromisoformat(tgt)
        gbm.append({"h": h, "window_start": (te - timedelta(hours=6)).isoformat(), "window_end": te.isoformat(),
                    "q_6h_m3": round(max(0.0, float(q)), 1), "family": last.get(f"h{h}_family") or "",
                    "low_confidence": h >= LOW_CONF_FROM_H})
    daily = {"as_of_date": None, "days": []}
    try:
        lat = json.load(open(LATEST, encoding="utf-8"))
        f = lat["forecasts"]["inflow"]["forecast"]
        asof = datetime.fromisoformat(f["as_of_date"])
        daily["as_of_date"] = f["as_of_date"]
        daily["status"] = lat["forecasts"]["inflow"].get("status")
        daily["staleness_status"] = f.get("staleness_status")
        for h in range(4, 8):
            p = (f.get("horizons") or {}).get(f"h{h}")
            if not p:
                continue
            qd = max(0.0, float(p["prediction_m3_per_day"]))
            daily["days"].append({"h": h, "date": (asof + timedelta(days=h)).date().isoformat(),
                                  "q_day_m3": round(qd, 1), "q_6h_avg_m3": round(qd / 4, 1),
                                  "low_confidence": bool(p.get("low_confidence")), "model": p.get("model_name")})
    except Exception as e:
        print("[outlook] อ่านโมเดลรายวันจาก latest.json ไม่ได้:", e)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "issued_at": issued.isoformat(),
        "run_at": last.get("run_at"),
        "unit": "m3_per_6h",
        "now": {"time": issued.isoformat(), "q_6h_m3": round(float(last["persistence_qin_now"]), 1)},
        "gbm": gbm,
        "daily": daily,
        "notes": [
            "3 วันแรก: โมเดล 6 ชม. (GBM) รายช่วง 6 ชม. 12 ช่วง · วันที่ 4–7: โมเดลรายวันเดิม แสดงเป็นค่าเฉลี่ยต่อ 6 ชม. (ค่าต่อวัน ÷ 4)",
            "ช่วงที่ 9–12 (54–72 ชม.) ความแม่นยำลดลง/ไม่นิ่ง ติดป้ายความเชื่อมั่นต่ำ · ใช้เป็นแนวโน้ม ไม่ใช่ประกาศทางการ",
        ],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-model-if-due", action="store_true")
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    a = ap.parse_args()
    if a.run_model_if_due:
        maybe_run_model()
    data = build()
    if not data:
        return 1
    out = Path(a.out)
    try:  # ไม่เขียนทับถ้า issued_at / ข้อมูลรายวันเหมือนเดิม -> ไม่เกิด commit ว่างทุก 15 นาที
        old = json.load(open(out, encoding="utf-8"))
        if old.get("issued_at") == data["issued_at"] and old.get("daily") == data["daily"]:
            print("[outlook] ไม่มีอะไรเปลี่ยน (issued_at เดิม)"); return 0
    except Exception:
        pass
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, out)
    print(f"[outlook] เขียน {out} (issued {data['issued_at']}, GBM {len(data['gbm'])} ช่วง + รายวัน {len(data['daily']['days'])} วัน)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

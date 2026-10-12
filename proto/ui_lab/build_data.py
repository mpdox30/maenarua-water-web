# -*- coding: utf-8 -*-
"""สร้าง data.js (snapshot ข้อมูลจริงจาก 03_website/assets/data) ให้ prototype เปิดจากไฟล์ได้เลย ไม่ต้องมีเซิร์ฟเวอร์
รัน:  python build_data.py   (อ่านอย่างเดียว ไม่แก้ไฟล์ production)"""
import json, os
from datetime import datetime, timedelta
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "03_website", "assets", "data"))
L = lambda f: json.load(open(os.path.join(SRC, f), encoding="utf-8"))
mon, led, w6, lat, fl = L("monitoring.json"), L("water_ledger.json"), L("inflow_6h_display.json"), L("latest.json"), L("flood_latest.json")

stations = []
for s in mon["stations"]:
    stations.append({k: s.get(k) for k in ("station_code", "name_th", "spillway_msl", "water_level", "rainfall_1h", "measure_datetime", "storage_m3", "storage_max_m3", "capacity_pct")} |
                    {"history": (s.get("history") or [])[-120:], "rain": (s.get("rainfall_hourly") or [])[-72:]})
rows = led["rows"][-45:]
ledger = [{"date": r["date"], "level": r["water_level_m"], "volume": r["water_volume_m3"], "inflow": r["inflow_m3"],
           "release": (r.get("outlet_release_m3") or 0) + (r.get("spill_m3") or 0), "spill": r.get("spill_m3") or 0, "rain": r.get("rain_24h_mm") or 0} for r in rows]
allrows = led["rows"]
inf = lat["forecasts"]["inflow"]["forecast"]
asof = datetime.fromisoformat(inf["as_of_date"])
fc = [{"date": asof.strftime("%Y-%m-%d"), "h": 0, "v": inf["current_qin_m3_per_day"]}]
for h in range(1, 8):
    p = inf["horizons"].get("h%d" % h)
    if p: fc.append({"date": (asof + timedelta(days=h)).strftime("%Y-%m-%d"), "h": h, "v": p["prediction_m3_per_day"], "low": bool(p.get("low_confidence"))})
data = {
    "snapshot": datetime.now().isoformat(timespec="seconds"),
    "monitoring_updated": mon["meta"]["updated"],
    "capacity_m3": 1625000, "crest": 489.545, "max_level_seen": max(r["water_level_m"] for r in allrows),
    "stations": stations, "ledger": ledger, "windows": w6["windows"], "forecast": fc,
    "kwan": {"level": fl["kwan_now"]["level"], "change_3d": fl["kwan_now"]["change_3d"], "bank": fl["banks"]["Mae_Main1"], "bank_ronghai": fl["banks"]["RongHai"], "flag": fl["flags"]["overall"], "generated_at": fl["generated_at"]},
}
open(os.path.join(HERE, "data.js"), "w", encoding="utf-8").write("window.PROTO_DATA = " + json.dumps(data, ensure_ascii=False) + ";\n")
print("data.js สร้างแล้ว:", os.path.getsize(os.path.join(HERE, "data.js")) // 1024, "KB ; snapshot", data["snapshot"])

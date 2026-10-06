"""เทียบฝน WeatherNext (WN2/WN3) กับฝนเกจ RES002 ช่วงพายุ 5 ต.ค. 2569 (เวลาในไฟล์เกจ = เวลาไทย UTC+7)"""
import os, pandas as pd
H = os.path.dirname(os.path.abspath(__file__))
tel = pd.read_csv(os.path.join(H, "..", "..", "Reservoirs", "inflow_auto", "telemetry_backfill_20260910_20261005.csv"),
                  parse_dates=["measure_datetime"])
tel["utc"] = tel.measure_datetime - pd.Timedelta(hours=7)
g = tel.set_index("utc").RES002_rainfall_1h
# rolling-1h gauge, ค่าที่ ณ นาที :00 = ฝนสะสม 1 ชม. ที่จบชั่วโมงนั้น
gh = g[g.index.minute == 0]
w3 = pd.read_csv(os.path.join(H, "wn3_storm_test.csv"), parse_dates=["init_utc", "valid_end_utc"])
for c in ("init_utc","valid_end_utc"): w3[c]=w3[c].dt.tz_localize(None)
w2 = pd.read_csv(os.path.join(H, "wn2_storm_test.csv"), parse_dates=["init_utc", "valid_end_utc"])
for c in ("init_utc","valid_end_utc"): w2[c]=w2[c].dt.tz_localize(None)

print("== gauge rain_1h (mm) ending each UTC hour, 5 Oct 03Z-12Z ==")
print(gh["2026-10-05 03:00":"2026-10-05 09:00"].round(1).to_string())
peak_t = gh["2026-10-05"].idxmax(); peak = gh["2026-10-05"].max()
print(f"gauge peak: {peak:.1f} mm/h ending {peak_t} UTC")
s6 = gh["2026-10-05 06:00"] if pd.Timestamp("2026-10-05 06:00") in gh.index else None
win = pd.date_range("2026-10-05 00:00", "2026-10-05 08:00", freq="1h")
gauge6 = gh.reindex(win)
# 6h รวมแบบไม่ซ้อน: ฝนจริง 00-06Z = sum ชั่วโมง 01..06
gauge_00_06 = gh.reindex(pd.date_range("2026-10-05 01:00", "2026-10-05 06:00", freq="1h")).sum()
gauge_06_12 = gh.reindex(pd.date_range("2026-10-05 07:00", "2026-10-05 09:00", freq="1h")).sum()
print(f"gauge sum 01-06Z = {gauge_00_06:.1f} mm ; 07-09Z (ถึงข้อมูลสุดท้าย) = {gauge_06_12:.1f} mm")

print("\n== WN3 0.1deg: ฝนชั่วโมงที่จบ 06Z (12-13 ไทย) และยอดรวมช่วง 05-07Z, ต่อ init ==")
rows = []
for init, d in w3.groupby("init_utc"):
    d = d.set_index("valid_end_utc")
    v = lambda c, t: d.loc[pd.Timestamp(t), c] if pd.Timestamp(t) in d.index else float("nan")
    peak_row = d.loc["2026-10-05 01:00":"2026-10-05 12:00", "pt_total_precipitation_1hr_mean_mm"]
    rows.append(dict(init=init, lead_to_06Z=int((pd.Timestamp("2026-10-05 06:00") - init) / pd.Timedelta(hours=1)),
        mean_06Z=v("pt_total_precipitation_1hr_mean_mm", "2026-10-05 06:00"),
        p90_06Z=v("pt_total_precipitation_1hr_p90_mm", "2026-10-05 06:00"),
        imerg_06Z=v("pt_imerg_tp_1hr_mean_mm", "2026-10-05 06:00"),
        bx_mean_06Z=v("bx_total_precipitation_1hr_mean_mm", "2026-10-05 06:00"),
        sum_mean_01_12Z=peak_row.sum(),
        peak_hr_mean=peak_row.max(), peak_at=str(peak_row.idxmax())[11:16] if len(peak_row) else ""))
t3 = pd.DataFrame(rows)
print(t3[t3.lead_to_06Z > 0].round(2).to_string(index=False))

print("\n== WN2 (64 members, 6h window ending 06Z = 00-06Z) ==")
r2 = w2[w2.valid_end_utc == "2026-10-05 06:00"].copy()
print(r2[["init_utc", "lead_h", "pt_mean_mm", "pt_p90_mm", "pt_max_mm", "bx_mean_mm", "pt_prob_ge10"]].round(2).to_string(index=False))
print(f"gauge 01-06Z sum = {gauge_00_06:.1f} mm")
t3.to_csv(os.path.join(H, "storm_compare_wn3.csv"), index=False)

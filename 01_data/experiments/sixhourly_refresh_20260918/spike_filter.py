# -*- coding: utf-8 -*-
"""
spike_filter.py  (2026-10-06)
=============================
กรอง "spike ชั่วคราว" ของระดับน้ำรายชั่วโมง RES002 ก่อนเอาไปคำนวณ Q_in 6 ชม. ใน shadow_predict.py

ที่มา: ช่วง 10 ส.ค. - 6 ก.ย. 2569 มี 18 หน้าต่าง 6 ชม. ที่ระดับน้ำพุ่ง/ตกชั่วคราวแล้วย้อนกลับใน 4-8 ชม. โดยไม่มี
ฝน (เช่น 27 ส.ค. 13:00 +38 ซม. ใน 1 ชม. แล้ว -37 ซม. ตอน 17:00) สูตร Q_in ตัดค่าลบเป็น 0 แต่ปล่อยค่าบวก จึงได้
"น้ำไหลเข้า" ปลอมสูงสุด ~200k ม3/6ชม. (ดู experiments/sixhourly_stormfix_20261006/FINDINGS.md)

2 ขั้น (ไม่แก้ค่าเกจในไฟล์ดิบเลย -- กรองเฉพาะกริดชั่วโมงในหน่วยความจำ):
 1) RETRO  : หา "bump" ช่วง 2-8 ชม. ที่ระดับขึ้น (หรือลง) จากเส้นฐานเชื่อมจุดหัว-ท้าย >= 0.15 ม. แล้วกลับมาที่เดิม
             (|ท้าย-หัว| <= 50% ของความสูง bump) -> แทนด้วยเส้นตรงระหว่างจุดหัว-ท้าย
             เงื่อนไขกันกรองของจริง: (ก) ระดับสูงสุดในช่วง < สันฝาย-2 ซม. (ถ้าน้ำล้นสปิลเวย์ ระดับตกกลับเร็วได้จริง)
             (ข) สำหรับ bump ขาขึ้น ฝนรวม 2 ชม.ก่อนเริ่มถึงยอด < 2 มม. (ถ้ามีฝน การขึ้นเป็นของจริง)
 2) HOLD   : ส่วนหางที่ยังไม่รู้ผล (ชั่วโมงล่าสุด) -- ถ้ากระโดด >= 0.25 ม./ชม. โดยไม่มีฝน และยังอยู่ใต้สันฝาย ให้ "ค้างค่าเดิม"
             ไว้ไม่เกิน 6 ชม. เพื่อรอพิสูจน์ (ถ้ายืนเกิน 6 ชม. ถือว่าจริง ปล่อยตามค่าจริง) -- ปิดได้ด้วย hold=False

ส่ง hourly_level / hourly_rain เป็น dict {datetime(ชั่วโมงเต็ม): ค่าหรือ None}  คืน (dict ใหม่, รายการเหตุการณ์ที่แก้)
"""
from __future__ import annotations

from datetime import timedelta

CREST_M = 489.545


def despike_hourly(hourly_level, hourly_rain, *, crest=CREST_M, rise_min=0.15, max_len=8,
                   retrace_frac=0.5, rain_gate_mm=2.0, hold=True, hold_jump=0.25, hold_max=6,
                   hold_rain_gate_mm=1.0):
    ts = sorted(hourly_level)
    L = [hourly_level[t] for t in ts]
    R = [(hourly_rain.get(t) or 0.0) for t in ts]
    n = len(ts)
    events = []
    cap = crest - 0.02

    a = 0
    while a < n - 2:
        if L[a] is None:
            a += 1
            continue
        best = None  # (excess, b, sign)
        for b in range(a + 2, min(n, a + max_len + 1)):
            if L[b] is None:
                continue
            span = b - a
            interior = range(a + 1, b)
            if any(L[i] is None for i in interior):
                continue
            base = [L[a] + (L[b] - L[a]) * (i - a) / span for i in interior]
            exc = [L[i] - bs for i, bs in zip(interior, base)]
            up, dn = max(exc), -min(exc)
            sign, ex = (1, up) if up >= dn else (-1, dn)
            if ex < rise_min or abs(L[b] - L[a]) > retrace_frac * ex:
                continue
            if max(L[a:b + 1]) >= cap:
                continue
            if sign == 1:
                ipk = a + 1 + exc.index(up)
                if sum(R[max(a - 1, 0):ipk + 1]) >= rain_gate_mm:   # มีฝนก่อน/ระหว่างขึ้น = ของจริง
                    continue
            if best is None or ex > best[0]:
                best = (ex, b, sign)
        if best is None:
            a += 1
            continue
        ex, b, sign = best
        span = b - a
        for i in range(a + 1, b):
            L[i] = L[a] + (L[b] - L[a]) * (i - a) / span
        events.append({"kind": "bump" if sign == 1 else "dip", "start": ts[a + 1], "end": ts[b - 1],
                       "excess_m": round(ex, 3)})
        a = b

    if hold:
        # หางที่ยังไม่รู้ผล: หา jump ล่าสุดภายใน hold_max ชม. สุดท้าย
        lo = max(1, n - hold_max)
        for s in range(lo, n):
            if L[s] is None or L[s - 1] is None:
                continue
            if L[s] - L[s - 1] >= hold_jump and L[s] < cap and sum(R[max(s - 2, 0):s + 1]) < hold_rain_gate_mm:
                held = L[s - 1]
                for i in range(s, n):
                    if L[i] is not None and L[i] - held > 0.5 * hold_jump:
                        L[i] = held
                events.append({"kind": "hold", "start": ts[s], "end": ts[n - 1],
                               "excess_m": round(hourly_level[ts[s]] - held, 3)})
                break

    out = dict(hourly_level)
    for t, v in zip(ts, L):
        out[t] = v
    return out, events

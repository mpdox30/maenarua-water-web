# Reservoir Reference Data

ไฟล์ในโฟลเดอร์นี้เป็น "ข้อมูลอ้างอิงคงที่" (static reference) สำหรับคำนวณ
Inflow ของอ่างเก็บน้ำแม่นาเรือ แบบไม่ต้องพึ่ง Excel/openpyxl ตอนรัน pipeline จริง

ที่มา: แปลงจากไฟล์ Excel ต้นฉบับที่ผู้ใช้ให้มา (Spillway_Overflow_calculation.xlsx,
2026_May_MNR.xlsx, MonthlyEvapNorm.xlsx) เมื่อ 5 ก.ค. 2569

## ไฟล์ทั้งหมด

### rating_curve_1cm.csv
คอลัมน์: msl_height_m, z_factor, area_m2, volume_m3
771 แถว ครอบคลุมระดับน้ำ 482.8–490.5 m (ทุก 1 cm)
มาจาก sheet "Rating Curve 1 CM" ของไฟล์ 2026_May_MNR.xlsx
**เป็นตารางเดียวที่ใช้อ้างอิง Area/Volume ทั้งหมด** (ยืนยันแล้วว่าตัดตาราง
"Rating Curve" เก่า และ "Area_Terrain" ออก ไม่ใช้อีกต่อไป)

วิธี lookup ต้อง **ตรงกับพฤติกรรม Excel XLOOKUP(...,match_mode=-1) เป๊ะ**
คือ "exact match หรือค่าที่เล็กกว่าถัดไป" (step lookup) — **ไม่ใช่ linear
interpolation** ถ้า implement ผิดเป็น interpolation ค่าจะไม่ตรงกับที่ train ไว้

### flow_rate_spillway.csv / flow_rate_inlet.csv
คอลัมน์: valve_turns, avg_v_ms, avg_q_m3h, avg_q_m3min
จากค่าเฉลี่ย 3 รอบการทดลองวัดในแต่ละไฟล์ Flow rate measuring experiment
ใช้ lookup ตรงตาม valve_turns (exact match, ไม่มีค่าทศนิยม)

### monthly_evap_norm.json
ค่าระเหยเฉลี่ยรายเดือน (mm/เดือน) แบบ climatological คงที่ 12 ค่า
ใช้ในสูตร: Evaporation(m3) = Area(m2) × (MonthlyEvapNorm[เดือน]/days_in_month × 0.7) / 1000
(0.7 = pan coefficient, ค่าคงที่)

### weir_constants.json
ค่าคงที่ทางกายภาพของสปิลเวย์ ใช้คำนวณ Spill (น้ำล้นสปิลเวย์):
Q(m3/s) = C × L × H^1.5
H = max(0, water_level − spillway_level_msl)
Volume(m3/h) = Q(m3/s) × 3600

## สูตร Inflow เต็ม (ยืนยันแล้วกับผู้ใช้ 5 ก.ค. 2569)

```
Inflow(day) = ΔS − R + O + Spill + E + Infiltration
```

| Term | สูตร | ตารางที่ใช้ |
|---|---|---|
| ΔS | Volume(t) − Volume(t−1) | rating_curve_1cm.csv (คอลัมน์ volume_m3) |
| R | Area × Rain_mm / 1000 | rating_curve_1cm.csv (คอลัมน์ area_m2) |
| E | Area × (EvapNorm/days_in_month × 0.7) / 1000 | rating_curve_1cm.csv + monthly_evap_norm.json |
| Infiltration | Area × 0.001 | rating_curve_1cm.csv |
| Spill | sum 24 ค่าใน 1 วันของ weir formula | weir_constants.json (ต้องมี water_level ราย ชม.) |
| O | query event log (Google Form) → lookup flow rate | flow_rate_spillway.csv / flow_rate_inlet.csv |

**หมายเหตุสำคัญ:** สูตร Inflow ในไฟล์ Excel ต้นฉบับ (2026_May_MNR.xlsx)
"ลืม" รวม Infiltration เข้าไปในสูตรจริง (สูตรที่ใช้จริงคือ ΔS−R+O+Spill+E
ไม่มี Infiltration) — ผู้ใช้ยืนยันแล้วว่าเป็น bug ที่ต้องแก้ ไม่ใช่ replicate
พฤติกรรมเดิม ให้ pipeline ใหม่รวม Infiltration เข้าไปด้วยเสมอ

## Known limitation

- Flow rate tables วัดครั้งเดียว ใช้ตลอดไป (ยืนยันจากผู้ใช้) — ถ้าท่อสึก/
  ตะกอนอุดตันในอนาคต ค่าพวกนี้อาจไม่แม่นยำอีกต่อไป ควรมีการวัดซ้ำเป็นระยะ
- water_level(ADJ) ที่เคยเห็นใน Spillway_Overflow_calculation.xlsx **ไม่ได้ใช้แล้ว**
  ให้ใช้ water_level ดิบจากโทรมาตรตรงๆ กับ rating_curve_1cm.csv

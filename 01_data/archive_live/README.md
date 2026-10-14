# archive_live — ค่าพยากรณ์ที่ออกจริงรายวัน (กู้ย้อนหลังไม่ได้ จึงเก็บสำเนาลง git)

สร้างโดย `01_data/scripts and code/colab_migration/archive_live_outputs.py` (Colab Cell 12 เรียกอัตโนมัติทุกวัน; Windows รันมือตอนเก็บตก)
ตรวจช่องว่างด้วย `.github/scripts/check_data_gaps.py` (Colab Cell 13) — วันที่รู้และยอมรับว่าขาดแล้วใส่ใน `KNOWN_GAPS.txt`

| โฟลเดอร์ | เนื้อหา | ตั้งชื่อตาม |
|---|---|---|
| `latest/` | `latest.json` (พยากรณ์ความต้องการน้ำ + น้ำไหลลงอ่าง h1–h7) บีบอัด .gz | วันไทยของ `run_timestamp` |
| `flood_latest/` | `flood_latest.json` (พยากรณ์กว๊าน/น้ำล้น 7 วัน) .gz | `base_date` |
| `wmb_forecast/` | ผล WMB รายวัน `09_live/output/forecast_*.csv` | วันที่ออกพยากรณ์ |
| `weathernext/` | พยากรณ์ฝน WeatherNext ตามที่ออกจริง | เวลา init (UTC) |

ไม่ทับไฟล์ที่มีอยู่แล้ว · ขนาดรวม < 1 MB ต่อเดือน

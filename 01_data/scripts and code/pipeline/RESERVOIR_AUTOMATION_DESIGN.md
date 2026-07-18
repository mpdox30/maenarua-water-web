# ระบบอัตโนมัติบัญชีน้ำ — Design Doc (2026-07-14)

## เป้าหมาย
เลิกอัปโหลดไฟล์ `<year>_<month>_MNR.xlsx` ด้วยมือทุกเดือน โดยคำนวณ "บัญชีน้ำ" รายวัน
(Inflow, Storage, ΔS ฯลฯ) เองจาก 4 อินพุตดิบ:

| อินพุต | แหล่งที่มา | สถานะ |
|---|---|---|
| ระดับน้ำ (MSL) | API สถานีโทรมาตร | มีอยู่แล้ว (ยืนยันโดยผู้ใช้ 2026-07-14) |
| ฝนสะสม 24 ชม. | API สถานีโทรมาตร | มีอยู่แล้ว (ยืนยันโดยผู้ใช้ 2026-07-14) |
| ปริมาณน้ำที่ปล่อยออก (O) | Google Form (ยังไม่สร้าง) | ต้องสร้างใหม่ — เป็นการตัดสินใจของเจ้าหน้าที่ วัดจากเซนเซอร์ไม่ได้ |
| น้ำล้นสปิลเวย์ (Spill) | คำนวณจากระดับน้ำ (weir formula) | คำนวณได้เองถ้ามีระดับน้ำรายชั่วโมง |

**Evaporation, Infiltration, Storage, ΔS, R (น้ำฝนไหลลงอ่างตรง)** ทั้งหมดนี้เป็นสูตรที่คำนวณ
จากระดับน้ำอย่างเดียวอยู่แล้วในไฟล์ต้นฉบับ (ผ่านตาราง Rating Curve / Area_Terrain) — **ไม่มีการ
กรอกมือจริงๆ แม้แต่ตอนนี้** สิ่งที่กรอกมือคือ "ระดับน้ำ" กับ "ฝน" (ซึ่งมี API แล้ว) และ "การปล่อยน้ำ"
(ซึ่งต้องมี Form)

## ส่วนที่ทำเสร็จและสอบทานแล้ว (2026-07-14)

`reservoir_water_balance.py` (ในโฟลเดอร์เดียวกับ `data_pipeline.py`) — สกัดสูตรตรงตัวจากไฟล์
`2026_July_MNR.xlsx` ที่ผู้ใช้อัปโหลด (ชีต "บัญชีน้ำ", "Rating Curve 1 CM", "Area_Terrain",
"น้ำล้นสปิลเวย์") มา reimplement เป็น Python แล้วสอบทานกับค่า Inflow จริงในไฟล์ **ตรงกันแบบ
bit-exact ทั้ง 14 วัน** (1-14 กรกฎาคม 2569) รวมถึงเคสขอบที่ระดับน้ำไม่ตรง grid 0.01 พอดี

จุดสำคัญที่ค้นพบระหว่างสอบทาน: สูตร `XLOOKUP` ในไฟล์ต้นฉบับใช้ `match_mode=-1`
(exact match หรือ floor ไปหาค่าที่เล็กกว่าถัดไป) **ไม่ใช่ round-to-nearest** — ถ้า implement
ผิดจุดนี้ Storage จะเพี้ยนหลักพันลูกบาศก์เมตร/วัน (ลองผิดมาก่อนระหว่างพัฒนา แก้แล้ว)

ไฟล์อ้างอิงที่ export มาด้วย (จากไฟล์ผู้ใช้อัปโหลด, ใช้ได้ตลอดไม่ต้องพึ่งพา Excel อีก):
- `01_data/Reservoirs/reference/rating_curve_1cm.csv` (771 แถว: ระดับน้ำ → พื้นที่ผิวน้ำ, ความจุ)
- `01_data/Reservoirs/reference/area_terrain.csv` (872 แถว: ระดับน้ำ → พื้นที่ terrain, ปริมาตร)

## อัปเดต 2026-07-14 (รอบ 2) — เสร็จเพิ่ม

1. ✅ **ค่าคงที่ evaporation รายเดือนครบ 12 เดือน** — ผู้ใช้เพิ่มไฟล์
   `01_data/Reservoirs/inflow/Evap_Monthly.xlsx` (Average_2012_2024, สถานี 310201 พะเยา)
   เติมใน `MONTHLY_EVAP_CONST_MM` แล้ว สอบทานอีกครั้งกับ 14 วันจริง (bit-exact ภายใน 0.5 m3
   ซึ่งเป็นผลจากค่า July เต็มความละเอียด 120.0254 ต่างจากค่าปัดในไฟล์ต้นฉบับ 120.03 เล็กน้อย)
2. ✅ **สเปค + client สำหรับ API สถานีโทรมาตรจริง** — ผู้ใช้ให้ link จริงมา (สสน., station
   RES002) เขียน+ทดสอบ `reservoir_telemetry_client.py` แล้ว (`fetch_latest_readings()`) —
   ทดสอบ parsing logic กับ payload จริงผ่าน (กรอง RES002 ออกจากหลายสถานีที่ปนกันมาถูกต้อง)
   ตั้งค่าผ่าน env var `RESERVOIR_TELEMETRY_API_URL` (ตาม convention เดียวกับ `gee_auth.py`
   — **ห้าม hardcode credential ในซอร์สที่ commit**)

   **ข้อจำกัดสำคัญที่พบจากการเรียกจริง**: API นี้คืนแค่ "ค่าล่าสุด" เท่านั้น ไม่มี query
   ย้อนหลัง — ต้อง poll เองเป็นระยะ (เสนอทุก 1 ชม.) แล้วสะสม log local เพื่อ (ก) รวม
   `rainfall_1h` เป็นฝนสะสม 24 ชม. ตามที่สูตรต้องการ และ (ข) เก็บระดับน้ำรายชั่วโมงไว้ป้อน
   `compute_spillway_overflow_m3()` — ยังไม่ได้ implement ส่วน log/polling นี้ (ดู TODO
   ท้ายไฟล์ `reservoir_telemetry_client.py`)

## ส่วนที่ยังไม่เสร็จ (ต้องข้อมูล/การตัดสินใจจากผู้ใช้)

1. **โครงสร้าง Google Form** (ดูหัวข้อถัดไป) + กติกาแปลงข้อมูลฟอร์มเป็น O (m3/day)
2. **Polling/log script** — สคริปต์ที่เรียก `fetch_latest_readings()` ทุก 1 ชม. (เสนอ mirror
   โครงสร้าง `sar_background_job.py` ที่มีอยู่แล้ว + Windows Task Scheduler เดียวกัน) แล้ว
   append ลง CSV log local — ต้องยืนยันความถี่ที่ต้องการ (1 ชม. พอไหม หรือถี่กว่านั้น)
3. **Orchestration script รายวัน** — ยังไม่เขียน เพราะรอข้อ 1-2 ก่อน จะเป็นสคริปต์ที่:
   อ่าน log รายชั่วโมงมารวมฝน 24 ชม. + เลือกระดับน้ำ ~07:00 น. → ดึงข้อมูลปล่อยน้ำจาก
   Google Sheet (ที่ผูกกับ Form) → เรียก `compute_daily_row()` → เขียนผลลง live data source
   (ดูหัวข้อ "จุดเชื่อมต่อ pipeline")
4. **ตั้ง env var `RESERVOIR_TELEMETRY_API_URL` บนเครื่องที่จะรัน scheduled task จริง** (ตอนนี้
   ตั้งไว้แค่ในเซสชันทดสอบนี้ชั่วคราว)

## Google Form ที่ต้องสร้าง — บันทึกการปล่อยน้ำ

อิงจากโครงสร้างชีต "ตารางปล่อยน้ำ" ในไฟล์ต้นฉบับ ที่มีอยู่แล้วเป็น log แบบ event (เริ่ม-จบ)
ไม่ใช่ log รายวัน — เสนอฟิลด์ Form ดังนี้:

| ฟิลด์ | ชนิด | หมายเหตุ |
|---|---|---|
| วันที่ + เวลาเริ่มปล่อยน้ำ | Date + Time | |
| วันที่ + เวลาปิดน้ำ | Date + Time | เว้นว่างได้ถ้ายังเปิดอยู่ (ต่อเนื่องหลายวันแบบที่เห็นในข้อมูลจริง) |
| ฝั่งท่อน้ำออก | Dropdown (สปิลเวย์ / ทางเข้าอ่าง) | ตรงกับคอลัมน์ "ฝั่งท่อน้ำออก" เดิม |
| จำนวนรอบที่เปิดวาล์ว | Number | ใช้แปลงเป็นอัตราการไหล (ต้องมีตารางเทียบ รอบ→m3/day จากเจ้าหน้าที่ ถ้ายังไม่มี ให้ใช้อัตราคงที่ที่สังเกตจากข้อมูลจริง เช่น 9446.4 m3/day ที่เห็นในไฟล์กรกฎาคม) |
| วัตถุประสงค์ | Dropdown/Text | เกษตร / ระบายรองรับฝน / อื่นๆ |
| พื้นที่รับน้ำ (ถ้าเพื่อการเกษตร) | Text | ไม่กระทบการคำนวณ Inflow แต่มีประโยชน์เชิงบันทึก |

การแปลงเป็น O(m3/day) รายวัน: ถ้ามีเหตุการณ์ปล่อยน้ำ "ครอบคลุม" วันนั้น (start ≤ วันนั้น ≤ end)
ให้ใช้อัตราของเหตุการณ์นั้น ถ้าไม่มีเหตุการณ์ครอบคลุมวันนั้นเลย O = 0

## จุดเชื่อมต่อกับ pipeline หลัก (data_pipeline.py)

ยังไม่ได้ wire เข้า — เมื่อพร้อม มี 2 ทางเลือก:

- **(a) ง่ายกว่า/เปลี่ยนน้อยกว่า**: orchestration script เขียนผลรายวันลงไฟล์ xlsx รูปแบบเดิม
  (sheet "บัญชีน้ำ", header แถวมี "Date") ต่อท้ายในโฟลเดอร์ `RESERVOIR_INFLOW_RAW_DIR` —
  `_ri_load_raw_monthly_data()` เดิมอ่านได้เลยไม่ต้องแก้โค้ด pipeline
- **(b) สะอาดกว่าระยะยาว**: แก้ `_ri_load_raw_monthly_data()` ให้อ่านจาก CSV/Google Sheet
  ที่ orchestration script เขียนตรงๆ ตัดขั้นตอน xlsx ออกทั้งหมด (ต้องแก้ `data_pipeline.py`)

แนะนำเริ่มจาก (a) ก่อนเพื่อความเสี่ยงต่ำ (ไม่ต้องแก้ pipeline ที่ทำงานอยู่แล้ว) แล้วค่อยย้ายไป (b)
ทีหลังถ้าต้องการ

## สรุปสิ่งที่ต้องได้จากผู้ใช้เพื่อทำต่อ

1. ค่าคงที่ evap ของเดือนอื่นๆ (หรือไฟล์ MNR.xlsx เดือนอื่นให้ผมดึงเอง)
2. สเปค/เอกสาร API สถานีโทรมาตร (หรือให้ผมลองเรียกดูถ้ามี URL/key ที่แชร์ได้)
3. ยืนยันโครงสร้าง Google Form ข้างบน หรือปรับตามที่ต้องการ
4. เลือกทางเชื่อมต่อ pipeline (a) หรือ (b)

---

# อัปเดต 2026-07-18 — Google Form บันทึกการปล่อยน้ำ: สเปคสุดท้าย + Apps Script

**หมายเหตุ**: ทุกอย่างข้างบน (ก่อนบรรทัดนี้) เป็น draft เก่าจาก 2026-07-14 ตอนยังไม่มีข้อมูลจริงหลาย
จุด — ตอนนี้ resolved ไปหมดแล้ว (ดู `PROJECT_MEMORY.md` สำหรับสถานะรวมล่าสุด) ยกเว้น **Google
Form ที่ยังไม่ได้สร้างจริง** — หัวข้อนี้แทนที่สเปค Form แบบเก่าทั้งหมดด้านบน (ฟิลด์/logic
เปลี่ยนไปตามที่คุยกันรอบนี้)

## การตัดสินใจสำคัญที่ต่างจาก draft เดิม

- **Form เดียว ไม่แยก 2 ฟอร์ม** — มีคำถาม "การกระทำ" แรกสุด แตกสาย (branch) ไปหน้าเปิด/หน้าปิด
- **ตอนปิดวาล์ว ต้องเลือก event ที่จะปิดจาก dropdown** (ไม่ใช่กรอกวันที่ปิดลอยๆ แล้วให้ระบบเดา) —
  dropdown นี้ต้องอัปเดตอัตโนมัติให้เห็นเฉพาะ event ที่ยังเปิดอยู่จริง (ทำผ่าน Apps Script time-driven
  trigger ทุก 15 นาที)
- **`reservoir_daily_orchestration.py` ดึงข้อมูลจาก Google Sheet ที่ Form เขียนลงอัตโนมัติแล้ว**
  (โค้ดแก้เสร็จแล้ว 2026-07-18 — ดู `get_release_events()` / `load_release_events_from_sheet()` /
  env var `RESERVOIR_RELEASE_SHEET_CSV_URL`) เหลือแค่สร้าง Form + Sheet + publish-to-web จริงฝั่งคุณ
- **จำนวนรอบวาล์ว**: ใช้ dropdown เดียว 1-12 (ไม่แยกช่วงตามฝั่งท่อ เพื่อไม่ต้องทำ Form branching
  ซ้อนอีกชั้น) — Apps Script ฝั่งหลังบ้านเป็นคนตรวจว่ารอบที่เลือกมีอยู่ในตารางของฝั่งท่อนั้นจริงหรือไม่
  (inlet มีจริง 1-11 รอบ, สปิลเวย์มีจริง 1-12 รอบ — ถ้าเลือกไม่ตรง เช่น inlet รอบ 12 จะเขียนแถวแต่
  ปล่อย `rate_m3_per_day` ว่างพร้อม flag ข้อความเตือนใน `note` ให้เจ้าหน้าที่เห็นและแก้มือ ไม่เดาค่าให้)

## ขั้นตอนสร้าง Google Form (ทำในเบราว์เซอร์ตัวเอง)

ไปที่ forms.google.com สร้าง Form ใหม่ ชื่อ "บันทึกการปล่อยน้ำ — อ่างเก็บน้ำแม่นาเรือ" แล้วสร้างคำถาม
ตามลำดับนี้ (ชื่อคำถามต้อง**ตรงเป๊ะ**กับที่ระบุ เพราะ Apps Script ด้านล่างอ้างชื่อคำถามตรงๆ ถ้าอยาก
ใช้ชื่ออื่นต้องไปแก้ค่าคงที่ `ITEM_TITLES` ในโค้ดให้ตรงกันด้วย):

**คำถามที่ 1 — "การกระทำ"** (Dropdown, required) — ใช้สำหรับแตกสาย:
- ตัวเลือก: `เปิดวาล์วใหม่`, `ปิดวาล์วที่เปิดอยู่`
- คลิกจุด 3 จุดขวาล่างของคำถาม > "Go to section based on answer" ตั้ง:
  - `เปิดวาล์วใหม่` → ไป Section 2 (เปิดวาล์ว)
  - `ปิดวาล์วที่เปิดอยู่` → ไป Section 3 (ปิดวาล์ว)

**Section 2 — เปิดวาล์วใหม่** (ตั้ง "ไปหน้าถัดไป" ท้าย section เป็น "Submit form"):
| ลำดับ | ชื่อคำถาม | ชนิด | ตัวเลือก/หมายเหตุ |
|---|---|---|---|
| 2.1 | `วันที่เปิดวาล์ว` | Date | required |
| 2.2 | `เวลาเปิดวาล์ว` | Time | required |
| 2.3 | `ทางออกที่เปิด` | Dropdown | `ทางเข้าอ่าง`, `สปิลเวย์` — required |
| 2.4 | `จำนวนรอบวาล์วที่เปิด` | Dropdown | `1`...`12` (12 ตัวเลือก) — required |
| 2.5 | `วัตถุประสงค์` | Short answer หรือ Dropdown | เช่น "ระบายน้ำเพื่อรองรับน้ำฝน" — required |
| 2.6 | `หมายเหตุ (เปิด)` | Short answer | ไม่ required |

**Section 3 — ปิดวาล์วที่เปิดอยู่** (ตั้ง "ไปหน้าถัดไป" ท้าย section เป็น "Submit form"):
| ลำดับ | ชื่อคำถาม | ชนิด | ตัวเลือก/หมายเหตุ |
|---|---|---|---|
| 3.1 | `เลือกเหตุการณ์ที่จะปิด` | Dropdown | ใส่ตัวเลือกชั่วคราวไปก่อน 1 ตัว เช่น "(ยังไม่มีข้อมูล)" — Apps Script จะมาอัปเดตตัวเลือกจริงให้อัตโนมัติทุก 15 นาที — required |
| 3.2 | `วันที่ปิดวาล์ว` | Date | required |
| 3.3 | `เวลาปิดวาล์ว` | Time | required |
| 3.4 | `หมายเหตุ (ปิด)` | Short answer | ไม่ required |

หลังสร้างครบ ไปแท็บ "Responses" ของ Form กดไอคอน Sheets (สีเขียว) เพื่อสร้าง/ผูก Google Sheet
คำตอบ (ชื่อ Sheet อะไรก็ได้) แล้วเปิด Sheet นั้น **เพิ่มแท็บใหม่** ชื่อ `release_log` (สะกดตรงนี้
สำคัญ — ต้องตรงกับ `SHEET_TAB_NAME` ในโค้ด) ใส่หัวคอลัมน์แถวที่ 1 เป็น:

```
event_no,start_date,start_time,end_date,end_time,outlet_side,rate_m3_per_day,purpose,note
```

(โครงสร้างเดียวกับ `01_data/Reservoirs/release_log/release_events.csv` local เป๊ะ)

## ติดตั้ง Apps Script

1. เปิด Google Form ที่สร้างไว้ → เมนู 3 จุดขวาบน → "Script editor" (หรือ "Apps Script")
2. ลบโค้ด default ทั้งหมด แล้ววางโค้ดด้านล่างนี้ทั้งหมด
3. แก้ `SHEET_ID` ให้เป็น ID ของ Google Sheet คำตอบที่ผูกกับ Form (ดูจาก URL ของ Sheet:
   `https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit...` — copy ส่วน `<SHEET_ID>`)
4. กด Save (ไอคอนแผ่นดิสก์) ตั้งชื่อโปรเจกต์ เช่น "release_log_automation"
5. รันฟังก์ชัน `refreshCloseDropdownChoices` มือครั้งแรก (เลือกจาก dropdown ฟังก์ชันด้านบน แล้วกด
   Run ▷) — Google จะถามสิทธิ์เข้าถึง Form/Sheet ของคุณเอง กด "Allow" (เป็นสิทธิ์เข้าถึงแค่ไฟล์ของ
   คุณเอง ไม่ใช่บุคคลที่สาม ปลอดภัย)
6. ไปแท็บ Triggers (ไอคอนนาฬิกาซ้ายมือ) → "Add Trigger" ตั้ง 2 ตัว:
   - Function: `onFormSubmitReleaseLog` | Event source: `From form` | Event type: `On form submit`
   - Function: `refreshCloseDropdownChoices` | Event source: `Time-driven` | ทุก 15 นาที
7. ทดสอบ: เปิด Form (ปุ่ม "Send" > คัดลอกลิงก์) กรอกทดสอบ "เปิดวาล์วใหม่" 1 รอบ → เช็คว่ามีแถวใหม่
   ใน `release_log` (end_date/end_time ว่าง) → รอ/รัน `refreshCloseDropdownChoices` มือ → เปิด Form
   อีกครั้งเลือก "ปิดวาล์วที่เปิดอยู่" ควรเห็น event ที่เพิ่งเปิดใน dropdown → กรอกปิดทดสอบ → เช็คว่า
   แถวเดิมถูกเติม end_date/end_time (ไม่ใช่สร้างแถวใหม่)

```javascript
/**
 * Code.gs — Apps Script สำหรับ Form "บันทึกการปล่อยน้ำ" (อ่างเก็บน้ำแม่นาเรือ)
 * เขียน/แก้ไขแถวในแท็บ "release_log" ของ Google Sheet คำตอบ ให้โครงสร้างตรงกับที่
 * reservoir_daily_orchestration.py::load_release_events_from_sheet() คาดหวัง
 */

var SHEET_ID = 'ใส่ SHEET_ID ของ Google Sheet คำตอบตรงนี้'; // แก้ก่อนใช้งานจริง
var SHEET_TAB_NAME = 'release_log';
var SHEET_COLUMNS = ['event_no', 'start_date', 'start_time', 'end_date', 'end_time',
                      'outlet_side', 'rate_m3_per_day', 'purpose', 'note'];

var ITEM_TITLES = {
  ACTION: 'การกระทำ',
  OPEN_DATE: 'วันที่เปิดวาล์ว',
  OPEN_TIME: 'เวลาเปิดวาล์ว',
  OUTLET: 'ทางออกที่เปิด',
  VALVE_TURNS: 'จำนวนรอบวาล์วที่เปิด',
  PURPOSE: 'วัตถุประสงค์',
  OPEN_NOTE: 'หมายเหตุ (เปิด)',
  CLOSE_EVENT: 'เลือกเหตุการณ์ที่จะปิด',
  CLOSE_DATE: 'วันที่ปิดวาล์ว',
  CLOSE_TIME: 'เวลาปิดวาล์ว',
  CLOSE_NOTE: 'หมายเหตุ (ปิด)',
};

var ACTION_OPEN = 'เปิดวาล์วใหม่';
var ACTION_CLOSE = 'ปิดวาล์วที่เปิดอยู่';

// รอบวาล์ว -> m3/day = avg_q_m3h * 24 คัดลอกมาจาก
// 01_data/Reservoirs/reference/flow_rate_inlet.csv / flow_rate_spillway.csv (2026-07-18)
// ถ้าทดสอบวาล์วใหม่แล้วไฟล์ CSV ต้นทางเปลี่ยน ต้องมาแก้ตารางนี้ให้ตรงกันด้วยมือ (ไม่ sync อัตโนมัติ)
var FLOW_RATE_M3_PER_DAY = {
  'ทางเข้าอ่าง': {1: 0, 2: 331.2, 3: 1771.2, 4: 3537.6, 5: 4910.4, 6: 5572.8, 7: 6100.8,
                  8: 6619.2, 9: 6724.8, 10: 6772.8, 11: 6792.0},
  'สปิลเวย์':    {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 9446.4, 7: 10409.6, 8: 11025.6,
                  9: 11289.6, 10: 11467.2, 11: 11728.0, 12: 12012.8},
};

function getReleaseLogSheet_() {
  var ss = SpreadsheetApp.openById(SHEET_ID);
  var sheet = ss.getSheetByName(SHEET_TAB_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_TAB_NAME);
    sheet.appendRow(SHEET_COLUMNS);
  }
  return sheet;
}

function firstAnswer_(namedValues, title) {
  var v = namedValues[title];
  return (v && v.length > 0) ? String(v[0]).trim() : '';
}

/** onFormSubmit trigger -- ดู setup ข้อ 6 */
function onFormSubmitReleaseLog(e) {
  try {
    var nv = e.namedValues;
    var action = firstAnswer_(nv, ITEM_TITLES.ACTION);

    if (action === ACTION_OPEN) {
      handleOpenEvent_(nv);
    } else if (action === ACTION_CLOSE) {
      handleCloseEvent_(nv);
    } else {
      Logger.log('onFormSubmitReleaseLog: action ไม่รู้จัก: ' + action);
    }
    // อัปเดต dropdown ปิดวาล์วทันทีหลัง submit แต่ละครั้ง (ไม่ต้องรอ trigger 15 นาที)
    refreshCloseDropdownChoices();
  } catch (err) {
    Logger.log('onFormSubmitReleaseLog ล้มเหลว: ' + err);
    // ไม่ throw ต่อ -- กัน Form response หายไปเงียบๆ ถ้าอยากได้ alert อีเมลตอน error จริง
    // เพิ่ม MailApp.sendEmail(...) ตรงนี้ได้
  }
}

function handleOpenEvent_(nv) {
  var sheet = getReleaseLogSheet_();
  var outlet = firstAnswer_(nv, ITEM_TITLES.OUTLET);
  var valveTurns = parseInt(firstAnswer_(nv, ITEM_TITLES.VALVE_TURNS), 10);
  var purpose = firstAnswer_(nv, ITEM_TITLES.PURPOSE);
  var note = firstAnswer_(nv, ITEM_TITLES.OPEN_NOTE);

  var table = FLOW_RATE_M3_PER_DAY[outlet];
  var rate = table ? table[valveTurns] : undefined;
  if (rate === undefined) {
    note = (note ? note + ' ' : '') +
      '[ตรวจสอบมือ: จำนวนรอบวาล์ว ' + valveTurns + ' ไม่มีในตารางของ "' + outlet + '"]';
    rate = '';
  }

  var data = sheet.getDataRange().getValues();
  var maxEventNo = 0;
  for (var i = 1; i < data.length; i++) {
    var n = parseInt(data[i][0], 10);
    if (!isNaN(n) && n > maxEventNo) maxEventNo = n;
  }
  var nextEventNo = maxEventNo + 1;

  sheet.appendRow([
    nextEventNo,
    firstAnswer_(nv, ITEM_TITLES.OPEN_DATE),
    firstAnswer_(nv, ITEM_TITLES.OPEN_TIME),
    '', '', // end_date, end_time -- ว่างไว้ก่อน = ยังไม่ปิด
    outlet,
    rate,
    purpose,
    note,
  ]);
}

function handleCloseEvent_(nv) {
  var selected = firstAnswer_(nv, ITEM_TITLES.CLOSE_EVENT);
  var m = selected.match(/event#(\d+)/);
  if (!m) {
    Logger.log('handleCloseEvent_: หา event_no จาก dropdown label ไม่เจอ: ' + selected);
    return;
  }
  var eventNo = parseInt(m[1], 10);

  var sheet = getReleaseLogSheet_();
  var data = sheet.getDataRange().getValues();
  for (var i = 1; i < data.length; i++) {
    var rowEventNo = parseInt(data[i][0], 10);
    var endDateCell = data[i][3];
    if (rowEventNo === eventNo && (!endDateCell || endDateCell === '')) {
      var rowIndex = i + 1; // 1-indexed สำหรับ Sheets API
      sheet.getRange(rowIndex, 4).setValue(firstAnswer_(nv, ITEM_TITLES.CLOSE_DATE)); // end_date
      sheet.getRange(rowIndex, 5).setValue(firstAnswer_(nv, ITEM_TITLES.CLOSE_TIME)); // end_time
      var closeNote = firstAnswer_(nv, ITEM_TITLES.CLOSE_NOTE);
      if (closeNote) {
        var existingNote = data[i][8] || '';
        sheet.getRange(rowIndex, 9).setValue(existingNote + (existingNote ? ' | ' : '') + 'ปิด: ' + closeNote);
      }
      return;
    }
  }
  Logger.log('handleCloseEvent_: ไม่พบ event#' + eventNo + ' ที่ยังเปิดอยู่ (อาจถูกปิดไปแล้วก่อนหน้า)');
}

/** Time-driven trigger (ทุก 15 นาที) -- รีเฟรช dropdown "เลือกเหตุการณ์ที่จะปิด" ให้ตรงกับ
 *  เหตุการณ์ที่ end_date ยังว่างจริงใน release_log ตอนนี้ */
function refreshCloseDropdownChoices() {
  var sheet = getReleaseLogSheet_();
  var data = sheet.getDataRange().getValues();
  var labels = [];
  for (var i = 1; i < data.length; i++) {
    var eventNo = data[i][0];
    var endDate = data[i][3];
    if (eventNo !== '' && (!endDate || endDate === '')) {
      labels.push('event#' + eventNo + ' - ' + data[i][5] + ' - เปิดเมื่อ ' + data[i][1] + ' ' + data[i][2]);
    }
  }
  if (labels.length === 0) {
    labels = ['(ไม่มีเหตุการณ์เปิดอยู่ในขณะนี้)'];
  }

  var form = FormApp.getActiveForm();
  var items = form.getItems();
  for (var j = 0; j < items.length; j++) {
    if (items[j].getTitle() === ITEM_TITLES.CLOSE_EVENT) {
      items[j].asListItem().setChoiceValues(labels);
      return;
    }
  }
  Logger.log('refreshCloseDropdownChoices: หาคำถามชื่อ "' + ITEM_TITLES.CLOSE_EVENT + '" ใน Form ไม่เจอ');
}
```

## Publish-to-web + ตั้ง env var (ทำหลังทดสอบ Apps Script ผ่านแล้ว)

1. เปิด Google Sheet คำตอบ → File > Share > Publish to web
2. เลือก dropdown แท็บเป็น `release_log` (ไม่ใช่ "Entire Document") → format `Comma-separated values (.csv)` → Publish
3. Copy ลิงก์ที่ได้ (รูปแบบ `https://docs.google.com/spreadsheets/d/e/<id>/pub?gid=<gid>&single=true&output=csv`)
4. บนเครื่อง Windows ที่รัน `reservoir_daily_orchestration.py` เปิด Command Prompt แล้วรัน
   (ครั้งเดียว ค่าจะติดถาวรกับ user account):
   ```
   setx RESERVOIR_RELEASE_SHEET_CSV_URL "<ลิงก์ที่ copy มา>"
   ```
5. ปิด/เปิด Command Prompt ใหม่ (หรือ log off/on) ให้ env var มีผล แล้วทดสอบ:
   ```
   cd /d "D:\maenaruea-water-web\01_data\scripts and code\pipeline"
   python reservoir_official_file_writer.py --dates 2026-07-18 --dry-run
   ```
   เช็ค log ว่าไม่มี warning "ไม่มีเหตุการณ์ปล่อยน้ำ...ใช้ O=0" ทั้งที่ Sheet มี event ครอบคลุมวันนั้นจริง
   (ถ้าเห็น warning นี้ทั้งที่ควรมี event -- เช็คว่า publish-to-web link ยังไม่ propagate เสร็จ
   รอ 2-3 นาทีแล้วลองใหม่ หรือเช็คว่า publish เลือกแท็บ `release_log` ถูกจริง)

**ถ้ายังไม่อยากตั้ง env var ตอนนี้** ระบบจะ fallback ไปอ่าน `release_events.csv` local เหมือนเดิม
โดยอัตโนมัติ (ไม่ต้องแก้อะไรเพิ่ม ไม่มีความเสี่ยง) — ตั้ง env var เมื่อพร้อมทดสอบ Form จริงแล้วเท่านั้น

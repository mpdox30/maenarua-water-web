# แผนละเอียด: ย้าย automation ไป GitHub Actions + เก็บเครื่อง Windows เป็น shadow คู่ขนาน

สถานะ: **เอกสารแผนเท่านั้น ยังไม่ได้ลงมือทำอะไร**

## ภาพรวมสถาปัตยกรรม

```
GitHub Actions (ใหม่ — ระบบหลัก)          เครื่อง Windows (เดิม — เปลี่ยนบทบาทเป็น shadow)
├─ workflow: reservoir-orchestration        ├─ Task Scheduler เดิมทั้ง 4 ตัว ยังรันเหมือนเดิมทุกอย่าง
│   cron ทุกวัน 00:30 UTC (=07:30 ไทย)      │   (ไม่ต้อง port/แก้โค้ดเลย)
├─ workflow: monitoring-builder             ├─ **เปลี่ยนแค่จุดเดียว**: ปิดขั้น git push ออก
│   cron ทุก 15 นาที                        │   (หรือ push ไป branch แยก — ดูหัวข้อ 4)
├─ workflow: sar-background-job             ├─ ไฟล์ที่คำนวณได้ (xlsx/CSV/JSON) ยังเขียนลงดิสก์
│   cron ทุกสัปดาห์ (จ. 20:00 UTC = 03:00 ไทย)│   เครื่อง Windows ตามปกติ — ใช้เทียบกับผลจาก
└─ workflow: main-pipeline                  │   GitHub Actions ได้เหมือนที่เคยเทียบ Windows
    cron ทุกวัน 02:00 UTC (=09:00 ไทย,       │   vs Colab มาก่อน
    หลัง orchestration เสร็จแน่ๆ)            └─ ไม่ต้องเปิดเครื่องไว้ตลอด — เปิดเป็นช่วงๆ/ตามสะดวก
        ↓ ทั้งหมด push ไป GitHub master          ก็พอ เพราะไม่ใช่ระบบหลักที่เว็บพึ่งพาแล้ว
    เว็บอ่านจาก GitHub Pages/ไฟล์ที่ push มา
```

## 1. รายละเอียด 4 workflow

แต่ละ workflow = 1 ไฟล์ YAML ใน `.github/workflows/` โครงเดียวกัน:

```yaml
name: reservoir-orchestration
on:
  schedule:
    - cron: "30 0 * * *"   # 00:30 UTC = 07:30 ไทย
  workflow_dispatch: {}     # กดรันมือได้จาก GitHub UI ด้วย เผื่อทดสอบ/backfill
jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip        # แคช pip package ข้ามรอบ ลดเวลา install ซ้ำ
      - run: pip install -r "01_data/scripts and code/pipeline/requirements.txt"
      - run: python "01_data/scripts and code/pipeline/reservoir_daily_orchestration_actions.py"
        env:
          RESERVOIR_TELEMETRY_SHEET_CSV_URL: ${{ secrets.RESERVOIR_TELEMETRY_SHEET_CSV_URL }}
          RESERVOIR_RELEASE_SHEET_CSV_URL: ${{ secrets.RESERVOIR_RELEASE_SHEET_CSV_URL }}
      - name: commit + push
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git pull --no-rebase --no-edit origin master
          git add "01_data/Reservoirs/inflow/" "01_data/Reservoirs/inflow_auto/RES002_daily_computed.csv"
          git diff --cached --quiet || git commit -m "Auto-update: reservoir orchestration (Actions)"
          git push origin master
```

อีก 3 workflow (`monitoring-builder`, `sar-background-job`, `main-pipeline`) หน้าตาเหมือนกันทุกจุด
ต่างแค่ cron schedule + สคริปต์ที่เรียก + secrets ที่ต้องใช้ (`main-pipeline` ต้องเพิ่ม
`CDSAPI_URL`/`CDSAPI_KEY`/`GEE_SA_KEY_JSON`/`GEE_SA_EMAIL`) `git push` ใช้ `GITHUB_TOKEN` มาตรฐานที่
Actions ให้มาฟรีทุก workflow (ตั้ง `permissions: contents: write` ในไฟล์) **ไม่ต้องสร้าง PAT ใหม่**
เพราะ push กลับ repo เดียวกับที่ workflow รันอยู่

## 2. งานที่ต้องทำเพิ่ม (นอกเหนือจาก 4 ไฟล์ YAML)

1. **Port 3 สคริปต์** (`reservoir_daily_orchestration.py`, `monitoring_data_builder.py`,
   `sar_background_job.py`) → เวอร์ชันไม่พึ่ง Windows path/conda env ใดๆ — จากที่ตรวจแล้วรอบก่อน
   ไม่มีตัวไหนติด Windows-only dependency เลย (ไม่เหมือน `era5t_worker.py` ที่เคยติด ArcGIS)
   คาดว่า port ตรงไปตรงมา คล้ายที่ทำ `data_pipeline_colab.py` สำเร็จมาแล้ว
2. **ย้าย credential เข้า GitHub Actions Secrets** (Settings → Secrets and variables → Actions):
   `RESERVOIR_TELEMETRY_SHEET_CSV_URL`, `RESERVOIR_RELEASE_SHEET_CSV_URL`, `CDSAPI_URL`, `CDSAPI_KEY`,
   `GEE_SA_KEY_JSON`, `GEE_SA_EMAIL` — ค่าเดียวกับที่ตั้งไว้ใน Colab Secrets อยู่แล้ว แค่ copy มาวางที่ใหม่
3. **ทดสอบว่า cfgrib/eccodes ติดตั้งได้จริงบน Actions runner (ubuntu-latest)** — นี่คือความเสี่ยงข้อ
   1 ด้านล่าง ควรทดสอบเป็นอย่างแรกก่อนลงแรง port อะไรเพิ่ม เพราะถ้าไม่ผ่านต้องหาทางแก้ก่อน
4. เขียน workflow YAML ทั้ง 4
5. รันคู่ขนานเทียบผลกับ Colab สัก 1-2 สัปดาห์ (เหมือน pattern cutover ที่เคยวางแผนไว้ตอน
   Colab migration) ก่อนเลิกเปิด Colab
6. ปรับเครื่อง Windows (ดูหัวข้อ 4)

## 3. ความเสี่ยง/ข้อจำกัดของ GitHub Actions (เรียงตามความสำคัญ)

### 3.1 ⚠️ eccodes/cfgrib บน ubuntu-latest runner — ยังไม่ยืนยัน ต้องทดสอบก่อน
ปัญหาเดิมบน Windows คือ pip install cfgrib/eccodes ไม่ได้เพราะขาด eccodes system library ตัวจริง —
แก้ได้บน Colab เพราะเป็น Linux ที่ pip install ผ่าน แต่ **Colab อาจมี system library บางตัวติดตั้งไว้
ล่วงหน้าที่ vanilla Ubuntu runner ของ Actions ไม่มี** ต้องทดสอบจริงก่อน ถ้าไม่ผ่านอาจต้องเพิ่มขั้น
`apt-get install libeccodes0` หรือใช้ conda ผ่าน `setup-miniconda` action แทน pip ตรงๆ — **นี่คือ
ความเสี่ยงทางเทคนิคข้อเดียวที่อาจทำให้แผนนี้สะดุดจริง แนะนำทดสอบเป็นขั้นแรกสุดก่อนลงมือ port อะไรอื่น**

### 3.2 ⚠️ GitHub Actions ไม่มี state ค้างข้าม run เลย (หนักกว่า Colab)
Colab ยังต้อง pip install ใหม่ทุกวัน (1 ครั้ง/วัน) แต่ **Actions เป็นเครื่องเปล่าใหม่ทุกครั้งที่ trigger
รวมถึง `monitoring-builder` ที่รันทุก 15 นาที = ต้อง checkout + setup Python + pip install ซ้ำ 96
รอบ/วัน** แม้จะใช้ `cache: pip` ช่วยลดเวลาได้มาก (ไม่ต้องดาวน์โหลดใหม่ แต่ยัง extract/install อยู่ดี)
ก็ยังมี overhead ต่อรอบที่ Colab (session เดียวรันยาวทั้งวัน) ไม่มี

### 3.3 ⚠️ Quota นาทีฟรี — จุดที่ต้องเช็คก่อนตัดสินใจจริงๆ
ประมาณการเวลาใช้งาน/เดือน (คร่าวๆ จาก log จริง: pipeline หลักรันจริงล่าสุดใช้ ~2.5 นาที/รอบ):

| workflow | ความถี่ | เวลา/รอบ (ประมาณ) | รวม/เดือน |
|---|---|---|---|
| monitoring-builder | ทุก 15 นาที (96/วัน) | ~0.5-1.5 นาที (ส่วนใหญ่เป็น overhead setup) | **1,400-4,300 นาที** |
| main-pipeline | วันละครั้ง | ~3-8 นาที | 90-240 นาที |
| reservoir-orchestration | วันละครั้ง | ~1-2 นาที | 30-60 นาที |
| sar-background-job | สัปดาห์ละครั้ง | ~5-15 นาที | 20-60 นาที |
| **รวม** | | | **~1,600-4,700 นาที/เดือน** |

**GitHub ให้ฟรี 2,000 นาที/เดือนเฉพาะ repo แบบ private** (repo แบบ public ไม่จำกัดเลย) —
ตัวเลขประมาณการข้างบนมีโอกาสสูงที่จะ**เกิน quota ฟรีถ้า repo เป็น private** (ตัว
`monitoring-builder` ตัวเดียวก็เกือบเต็ม quota แล้ว) **ต้องเช็คก่อนว่า repo นี้ public หรือ private**
— ถ้าเป็นข้อมูลไม่อ่อนไหว (เป็นข้อมูลน้ำ/สิ่งแวดล้อมสาธารณะ) **แนะนำเปลี่ยนเป็น public** จะตัดปัญหานี้
ไปเลยทั้งหมด (credential ทุกตัวอยู่ใน Secrets แยกอยู่แล้ว ไม่ได้อยู่ในโค้ดที่จะ public ไปด้วย)
ถ้าต้องการ private ต่อไป ต้องเตรียมงบสำหรับนาทีส่วนเกิน (คิดตามการใช้จริง)

### 3.4 Cron ของ Actions ไม่ตรงเวลาเป๊ะเสมอ
GitHub เอกสารระบุเองว่า scheduled workflow อาจ**ล่าช้าได้ช่วงระบบโหลดสูง** (ปกติไม่กี่นาที) — ไม่ใช่
ปัญหาใหญ่สำหรับงานพวกนี้ (ไม่มีอะไรต้องเป๊ะถึงวินาที) แค่ต้องรู้ไว้ไม่ให้คาดหวัง "ตรง 15:00:00 เป๊ะ"

### 3.5 Push ชนกันระหว่างหลาย workflow
ถ้า 2 workflow บังเอิญ push พร้อมกัน (เช่น monitoring-builder ชนกับ main-pipeline ที่ยาวจนเวลาทับกัน)
อาจ push ไม่ผ่านรอบนั้น (non-fast-forward) — **แก้ด้วย `git pull --no-rebase` ก่อน push เสมอ** (pattern
เดียวกับที่ .bat ไฟล์เดิมใช้อยู่แล้วตอนนี้ พิสูจน์แล้วว่าใช้ได้จริงกับ 2 ระบบคู่ขนาน Windows+Colab)
ไม่ทำให้ข้อมูลเสีย แค่บางรอบอาจข้ามการ push ไปเฉยๆ (ไม่ error ร้ายแรง)

### 3.6 ไม่มีทางดู output แบบ interactive เหมือน Colab
รันแบบ headless ทั้งหมด ต้องเข้าไปดู log ใน tab "Actions" ของ GitHub ทีหลังถ้าอยากรู้ว่าเกิดอะไรขึ้น —
แนะนำเพิ่มขั้นแจ้งเตือนเมื่อ job ล้มเหลว (เช่นส่งอีเมล/แจ้งผ่าน GitHub เองที่ตั้งค่าได้อยู่แล้วเวลา
workflow fail, ไม่ต้องทำอะไรเพิ่มก็ได้แจ้งเตือนพื้นฐานฟรีอยู่แล้ว)

## 4. แผนสำหรับเครื่อง Windows (เก็บไว้เป็น shadow คู่ขนาน)

ตามที่ขอ — **ไม่ต้องปิด Task Scheduler บน Windows เลย** แค่เปลี่ยนบทบาทจาก "ระบบหลักที่เว็บพึ่งพา"
เป็น "ระบบสำรองไว้เทียบข้อมูล" (เหมือนที่เคยใช้เทียบ Windows vs Colab ตอน cutover ที่ผ่านมา)

**สิ่งที่ต้องปรับ (น้อยมาก — ไม่ต้อง port อะไร ไม่ต้องแก้ logic เลย):**
- ตัดขั้น `git push` ออกจาก `.bat` launcher ทั้ง 4 ไฟล์ (หรือปรับให้ push ไป branch แยก เช่น
  `windows-shadow` แทน `master` ถ้าอยากมี backup บน GitHub ด้วย ไม่ใช่แค่ในเครื่อง) — เลือกได้ 2 ทาง:
  - **(ก) ง่ายสุด**: ลบ/comment ขั้น git add/commit/push ทิ้งไปเลย ปล่อยให้เขียนแค่ไฟล์ในเครื่อง
    (xlsx/CSV/JSON เดิมทุกอย่าง) — ไม่ต้อง push ที่ไหนเลย เก็บไว้ในเครื่องอย่างเดียวตามที่บอก
  - **(ข)** เปลี่ยน remote/branch เป็น `windows-shadow` แทน `master` — ได้ backup บน GitHub ด้วย
    เผื่ออยากเทียบจากที่ไหนก็ได้ ไม่ต้องเปิดเครื่อง Windows เพื่อดูผลย้อนหลัง
- ผลคือ: เครื่อง Windows ยังคำนวณทุกอย่างเหมือนเดิมทุกวัน (07:30 orchestration, ทุก 15 นาที monitoring,
  ทุกสัปดาห์ SAR) เก็บไว้ในเครื่อง/branch แยก ไม่ชนกับที่ GitHub Actions push ไป `master` เลย
- **ไม่ต้องเปิดเครื่องไว้ตลอด 24/7** — Task Scheduler จะรันเฉพาะตอนเครื่องเปิดอยู่ ถ้าปิดเครื่องช่วงที่
  ควรรัน ก็แค่ข้ามรอบนั้นไป (ไม่ error, ไม่กระทบเว็บเพราะเว็บพึ่ง GitHub Actions เป็นหลักแล้ว) — เปิด
  เครื่องเท่าที่สะดวก ได้ข้อมูลมาเทียบเป็นระยะๆ ก็พอสำหรับ validate/debug กรณีสงสัยว่าข้อมูลผิดปกติ

## 5. ลำดับขั้นแนะนำ (ถ้าตัดสินใจเดินหน้า)

1. เช็ค repo public/private ก่อน (ตัดสินใจเรื่อง quota)
2. ทดสอบ eccodes/cfgrib บน `ubuntu-latest` ก่อนเป็นอันดับแรก (สร้าง workflow ทดสอบเล็กๆ 1 ไฟล์)
3. ถ้าผ่าน → port 3 สคริปต์ + เขียน 4 workflow YAML
4. ตั้ง GitHub Actions Secrets
5. รัน `workflow_dispatch` (กดมือ) ทดสอบทีละตัวก่อนเปิด cron จริง
6. เปิด cron จริง รันคู่ขนานกับ Colab เทียบผล 1-2 สัปดาห์
7. ปรับ .bat บน Windows ตามหัวข้อ 4 (ตัด push)
8. ปิด Colab (เลิกต้องเปิดโน๊ตบุ๊คทุกวัน)

## สิ่งที่ต้องตอบก่อนเริ่มขั้นตอนจริง
- Repo public หรือ private?
- โอเคไหมถ้าจะทดสอบ eccodes บน Actions ก่อน (ใช้เวลา/quota เล็กน้อยแต่ตอบคำถามความเสี่ยงหลักได้เลย)

"""
gee_auth.py
===========
2026-07-14 เพิ่ม — helper เดียวสำหรับ ee.Initialize() ที่ทุกโมดูลที่ใช้ Google Earth Engine
(chirps_feature.py, sar_classification.py) ควรเรียกผ่านฟังก์ชันนี้แทนการเรียก
ee.Initialize(project=...) ตรงๆ เอง เพื่อให้สลับจาก personal credential (ee.Authenticate() แบบ
interactive) ไปเป็น Service Account ได้จุดเดียว ไม่ต้องแก้ทุกไฟล์ที่เรียก ee.Initialize() เอง

เหตุผลที่ต้องมีไฟล์นี้ (TODO ที่ค้างมาตั้งแต่ chirps_feature.py/sar_classification.py หัวไฟล์):
personal credential (ee.Authenticate() แบบ interactive, เปิด browser login เอง) ไม่เหมาะกับการรัน
แบบ scheduled/unattended (Windows Task Scheduler ผ่าน run_pipeline.bat / run_sar_background_job.bat)
เพราะ OAuth token ส่วนตัวอาจหมดอายุหรือถูก revoke โดยไม่มีใครคอย login ซ้ำให้ ทำให้ pipeline ที่รัน
อัตโนมัติพังกลางทางแบบเงียบๆ ได้ ต้องเปลี่ยนเป็น Service Account ก่อนพึ่งพา scheduled task ระยะยาว

=== วิธีตั้งค่า Service Account (ทำครั้งเดียวต่อเครื่องที่จะรัน scheduled task) ===

1. เปิด GCP Console (https://console.cloud.google.com) -> เลือก project 'maenaruea-water-pipeline'
   (project เดียวกับที่ตั้งไว้ DEFAULT_GEE_PROJECT ทุกไฟล์ในโปรเจกต์นี้)
2. ไปที่ IAM & Admin -> Service Accounts -> Create Service Account
   ตั้งชื่อ เช่น "maenaruea-sar-pipeline" -> Create and Continue -> Role: ไม่ต้องเพิ่ม role พิเศษ
   (Earth Engine ใช้ระบบสิทธิ์ของตัวเอง แยกจาก IAM role ปกติ — ดูขั้นตอน 4)
3. หลังสร้างเสร็จ ไปที่ service account นั้น -> tab "Keys" -> Add Key -> Create new key ->
   เลือก JSON -> ดาวน์โหลดไฟล์ .json มาเก็บไว้ในเครื่อง (path ใดก็ได้ที่ปลอดภัย นอกโฟลเดอร์ git repo
   นี้ หรือถ้าเก็บในนี้ต้องเพิ่มใน .gitignore ทันที — **ห้าม commit ไฟล์ key เข้า git เด็ดขาด**)
4. ลงทะเบียน service account email กับ Earth Engine (ขั้นตอนที่มักลืม แล้วจะ error "not registered"):
   ไปที่ https://code.earthengine.google.com/register -> เลือก "Register a Service Account" ->
   กรอก service account email (รูปแบบ xxx@xxx.iam.gserviceaccount.com จากขั้นตอน 2)
5. ตั้ง environment variable 2 ตัวบนเครื่องที่จะรัน scheduled task (System Properties ->
   Environment Variables -> New... ระดับ System หรือ User ก็ได้ แล้ว restart เครื่อง/Task Scheduler
   service เพื่อให้ env var มีผล หรือจะตั้งใน .bat ก่อนเรียก python ก็ได้ผ่าน `set` เหมือนกัน):
     GEE_SERVICE_ACCOUNT_EMAIL = xxx@xxx.iam.gserviceaccount.com   (จากขั้นตอน 2)
     GEE_SERVICE_ACCOUNT_KEY   = D:\path\to\service-account-key.json   (path ไฟล์จากขั้นตอน 3)
6. ทดสอบ: รัน test_sar_classification_live.py หรือ test_chirps_live.py แล้วดู log บรรทัด
   "GEE auth: ใช้ Service Account" ในขั้นที่ 1 — ถ้ายังเห็น "ใช้ personal credential" แปลว่า env var
   ยังไม่ถูกอ่านเจอ (เช็คว่า restart terminal/เครื่องหลังตั้งค่าแล้วหรือยัง)

ถ้าไม่ตั้ง 2 ตัวแปรนี้ไว้เลย init_ee() จะ fallback ไปใช้ personal credential (ee.Authenticate())
เหมือนเดิมทันที ไม่ error — เหมาะกับตอน dev/ทดสอบบนเครื่องคนเดียว แต่**ไม่เหมาะกับ scheduled task
ที่ไม่มีคนคอย login ซ้ำ**
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger("data_pipeline")

GEE_SERVICE_ACCOUNT_EMAIL_ENV = "GEE_SERVICE_ACCOUNT_EMAIL"
GEE_SERVICE_ACCOUNT_KEY_ENV = "GEE_SERVICE_ACCOUNT_KEY"


def init_ee(gee_project: str) -> str:
    """
    เรียก ee.Initialize() แบบเดียวที่ทุกโมดูล (chirps_feature.py, sar_classification.py) ควรใช้
    แทนการเรียก ee.Initialize(project=...) ตรงๆ เอง

    ลำดับความสำคัญ:
      1. ถ้าตั้ง env var GEE_SERVICE_ACCOUNT_EMAIL + GEE_SERVICE_ACCOUNT_KEY ไว้ครบ (ชี้ไปที่ไฟล์
         JSON key ที่มีอยู่จริงบนดิสก์) -> ใช้ ee.ServiceAccountCredentials() (เหมาะกับ scheduled
         task ที่ไม่มีคนคอย login ซ้ำ — ดู docstring หัวไฟล์นี้สำหรับวิธีตั้งค่า)
      2. ไม่งั้น fallback ไปใช้ ee.Initialize(project=gee_project) เฉยๆ (personal credential จาก
         ee.Authenticate() ที่เคยรันไว้ก่อนหน้าบนเครื่องนี้ — เหมาะกับตอน dev/ทดสอบ)

    คืนค่า string บอกว่าใช้ auth mode ไหนจริง ("service_account" หรือ "personal_credential") ให้
    caller log/รายงานได้ว่ารอบนี้ auth ด้วยวิธีไหน — สำคัญตอน debug ว่าทำไม scheduled task ถึง fail
    แบบ "ต้อง re-authenticate": ถ้าเห็นว่าเป็น personal_credential ใน log ของ scheduled task รู้ทันที
    ว่ายังไม่ได้ตั้ง Service Account ตามที่ควรก่อน deploy จริง

    ไม่ raise ถ้า Service Account ตั้งค่าไว้ผิด (เช่น path ไม่มีไฟล์จริง, service account ยังไม่ได้
    ลงทะเบียนกับ Earth Engine) -- log warning แล้ว fallback ไปใช้ personal credential แทน ให้ caller
    ยังพยายามรันต่อได้ (ตาม convention เดียวกับฟังก์ชันอื่นในโปรเจกต์นี้ที่ไม่ปล่อยให้ auth setup
    ผิดพลาดไป block ทั้ง pipeline เงียบๆ — เห็น warning ชัดเจนแทน)
    """
    import ee

    sa_email = os.environ.get(GEE_SERVICE_ACCOUNT_EMAIL_ENV)
    sa_key_path = os.environ.get(GEE_SERVICE_ACCOUNT_KEY_ENV)

    if sa_email and sa_key_path:
        key_path = Path(sa_key_path)
        if key_path.exists():
            try:
                credentials = ee.ServiceAccountCredentials(sa_email, str(key_path))
                ee.Initialize(credentials=credentials, project=gee_project)
                logger.info(
                    "GEE auth: ใช้ Service Account (%s, key=%s) -- เหมาะกับ scheduled task",
                    sa_email, key_path.name,
                )
                return "service_account"
            except Exception as exc:
                logger.warning(
                    "GEE auth: ตั้งค่า Service Account ไว้ (%s) แต่ ee.Initialize() ด้วย credential "
                    "นี้ล้มเหลว (%s) -- fallback ไปใช้ personal credential แทน ตรวจสอบว่า service "
                    "account ลงทะเบียนกับ Earth Engine แล้วหรือยัง "
                    "(https://code.earthengine.google.com/register) และ key ยังไม่หมดอายุ/ถูกลบ",
                    sa_email, exc,
                )
        else:
            logger.warning(
                "GEE auth: ตั้ง env var %s ไว้ (%s) แต่ไม่พบไฟล์จริงที่ %s -- fallback ไปใช้ "
                "personal credential แทน ตรวจสอบ path ให้ถูกต้อง",
                GEE_SERVICE_ACCOUNT_KEY_ENV, sa_email, key_path,
            )
    elif sa_email or sa_key_path:
        logger.warning(
            "GEE auth: ตั้ง env var ไว้แค่ตัวเดียว (%s=%s, %s=%s) -- ต้องตั้งให้ครบทั้งคู่ถึงจะใช้ "
            "Service Account ได้ fallback ไปใช้ personal credential แทน",
            GEE_SERVICE_ACCOUNT_EMAIL_ENV, sa_email, GEE_SERVICE_ACCOUNT_KEY_ENV, sa_key_path,
        )

    ee.Initialize(project=gee_project)
    logger.info(
        "GEE auth: ใช้ personal credential (ee.Authenticate() แบบ interactive ที่เคยรันไว้ก่อนหน้า) "
        "-- ไม่เหมาะกับ scheduled task ระยะยาว (token อาจหมดอายุโดยไม่มีคนคอย login ซ้ำ) ตั้ง env "
        "var %s / %s ให้ครบเพื่อเปลี่ยนเป็น Service Account (ดู docstring หัวไฟล์ gee_auth.py)",
        GEE_SERVICE_ACCOUNT_EMAIL_ENV, GEE_SERVICE_ACCOUNT_KEY_ENV,
    )
    return "personal_credential"

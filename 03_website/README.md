# 03_website — หมายเหตุการพึ่งพา external CDN

## Chart.js: vendored ไว้ local แล้ว (ไม่พึ่ง CDN อีกต่อไป)

**ปัญหาเดิม:** `inflow-forecast.html` และ `water-demand.html` โหลด Chart.js จาก
`https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.4/chart.umd.min.js` — ถ้าเปิดเครื่องที่ไม่มี
อินเทอร์เน็ต (หรือ cdnjs ล่ม/ถูกบล็อก) หน้าเว็บจะพังด้วย error `Chart is not defined` เพราะ global
`Chart` ไม่ถูกสร้างขึ้นเลย

**แก้แล้วโดย:** ดาวน์โหลด Chart.js v4.4.4 ตัวเดียวกับที่เคยใช้ (จาก npm package ทางการ `chart.js@4.4.4`
ซึ่งเป็นแหล่งเดียวกับที่ cdnjs ใช้ build) มา minify ด้วย terser แล้วเก็บไว้ที่:

```
03_website/assets/js/chart.umd.min.js   (~200 KB, UMD build — ใช้ <script src="..."> ตรงๆ ได้เลย)
```

ไฟล์ .html ทั้งสองไฟล์ที่ใช้กราฟ (`inflow-forecast.html`, `water-demand.html`) แก้ให้ชี้มาที่ไฟล์ local
นี้แทน:

```html
<script src="assets/js/chart.umd.min.js"></script>
```

**ทดสอบแล้ว:** โหลดหน้าเว็บทั้งสองในสภาพแวดล้อมที่ไม่มีเส้นทางออกอินเทอร์เน็ตไปยัง cdnjs.cloudflare.com
เลย (จำลองสถานการณ์ปิด Wi-Fi/ถอดสาย LAN) ยืนยันว่า `window.Chart` ถูกสร้างขึ้นเป็น function จริง
(`Chart.version === "4.4.4"`) และไม่มี error `Chart is not defined` เกิดขึ้นอีก — กราฟ render ได้ปกติ

**ถ้าต้องอัปเดตเวอร์ชัน Chart.js ในอนาคต:**

```bash
npm install chart.js@<version>
npx terser node_modules/chart.js/dist/chart.umd.js -c -m --comments false -o chart.umd.min.js
# แล้วคัดลอกไฟล์ที่ได้ไปทับ 03_website/assets/js/chart.umd.min.js
```

**หน้าใหม่ที่จะมีกราฟในอนาคต** (เช่นถ้า `monitoring.html` เพิ่มกราฟทีหลัง) ให้ใช้
`<script src="assets/js/chart.umd.min.js"></script>` (หรือ path สัมพัทธ์ที่ถูกต้องตามตำแหน่งไฟล์)
แทนการดึงจาก CDN ตรงๆ ด้วย เพื่อคงความ offline-capable ของเว็บไซต์นี้ไว้

## ส่วนอื่นที่ยังพึ่งพา external CDN อยู่ (ยังไม่ได้แก้ในรอบนี้)

เพื่อไม่ให้เข้าใจผิดว่าทั้งเว็บไซต์ทำงานแบบ offline 100% แล้ว — ยังมี 2 จุดที่ต้องมีอินเทอร์เน็ตอยู่:

- **Google Fonts** (ทุกหน้า) — โหลดจาก `fonts.googleapis.com`/`fonts.gstatic.com` ถ้าไม่มีเน็ต
  ฟอนต์จะ fallback ไปใช้ฟอนต์ระบบแทน (ไม่กระทบการทำงานของหน้าเว็บ แค่หน้าตาเปลี่ยนเล็กน้อย)
- **Leaflet + tile layers** (`gis-map.html` เท่านั้น) — โหลด Leaflet library จาก `unpkg.com` และ
  แผนที่พื้นหลัง (OpenStreetMap/CartoDB/ArcGIS) เป็น tile server ออนไลน์ ถ้าไม่มีเน็ตแผนที่จะไม่ขึ้นเลย
  (ยังไม่ได้แก้ในรอบนี้ — ถ้าต้องการให้หน้า GIS ทำงาน offline ด้วย จะต้อง vendor Leaflet.js เหมือนที่ทำกับ
  Chart.js และเก็บ tile ภาพนิ่งไว้ local ซึ่งเป็นงานคนละขอบเขต)

สรุป: **Chart.js (กราฟพยากรณ์น้ำ) ทำงานแบบ offline-capable แล้ว** ส่วนฟอนต์และแผนที่ GIS ยังต้องมีเน็ต

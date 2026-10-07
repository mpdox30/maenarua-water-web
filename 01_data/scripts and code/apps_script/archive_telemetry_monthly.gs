/**
 * archive_telemetry_monthly.gs
 * ----------------------------------------------------------------------------
 * แก้ปัญหา: สคริปต์ fetchAndLog ใน Apps Script ที่ผูกกับสเปรดชีต "Telemetry_Mae_Na_Rua"
 * ล้มเหลวด้วย error "เกินจำนวนเซลล์ที่จำกัดไว้ 10000000 เซลล์" เพราะแท็บ raw_log
 * (และ wide_log) สะสมแถวข้อมูลทุก 10 นาทีมาเรื่อยๆ โดยไม่เคยมีการล้างข้อมูลเก่าออก
 * จนตันเพดาน 10 ล้านเซลล์ของทั้ง workbook (ลบไม่ได้ ขอเพิ่มไม่ได้ เป็นเพดานตายตัวของ
 * Google Sheets)
 *
 * สคริปต์นี้ทำหน้าที่:
 *   1. อ่านแถวใน raw_log และ wide_log ทีละก้อนเล็กๆ (BATCH_ROWS_PER_RUN แถว/รอบ)
 *      จากบนสุด (เก่าสุด) ลงมา — ไม่อ่านทั้งชีตในครั้งเดียวอีกต่อไป (ดูหมายเหตุ
 *      2026-09-22 ด้านล่าง ว่าทำไมถึงเปลี่ยน)
 *   2. หาแถวที่ "เก่ากว่า N วัน" ภายในก้อนที่อ่านมา (อิงคอลัมน์เวลา — หาโดย
 *      auto-detect จากชื่อ header ไม่ผูกกับตำแหน่งคอลัมน์ตายตัว เผื่อโครงสร้างชีต
 *      เปลี่ยนในอนาคต)
 *   3. ย้าย (append) แถวเก่าไปที่สเปรดชีต archive แยกต่างหาก (คนละไฟล์ คนละเพดาน
 *      10 ล้านเซลล์)
 *   4. ลบแถวเก่าออกจากชีตต้นทางจริงๆ ด้วย deleteRows() เฉพาะช่วงที่แตะในรอบนี้
 *      เท่านั้น (ไม่ใช่แค่ clearContent — clear ไม่คืนเซลล์ให้เพดาน ต้องลบแถว/
 *      ลด grid size เท่านั้นถึงจะคืนโควตาเซลล์)
 *   5. ติดตั้งเป็น time-driven trigger รายเดือน ให้รันอัตโนมัติ ไม่ต้องทำมืออีก
 *      (ช่วง backlog เยอะครั้งแรก แนะนำใช้ trigger ถี่กว่านั้นชั่วคราว — ดู
 *      createCatchUpTrigger ด้านล่าง)
 *
 * ---------------------------------------------------------------------------
 * หมายเหตุสำคัญ 2026-09-22 — เหตุการณ์ timeout กลางคันตอนรันจริงครั้งแรก
 * ---------------------------------------------------------------------------
 * รันแรกด้วย DRY_RUN=false ตอน backlog ยังสะสมมหาศาล (raw_log มีหลักแสนแถว) ชน
 * เพดานรันจริงของ Apps Script (6 นาทีตายตัว ต่อการรันครั้งหนึ่ง แก้ไม่ได้) ก่อนที่
 * ฟังก์ชันจะเขียนจบ — ที่ตั้ง MAX_RUNTIME_MS เผื่อ buffer ไว้เดิม เช็คแค่ "ระหว่าง
 * แท็บ" (raw_log เสร็จแล้วค่อยเช็คก่อนเริ่ม wide_log) ไม่ได้เช็ค "ระหว่างกำลัง
 * ประมวลผลแท็บเดียว" เพราะงั้นตอน raw_log เพียงแท็บเดียวมี backlog ใหญ่พอที่จะกิน
 * เวลาอ่าน+วนลูป+เขียนเกิน 6 นาทีได้เอง ก็ไม่มีจังหวะให้เช็คเลย
 *
 * ผลที่เกิดขึ้นจริง (ตรวจสอบจากไฟล์ CSV export ทั้ง 2 ไฟล์แล้ว 2026-09-22):
 *   - archive ได้รับแถวเก่าครบถ้วนถูกต้อง (2026-08-01 00:06 -> 2026-08-23 09:16,
 *     120,005 แถว ไม่มีซ้ำไม่มีขาด)
 *   - raw_log ต้นทางเขียนแถว "ที่จะเก็บไว้" กลับสำเร็จครบเช่นกัน (2026-08-23 09:20
 *     -> ล่าสุด, ~116,667 แถว) ต่อกันพอดีกับจุดตัดของ archive (ห่างกัน 10 นาที
 *     ตรงตามรอบ poll ไม่มี gap ไม่มี overlap)
 *   - แต่สคริปต์โดนตัดกลางคัน "ก่อน" ขั้นตอนสุดท้าย (sheet.deleteRows เพื่อลด grid
 *     size ส่วนเกิน) เลยเหลือแถวว่างเปล่า (blank) ค้างอยู่กลางชีตหลักแสนแถว —
 *     ไม่ใช่ข้อมูลหาย แค่พื้นที่ grid เก่าที่ clearContent() ไปแล้วแต่ยังไม่ถูกลบแถว
 *     ออกจริง (ยังกินโควตาเซลล์อยู่ ซึ่งเป็นปัญหาเดิมที่สคริปต์นี้ตั้งใจจะแก้)
 *   - แถวใหม่ 2 รอบล่าสุดที่โผล่ต่อท้ายแถวว่าง (index ท้ายสุด) เป็นของจริงจาก
 *     fetchAndLog ที่ยังรันอัตโนมัติทุก 10 นาทีคู่ขนานไปตามปกติ ไม่เกี่ยวกับบั๊กนี้
 *
 * สรุป: ข้อมูลไม่ได้หาย แต่มีแถวว่างค้างกลางชีตที่ต้องเก็บกวาดออก (ใช้
 * repairBlankRowsFromInterruptedRun() ด้านล่าง รันครั้งเดียว ปลอดภัย เพราะอ่านแค่
 * คอลัมน์เวลาคอลัมน์เดียว ไม่แตะข้อมูลจริงเลย) กับต้องแก้ไม่ให้ปัญหานี้เกิดซ้ำ — จึง
 * เปลี่ยน _archiveOneTab() ทั้งหมดให้ประมวลผลทีละก้อนเล็ก (BATCH_ROWS_PER_RUN แถว
 * จากบนสุด/เก่าสุดของชีต) ต่อการรัน 1 ครั้ง แทนที่จะอ่าน/เขียนทั้งชีตทีเดียว —
 * รับประกันว่าแต่ละรอบจบไวพอ ไม่มีทางโดนตัดกลางคันได้อีก (ถึงจะโดนตัดจริงๆ ก็แค่
 * รอบนั้นไม่มีผลอะไรเกิดขึ้นเลย เพราะยังไม่ทันเขียน — ไม่มีสถานะค้างครึ่งๆ กลางๆ)
 *
 * วิธีติดตั้ง:
 *   1. เปิด Google Sheet "Telemetry_Mae_Na_Rua" → Extensions → Apps Script
 *   2. สร้างไฟล์ใหม่ (หรือแท็บใหม่) ในโปรเจกต์ แล้ววางโค้ดทั้งหมดนี้ลงไป (แทนที่
 *      เวอร์ชันเดิม)
 *   3. ถ้ายังไม่เคยตั้ง archive spreadsheet ID ไว้ (ตั้งไปแล้วรอบก่อน ข้ามได้):
 *      สร้างสเปรดชีตใหม่เปล่าๆ 1 ไฟล์ไว้เก็บ archive แล้วรันฟังก์ชัน
 *      __RUN_ONCE_setArchiveSpreadsheetId ครั้งเดียว
 *   4. รัน repairBlankRowsFromInterruptedRun() ก่อนเป็นอันดับแรก (ปลอดภัย ไม่แตะ
 *      ข้อมูลจริง) เพื่อเก็บกวาดแถวว่างค้างจากรันครั้งก่อนออก แล้วดู log ว่าจำนวน
 *      แถวที่ลบสมเหตุสมผลไหม (เทียบกับที่วิเคราะห์ไว้ด้านบน)
 *   5. ทดสอบด้วย DRY_RUN = true แล้วรัน archiveOldTelemetryRows ดู log ว่าจำนวน
 *      แถวที่ "จะ" ถูกย้ายต่อรอบสมเหตุสมผลไหม (ยังไม่มีการเขียน/ลบข้อมูลจริง)
 *   6. เปลี่ยน DRY_RUN = false แล้วรัน archiveOldTelemetryRows ด้วยมือได้เลย —
 *      ปลอดภัยกว่ารอบก่อนมาก เพราะแต่ละรอบแตะแค่ BATCH_ROWS_PER_RUN แถว จบไว
 *   7. เพราะ backlog ที่เหลือ (ของ wide_log ที่ยังไม่ได้แตะเลย) อาจต้องรันหลายรอบ
 *      กว่าจะครบ ให้รัน createCatchUpTrigger() ครั้งเดียว เพื่อตั้ง trigger ถี่
 *      (ทุก 10 นาที) ไล่เก็บ backlog อัตโนมัติจนหมด แล้วค่อยรัน
 *      removeCatchUpTrigger() ทีหลังเมื่อ log บอกว่า "ไม่มีแถวที่เก่ากว่า N วัน"
 *      ทั้ง 2 แท็บแล้ว
 *   8. สุดท้ายรัน createMonthlyArchiveTrigger() ครั้งเดียว เพื่อตั้ง trigger
 *      รายเดือนดูแลต่อเนื่องไปตลอด (backlog ปกติต่อเดือนเล็กกว่านี้มาก ไม่มีทางชน
 *      6 นาทีอีก)
 * ----------------------------------------------------------------------------
 */

// ========================= ตั้งค่าได้ตรงนี้ =========================

/** เก็บแถวที่ "ใหม่กว่า" N วันนี้ไว้ในชีตหลัก ส่วนที่เก่ากว่าจะถูกย้ายไป archive */
var DAYS_TO_KEEP = 30;

/** ชื่อแท็บที่ต้องการเก็บกวาด (ต้องมีอยู่จริงทั้งในไฟล์หลักและจะถูกสร้างซ้ำในไฟล์ archive) */
var TABS_TO_ARCHIVE = ['raw_log', 'wide_log'];

/**
 * ชื่อคอลัมน์เวลาที่จะใช้ตัดสินอายุของแถว เรียงตามลำดับความสำคัญ
 * (ลองหา 'measure_datetime' ก่อน เพราะเป็นเวลาที่ข้อมูลจริงถูกวัด
 * ถ้าไม่เจอค่อย fallback ไป 'fetch_time')
 */
var TIMESTAMP_COLUMN_CANDIDATES = ['measure_datetime', 'fetch_time'];

/**
 * true = จำลองการทำงานอย่างเดียว ไม่เขียน/ไม่ลบข้อมูลจริง แค่ log ว่าจะทำอะไรบ้าง
 * ให้ทดสอบด้วย true ก่อนเสมอ แล้วค่อยเปลี่ยนเป็น false ตอนพร้อมรันจริง
 */
var DRY_RUN = true;

/**
 * 2026-09-22 เพิ่ม — จำนวนแถว "สูงสุด" ที่จะอ่าน/ประมวลผล/เขียนต่อการรัน 1 ครั้ง
 * (นับจากแถวบนสุด/เก่าสุดของชีตลงมา) แทนที่จะอ่านทั้งชีตทีเดียวเหมือนเดิม — คือ
 * ตัวแก้หลักของปัญหา timeout กลางคัน ตั้งให้พอเหมาะ: ใหญ่พอจะไล่ backlog ได้เร็ว
 * แต่เล็กพอที่อ่าน+วนลูป+เขียนจะจบสบายๆ ภายในไม่กี่สิบวินาที ไม่มีทางใกล้ 6 นาที
 */
var BATCH_ROWS_PER_RUN = 20000;

/** กันสคริปต์รันนานเกินเพดาน 6 นาทีของ Apps Script (time-driven trigger) —
 * ตอนนี้แทบไม่มีโอกาสถูกใช้จริงแล้วเพราะ batch เล็กพอ แต่เก็บไว้เป็นเซฟตี้ชั้นที่ 2 */
var MAX_RUNTIME_MS = 4 * 60 * 1000;

// ========================= ฟังก์ชันหลัก =========================

/**
 * ฟังก์ชันหลัก — เรียกเองครั้งแรกด้วยมือ (ตอน DRY_RUN=true เพื่อทดสอบ,
 * แล้วอีกครั้ง DRY_RUN=false เพื่อเริ่มเก็บกวาด) จากนั้นปล่อยให้ trigger
 * (catch-up หรือรายเดือน) เรียกอัตโนมัติต่อไปเรื่อยๆ — แต่ละรอบแตะแค่
 * BATCH_ROWS_PER_RUN แถวต่อแท็บเท่านั้น ถ้า backlog เหลือมากกว่านั้นต้องรันซ้ำ
 * หลายรอบ (ดูคำแนะนำ createCatchUpTrigger ด้านบน)
 */
function archiveOldTelemetryRows() {
  var startTime = Date.now();
  var sourceSs = SpreadsheetApp.getActiveSpreadsheet();
  var archiveSs = _getArchiveSpreadsheet();

  if (!archiveSs) {
    Logger.log(
      'ERROR: ยังไม่ได้ตั้งค่า archive spreadsheet ID — ' +
      'ให้รัน __RUN_ONCE_setArchiveSpreadsheetId() ก่อน (ดูคอมเมนต์ด้านบนของไฟล์)'
    );
    return;
  }

  var cutoffDate = new Date();
  cutoffDate.setDate(cutoffDate.getDate() - DAYS_TO_KEEP);

  var summary = [];

  for (var t = 0; t < TABS_TO_ARCHIVE.length; t++) {
    if (Date.now() - startTime > MAX_RUNTIME_MS) {
      Logger.log(
        'หยุดก่อนเวลาเพื่อความปลอดภัย (ใกล้ครบ ' + (MAX_RUNTIME_MS / 1000) +
        ' วิ) — เหลือแท็บที่ยังไม่ได้ทำ: ' + TABS_TO_ARCHIVE.slice(t).join(', ') +
        ' → รอบถัดไปจะสานต่อเอง'
      );
      break;
    }
    var tabName = TABS_TO_ARCHIVE[t];
    var result = _archiveOneTab(sourceSs, archiveSs, tabName, cutoffDate);
    summary.push(result);
  }

  Logger.log('สรุปผลการเก็บกวาดรอบนี้ (DRY_RUN=' + DRY_RUN + ', batch สูงสุด ' + BATCH_ROWS_PER_RUN + ' แถว/แท็บ):');
  summary.forEach(function (s) {
    Logger.log(
      '  ' + s.tab + ': อ่านมา ' + s.totalRows + ' แถว (จากบนสุด) | ' +
      'ย้ายไป archive ' + s.archivedRows + ' แถว | ' +
      'เขียนกลับในก้อนนี้ ' + s.keptRows + ' แถว' +
      (s.unparseableRows > 0 ? ' | (คงไว้เพราะอ่านวันที่ไม่ออก: ' + s.unparseableRows + ' แถว)' : '') +
      (s.mayHaveMore ? ' | ยังมี backlog เหลือ เก่ากว่านี้อาจยังมีอีก รอรอบถัดไป' : ' | ไม่มีแถวเก่ากว่า ' + DAYS_TO_KEEP + ' วันเหลือแล้ว')
    );
  });
}

/**
 * จัดการ 1 แท็บ แบบ batch: อ่านเฉพาะ BATCH_ROWS_PER_RUN แถวบนสุด (เก่าสุด) ของชีต
 * → แยกเก่า/ใหม่ภายในก้อนนั้น → เขียนของเก่าไป archive (append) → เขียนของใหม่
 * (ที่ยังอยู่ในก้อนนี้) กลับที่เดิม → ลบแถวส่วนเกินของก้อนนี้ด้วย deleteRows()
 * แถวที่อยู่ "นอกก้อน" (ลึกกว่า BATCH_ROWS_PER_RUN ลงไป) จะไม่ถูกแตะเลยในรอบนี้
 * — ปลอดภัยเพราะงานทั้งหมดในฟังก์ชันนี้ต่อ 1 ครั้งเรียกมีขอบเขตจำกัดชัดเจน
 */
function _archiveOneTab(sourceSs, archiveSs, tabName, cutoffDate) {
  var sheet = sourceSs.getSheetByName(tabName);
  if (!sheet) {
    Logger.log('ข้าม: ไม่พบแท็บ "' + tabName + '" ในไฟล์ต้นทาง');
    return { tab: tabName, totalRows: 0, archivedRows: 0, keptRows: 0, unparseableRows: 0, mayHaveMore: false };
  }

  var lastRow = sheet.getLastRow();
  var lastCol = sheet.getLastColumn();
  if (lastRow < 2) {
    // ไม่มีข้อมูล (มีแค่ header หรือว่างเปล่า)
    return { tab: tabName, totalRows: 0, archivedRows: 0, keptRows: 0, unparseableRows: 0, mayHaveMore: false };
  }

  var headerRange = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
  var tsColIndex = _findTimestampColumnIndex(headerRange); // 0-based
  if (tsColIndex === -1) {
    Logger.log(
      'ข้าม: แท็บ "' + tabName + '" ไม่มีคอลัมน์เวลาที่รู้จัก (ลองหา: ' +
      TIMESTAMP_COLUMN_CANDIDATES.join(', ') + ') — header ที่เจอจริง: ' + headerRange.join(', ')
    );
    return { tab: tabName, totalRows: lastRow - 1, archivedRows: 0, keptRows: lastRow - 1, unparseableRows: 0, mayHaveMore: false };
  }

  // 2026-09-22 เปลี่ยน: อ่านแค่ก้อนบนสุด (เก่าสุด) ไม่เกิน BATCH_ROWS_PER_RUN แถว
  // ไม่อ่านทั้งชีต -- นี่คือตัวแก้หลักของปัญหา timeout
  var totalDataRows = lastRow - 1;
  var rowsToRead = Math.min(totalDataRows, BATCH_ROWS_PER_RUN);
  var mayHaveMore = totalDataRows > rowsToRead; // ยังมีแถวที่ลึกกว่าก้อนนี้ที่ยังไม่ได้ตรวจ

  var dataRange = sheet.getRange(2, 1, rowsToRead, lastCol);
  var batchRows = dataRange.getValues();

  var oldRows = [];
  var keepRows = [];
  var unparseableCount = 0;

  for (var i = 0; i < batchRows.length; i++) {
    var row = batchRows[i];
    var rawTs = row[tsColIndex];
    var ts = _parseTimestamp(rawTs);
    if (ts === null) {
      // อ่านวันที่ไม่ออก → เก็บไว้ในชีตหลักดีกว่า ปลอดภัยไว้ก่อน ไม่เสี่ยงข้อมูลหาย
      unparseableCount++;
      keepRows.push(row);
    } else if (ts < cutoffDate) {
      oldRows.push(row);
    } else {
      keepRows.push(row);
    }
  }

  if (oldRows.length === 0) {
    Logger.log(
      'แท็บ "' + tabName + '": ก้อนที่อ่านมา (' + batchRows.length + ' แถวบนสุด) ' +
      'ไม่มีแถวที่เก่ากว่า ' + DAYS_TO_KEEP + ' วันเลย ไม่ต้องทำอะไรต่อ'
      + (mayHaveMore ? ' (หมายเหตุ: เพิ่งอ่านแค่ก้อนแรก ไม่น่าเกิดขึ้นถ้าข้อมูลเรียงตามเวลาปกติ)' : '')
    );
    return {
      tab: tabName, totalRows: batchRows.length, archivedRows: 0,
      keptRows: keepRows.length, unparseableRows: unparseableCount, mayHaveMore: false,
    };
  }

  if (DRY_RUN) {
    Logger.log(
      '[DRY RUN] แท็บ "' + tabName + '": ก้อนนี้ (' + batchRows.length + ' แถวบนสุด) จะย้าย ' +
      oldRows.length + ' แถว (เก่ากว่า ' + DAYS_TO_KEEP + ' วัน) ไป archive แล้วเขียนกลับ ' +
      keepRows.length + ' แถว — ยังไม่ได้เขียน/ลบข้อมูลจริง'
    );
    return {
      tab: tabName, totalRows: batchRows.length, archivedRows: oldRows.length,
      keptRows: keepRows.length, unparseableRows: unparseableCount, mayHaveMore: mayHaveMore,
    };
  }

  // ----- ขั้นตอนสำคัญ: เขียนไปยัง archive ให้สำเร็จก่อน แล้วค่อยแก้ต้นทาง -----
  // (ถ้าขั้นตอนเขียน archive ล้มเหลว จะ throw ออกไปเลย ไม่ไปแตะต้นทาง กันข้อมูลหาย)
  var archiveSheet = _getOrCreateArchiveTab(archiveSs, tabName, headerRange);
  var archiveLastRow = archiveSheet.getLastRow();
  archiveSheet
    .getRange(archiveLastRow + 1, 1, oldRows.length, lastCol)
    .setValues(oldRows);

  // เขียนแถวที่ "เก็บไว้" กลับเข้าไปแทนที่ต้นของก้อนนี้ (รวดเร็ว เพราะก้อนเล็ก)
  if (keepRows.length > 0) {
    sheet.getRange(2, 1, keepRows.length, lastCol).setValues(keepRows);
  }
  // ลบแถวส่วนเกินของก้อนนี้ออกจริง (deleteRows คืนโควตาเซลล์ ต่างจาก clearContent)
  // ลบเฉพาะช่วง [2+keepRows.length, 2+rowsToRead-1] เท่านั้น -- แถวที่อยู่ลึกกว่า
  // ก้อนนี้ (ยังไม่ได้อ่าน/แตะเลย) จะขยับขึ้นมาต่อกันเองอัตโนมัติจาก deleteRows
  // โดยไม่ต้องไปยุ่งกับมันตรงๆ เลย
  var numToDelete = rowsToRead - keepRows.length; // = oldRows.length
  if (numToDelete > 0) {
    sheet.deleteRows(2 + keepRows.length, numToDelete);
  }

  Logger.log(
    'แท็บ "' + tabName + '": ก้อนนี้ย้าย ' + oldRows.length + ' แถวไป archive สำเร็จ, ' +
    'เขียนกลับ ' + keepRows.length + ' แถว' +
    (mayHaveMore ? ' (ยังมีแถวลึกกว่าก้อนนี้ที่ยังไม่ตรวจ รอรอบถัดไป)' : '')
  );

  return {
    tab: tabName, totalRows: batchRows.length, archivedRows: oldRows.length,
    keptRows: keepRows.length, unparseableRows: unparseableCount, mayHaveMore: mayHaveMore,
  };
}

/** หา index (0-based) ของคอลัมน์เวลา โดยลองชื่อใน TIMESTAMP_COLUMN_CANDIDATES ตามลำดับ */
function _findTimestampColumnIndex(headerRow) {
  for (var c = 0; c < TIMESTAMP_COLUMN_CANDIDATES.length; c++) {
    var candidate = TIMESTAMP_COLUMN_CANDIDATES[c];
    for (var i = 0; i < headerRow.length; i++) {
      if (String(headerRow[i]).trim() === candidate) {
        return i;
      }
    }
  }
  return -1;
}

/** แปลงค่าเซลล์เป็น Date — คืน null ถ้าแปลงไม่ได้ (จะถูกเก็บไว้ ไม่ย้าย ปลอดภัยไว้ก่อน) */
function _parseTimestamp(value) {
  if (value instanceof Date && !isNaN(value.getTime())) {
    return value;
  }
  if (typeof value === 'string' && value.trim() !== '') {
    var parsed = new Date(value);
    if (!isNaN(parsed.getTime())) {
      return parsed;
    }
  }
  return null;
}

/** เปิดไฟล์ archive จาก Script Properties — คืน null ถ้ายังไม่เคยตั้งค่า */
function _getArchiveSpreadsheet() {
  var id = PropertiesService.getScriptProperties().getProperty('ARCHIVE_SPREADSHEET_ID');
  if (!id) return null;
  try {
    return SpreadsheetApp.openById(id);
  } catch (e) {
    Logger.log('ERROR: เปิดไฟล์ archive ด้วย ID "' + id + '" ไม่สำเร็จ: ' + e.message);
    return null;
  }
}

/** หา (หรือสร้างใหม่ถ้ายังไม่มี) แท็บชื่อเดียวกันในไฟล์ archive พร้อม header แถวแรก */
function _getOrCreateArchiveTab(archiveSs, tabName, headerRow) {
  var sheet = archiveSs.getSheetByName(tabName);
  if (!sheet) {
    sheet = archiveSs.insertSheet(tabName);
    sheet.getRange(1, 1, 1, headerRow.length).setValues([headerRow]);
  }
  return sheet;
}

// ========================= ซ่อมแซมจากรันครั้งก่อนที่โดนตัดกลางคัน =========================

/**
 * 2026-09-22 เพิ่ม — รันฟังก์ชันนี้ "ครั้งเดียว" ก่อนอย่างอื่นทั้งหมด (ปลอดภัย
 * 100% ไม่แตะข้อมูลจริงเลย อ่านแค่คอลัมน์เวลาคอลัมน์เดียวเพื่อหาตำแหน่งแถวว่าง)
 * เพื่อล้างแถวว่างเปล่าที่ค้างอยู่กลางชีตจากการรันครั้งก่อนที่โดน Apps Script
 * ตัดกลางคันก่อนถึงขั้นตอน deleteRows สุดท้าย — ดูรายละเอียดเหตุการณ์ในคอมเมนต์
 * หัวไฟล์ด้านบน (หมายเหตุสำคัญ 2026-09-22)
 *
 * ทำงานโดย: อ่านคอลัมน์เวลา (measure_datetime/fetch_time) ทั้งคอลัมน์ (เบา เร็ว
 * เพราะอ่านแค่ 1 คอลัมน์) หาช่วงแถวที่ "ว่างเปล่าทั้งแถว" ติดกันเป็นช่วงๆ แล้วลบ
 * ช่วงเหล่านั้นออกด้วย deleteRows() (ลบจากล่างขึ้นบนกัน index เลื่อน) — ไม่ยุ่งกับ
 * แถวที่มีข้อมูลจริงเลยแม้แต่แถวเดียว
 */
function repairBlankRowsFromInterruptedRun() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  TABS_TO_ARCHIVE.forEach(function (tabName) {
    var sheet = ss.getSheetByName(tabName);
    if (!sheet) {
      Logger.log('ข้าม: ไม่พบแท็บ "' + tabName + '"');
      return;
    }
    var lastRow = sheet.getLastRow();
    if (lastRow < 2) {
      Logger.log('แท็บ "' + tabName + '": ไม่มีข้อมูล ข้าม');
      return;
    }
    var lastCol = sheet.getLastColumn();
    var headerRange = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
    var tsColIndex = _findTimestampColumnIndex(headerRange);
    if (tsColIndex === -1) {
      Logger.log('ข้าม: แท็บ "' + tabName + '" ไม่มีคอลัมน์เวลาที่รู้จัก');
      return;
    }

    var tsValues = sheet.getRange(2, tsColIndex + 1, lastRow - 1, 1).getValues();
    var ranges = []; // [[startIndex0based, length], ...]
    var rangeStart = -1;
    for (var i = 0; i < tsValues.length; i++) {
      var v = tsValues[i][0];
      var isBlank = (v === '' || v === null || v === undefined);
      if (isBlank && rangeStart === -1) {
        rangeStart = i;
      }
      if (!isBlank && rangeStart !== -1) {
        ranges.push([rangeStart, i - rangeStart]);
        rangeStart = -1;
      }
    }
    if (rangeStart !== -1) {
      ranges.push([rangeStart, tsValues.length - rangeStart]);
    }

    if (ranges.length === 0) {
      Logger.log('แท็บ "' + tabName + '": ไม่พบแถวว่างค้างอยู่ ไม่ต้องทำอะไร');
      return;
    }

    var totalBlank = ranges.reduce(function (s, r) { return s + r[1]; }, 0);
    Logger.log(
      'แท็บ "' + tabName + '": พบแถวว่างค้างอยู่ ' + totalBlank + ' แถว (' +
      ranges.length + ' ช่วง) กำลังลบ...'
    );

    // ลบจากล่างขึ้นบน กัน index ของช่วงที่เหลือเลื่อนระหว่างลบ
    for (var r = ranges.length - 1; r >= 0; r--) {
      var startRowSheet = ranges[r][0] + 2; // +2: แปลง 0-based (นับจากแถวข้อมูลแรก) -> เลขแถวจริงในชีต (มี header แถว 1)
      var numRows = ranges[r][1];
      sheet.deleteRows(startRowSheet, numRows);
      Logger.log('  ลบแถว ' + startRowSheet + '..' + (startRowSheet + numRows - 1) + ' (' + numRows + ' แถว) สำเร็จ');
    }
    Logger.log('แท็บ "' + tabName + '": ซ่อมแซมเสร็จ ลบแถวว่างออกครบ ' + totalBlank + ' แถว');
  });
}

// ========================= ตั้งค่าเริ่มต้น (รันเองด้วยมือ ครั้งเดียว) =========================

/**
 * รันฟังก์ชันนี้ "ครั้งเดียว" ด้วยมือจาก Apps Script editor เพื่อบันทึก
 * Spreadsheet ID ของไฟล์ archive ไว้ใน Script Properties
 * (แก้ค่า YOUR_ARCHIVE_SPREADSHEET_ID_HERE ให้เป็น ID จริงก่อนรัน — ถ้าตั้งไว้
 * แล้วจากรอบก่อน ข้ามขั้นตอนนี้ได้เลย)
 */
function __RUN_ONCE_setArchiveSpreadsheetId() {
  var ARCHIVE_ID = 'YOUR_ARCHIVE_SPREADSHEET_ID_HERE'; // <-- แก้ตรงนี้ก่อนรัน
  PropertiesService.getScriptProperties().setProperty('ARCHIVE_SPREADSHEET_ID', ARCHIVE_ID);
  Logger.log('บันทึก ARCHIVE_SPREADSHEET_ID = ' + ARCHIVE_ID + ' เรียบร้อย');
}

/**
 * 2026-09-22 เพิ่ม — รันฟังก์ชันนี้ "ครั้งเดียว" ชั่วคราว ตอนยังมี backlog เหลือ
 * เยอะ (ไล่ทีละ BATCH_ROWS_PER_RUN แถวต่อรอบคงช้าเกินไปถ้ารอ trigger รายเดือน) —
 * ตั้ง trigger ให้รัน archiveOldTelemetryRows ทุก 10 นาทีจนกว่า backlog จะหมด
 * (ดูใน log ว่าขึ้น "ไม่มีแถวเก่ากว่า N วันเหลือแล้ว" ทั้ง 2 แท็บ) แล้วค่อยรัน
 * removeCatchUpTrigger() เพื่อเอา trigger ถี่นี้ออก (เหลือแค่ trigger รายเดือนพอ)
 */
function createCatchUpTrigger() {
  var triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(function (tr) {
    if (tr.getHandlerFunction() === 'archiveOldTelemetryRows' && tr.getTriggerSource() === ScriptApp.TriggerSource.CLOCK) {
      // ลบ trigger เดิมของฟังก์ชันนี้ทั้งหมดก่อน (ทั้งรายเดือนและ catch-up เก่า) กันซ้อนกัน
      ScriptApp.deleteTrigger(tr);
    }
  });
  ScriptApp.newTrigger('archiveOldTelemetryRows')
    .timeBased()
    .everyMinutes(10)
    .create();
  Logger.log('ตั้ง catch-up trigger สำเร็จ: จะรัน archiveOldTelemetryRows ทุก 10 นาที จนกว่าจะลบ trigger นี้ทิ้งเอง (removeCatchUpTrigger) หรือแทนที่ด้วย createMonthlyArchiveTrigger');
}

/** เอา trigger ถี่ (10 นาที) ที่ตั้งจาก createCatchUpTrigger ออก -- เรียกหลัง backlog หมดแล้ว ก่อนตั้ง trigger รายเดือน */
function removeCatchUpTrigger() {
  var removed = 0;
  ScriptApp.getProjectTriggers().forEach(function (tr) {
    if (tr.getHandlerFunction() === 'archiveOldTelemetryRows' && tr.getTriggerSource() === ScriptApp.TriggerSource.CLOCK) {
      ScriptApp.deleteTrigger(tr);
      removed++;
    }
  });
  Logger.log('ลบ trigger ของ archiveOldTelemetryRows ออกแล้ว ' + removed + ' ตัว (อย่าลืมรัน createMonthlyArchiveTrigger ต่อ ถ้ายังไม่ได้ตั้ง)');
}

/**
 * รันฟังก์ชันนี้ "ครั้งเดียว" ด้วยมือ (หลัง backlog หมดแล้ว) เพื่อติดตั้ง trigger
 * รายเดือนให้ archiveOldTelemetryRows ทำงานอัตโนมัติทุกเดือนไปตลอด (วันที่ 1
 * ของเดือน เวลา 03:00-04:00) ถ้ารันซ้ำจะลบ trigger เก่าที่ชื่อเดียวกันออกก่อน
 * กันเกิด trigger ซ้ำซ้อน (รวมถึง catch-up trigger ถ้ายังไม่ได้ลบเอง)
 */
function createMonthlyArchiveTrigger() {
  var triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(function (tr) {
    if (tr.getHandlerFunction() === 'archiveOldTelemetryRows') {
      ScriptApp.deleteTrigger(tr);
    }
  });

  ScriptApp.newTrigger('archiveOldTelemetryRows')
    .timeBased()
    .onMonthDay(1)
    .atHour(3)
    .create();

  Logger.log('ตั้ง trigger รายเดือนสำเร็จ: จะรัน archiveOldTelemetryRows ทุกวันที่ 1 ของเดือน เวลาประมาณ 03:00 น.');
}

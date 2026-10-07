"""
compare_windows_colab_run.py
=============================
2026-09-20 เพิ่ม — สคริปต์ตรวจสอบว่าผลลัพธ์ที่ data_pipeline.py คำนวณได้บน Windows (Task Scheduler)
กับบน Colab (รันมือ) ตรงกันจริงหรือไม่ ในวันเดียวกัน

ที่มา: ผู้ใช้รันทั้ง 2 ระบบทุกวัน (Colab เป็นหลัก, Windows เป็น mirror) ต้องการวิธีตรวจสอบว่าผลตรงกัน
โดยไม่ต้องนั่งไล่เทียบ log ทีละบรรทัดด้วยมือทุกครั้ง

วิธีทำงาน: ทั้ง 2 ระบบ commit ผลลัพธ์ (03_website/assets/data/latest.json) เข้า git repo เดียวกัน
เสมอ ด้วย commit message ที่แยกแยะได้ชัดเจน:
  - Windows: "Auto-update: ml_features_live.csv + latest.json ..."   (author: mpdox30)
  - Colab:   "Auto-update: pipeline data ... (Colab)"                 (author: Mae Na Rua Pipeline (Colab))
สคริปต์นี้หา commit ล่าสุดของแต่ละฝั่งสำหรับวันที่ระบุ (default = วันนี้), git show เนื้อหา
latest.json ของทั้งคู่ออกมา แล้วเทียบทุก field แบบ flatten (รวม nested dict/list) — เพราะทั้ง 2
รันจากข้อมูลภายนอกชุดเดียวกัน (โทรมาตร, SAR result ที่ commit ไว้ล่วงหน้า, CHIRPS/ERA5T/MEI ณ
ช่วงเวลาใกล้เคียงกัน) ค่าที่ควรตรงกันเป๊ะ 100% ยกเว้นไม่กี่ field ที่ "ควรต่างกันเป็นปกติ" อยู่แล้ว:
  - run_timestamp                : เวลาที่รันจริง ต่างกันแน่นอน (คนละเครื่อง คนละเวลา)
  - telemetry.readings[*].*      : ยืนยันจาก log ทุกรอบว่าเป็น "mock data - ยังไม่ได้เชื่อม API จริง"
                                    (TELEMETRY_API_URL is None) จึงสุ่มค่าใหม่ทุกครั้งที่รัน โดยดีไซน์
  - crop_classification.age_days : คำนวณจาก (run_timestamp - SAR result timestamp) จึงต่างกันเล็กน้อย
                                    ตามเวลาที่รันจริง ไม่ใช่สัญญาณว่าข้อมูลไม่ตรงกัน

field อื่นนอกเหนือจากนี้ (predictions, crop_area_ha, climate features, reservoir inflow, ฯลฯ) ถ้า
ต่างกัน = สัญญาณว่ามีอะไรผิดปกติจริง (เช่น environment ไม่ sync, SAR result คนละเวอร์ชัน, โมเดลคนละไฟล์)
ต้องตรวจสอบทันที ไม่ควรมองข้าม

ทดสอบแล้ว (2026-09-20) กับข้อมูลจริง 2 วัน: 2026-09-19 (418 field, ต่างแค่ 12 field ที่คาดไว้แล้ว)
และ 2026-09-20 (417 field, ต่างแค่ 11 field ที่คาดไว้แล้ว) -- ทั้ง 2 วัน UNEXPECTED differing fields = 0

การใช้งาน:
  cd "01_data/scripts and code/pipeline"
  python compare_windows_colab_run.py                  # เทียบของวันนี้ (auto-detect commit ล่าสุด)
  python compare_windows_colab_run.py --date 2026-09-19 # เทียบของวันที่ระบุ
  python compare_windows_colab_run.py --win-ref <hash> --colab-ref <hash>  # ระบุ commit เองตรงๆ
  # ถ้า Colab เพิ่ง push แต่เครื่องนี้ยังไม่ได้ pull: รัน `git fetch --all` ก่อน แล้วใช้
  # --colab-ref origin/master (หรือ branch ที่ push ไป) แทน auto-detect

Exit code: 0 = ตรงกันหมด (หรือต่างกันแค่ field ที่คาดไว้แล้ว), 1 = เจอ field ที่ต่างกันแบบผิดปกติ
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

WEBSITE_LATEST_JSON_PATH = "03_website/assets/data/latest.json"

# field prefix ที่รู้อยู่แล้วว่า "ควรต่างกัน" ระหว่าง 2 รัน ไม่ใช่สัญญาณปัญหา (ดู docstring ด้านบน)
EXPECTED_TO_DIFFER_PREFIXES = (
    "run_timestamp",
    "telemetry.readings",
    "crop_classification.age_days",
)


def _run_git(args: list, cwd: Path) -> str:
    result = subprocess.run(
        ["git"] + args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} ล้มเหลว: {result.stderr.strip()}")
    return result.stdout


def find_latest_commit_for_date(repo_root: Path, target_date: date, author_pattern: str, grep_pattern: str) -> str:
    """
    หา commit ล่าสุด (ของวันที่ target_date ตามเวลาเครื่อง commit เอง ไม่ใช่ UTC) ที่แตะ
    WEBSITE_LATEST_JSON_PATH และ commit message ตรงกับ grep_pattern -- คืน commit hash
    """
    since = target_date.isoformat() + " 00:00:00"
    until = target_date.isoformat() + " 23:59:59"
    out = _run_git(
        [
            "log", "--oneline", "--all",
            f"--since={since}", f"--until={until}",
            f"--grep={grep_pattern}",
            "--", WEBSITE_LATEST_JSON_PATH,
        ],
        cwd=repo_root,
    )
    lines = [l for l in out.strip().splitlines() if l.strip()]
    if not lines:
        raise RuntimeError(
            f"ไม่พบ commit ที่แตะ {WEBSITE_LATEST_JSON_PATH} ในวันที่ {target_date.isoformat()} "
            f"ที่ message ตรงกับ '{grep_pattern}' -- อาจยังไม่ได้รันฝั่งนี้ของวันนี้ หรือยังไม่ได้ "
            f"push/fetch ล่าสุด (ลอง git fetch --all ก่อน)"
        )
    return lines[0].split()[0]  # commit ล่าสุดสุด (git log เรียงใหม่->เก่าอยู่แล้ว)


def flatten(d, prefix: str = "") -> dict:
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out.update(flatten(v, f"{prefix}.{k}" if prefix else k))
    elif isinstance(d, list):
        for i, v in enumerate(d):
            out.update(flatten(v, f"{prefix}[{i}]"))
    else:
        out[prefix] = d
    return out


def load_json_at_commit(repo_root: Path, commit: str, path: str) -> dict:
    out = _run_git(["show", f"{commit}:{path}"], cwd=repo_root)
    return json.loads(out)


def compare(win_json: dict, colab_json: dict) -> tuple:
    fw, fc = flatten(win_json), flatten(colab_json)
    all_keys = set(fw) | set(fc)
    diffs, expected_diffs = [], []
    for k in sorted(all_keys):
        vw, vc = fw.get(k, "<missing>"), fc.get(k, "<missing>")
        if vw != vc:
            (expected_diffs if k.startswith(EXPECTED_TO_DIFFER_PREFIXES) else diffs).append((k, vw, vc))
    return diffs, expected_diffs, len(all_keys)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo-root", default=None, help="path ของ maenaruea-water-web repo (default: auto-detect จาก location ของสคริปต์นี้)")
    parser.add_argument("--date", default=None, help="วันที่จะเทียบ (YYYY-MM-DD, default = วันนี้)")
    parser.add_argument("--win-ref", default=None, help="ระบุ Windows commit hash ตรงๆ (ข้าม auto-detect)")
    parser.add_argument("--colab-ref", default=None, help="ระบุ Colab commit hash ตรงๆ (ข้าม auto-detect, ลองใส่ origin/master ถ้ายังไม่ pull ในเครื่อง)")
    args = parser.parse_args()

    repo_root = Path(args.repo_root) if args.repo_root else Path(__file__).resolve().parents[3]
    target_date = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else datetime.now().date()

    print(f"=== เทียบผลลัพธ์ Windows vs Colab ({target_date.isoformat()}) ===")
    print(f"repo: {repo_root}\n")

    win_ref = args.win_ref or find_latest_commit_for_date(
        repo_root, target_date, "mpdox30", "Auto-update: ml_features_live.csv"
    )
    colab_ref = args.colab_ref or find_latest_commit_for_date(
        repo_root, target_date, "Colab", "(Colab)"
    )
    print(f"Windows commit: {win_ref}")
    print(f"Colab   commit: {colab_ref}\n")

    win_json = load_json_at_commit(repo_root, win_ref, WEBSITE_LATEST_JSON_PATH)
    colab_json = load_json_at_commit(repo_root, colab_ref, WEBSITE_LATEST_JSON_PATH)

    diffs, expected_diffs, total = compare(win_json, colab_json)

    print(f"Total leaf fields compared: {total}")
    print(f"Expected-to-differ fields (mock telemetry / timestamps): {len(expected_diffs)}")
    print(f"UNEXPECTED differing fields: {len(diffs)}\n")

    if diffs:
        print("!!! พบความต่างที่ผิดปกติ -- ต้องตรวจสอบ !!!")
        for k, vw, vc in diffs:
            print(f"  MISMATCH {k}: WIN={vw!r}  COLAB={vc!r}")
        sys.exit(1)
    else:
        print("ผลลัพธ์ Windows กับ Colab ตรงกันทุก field ที่มีนัยสำคัญ (ต่างกันแค่ mock telemetry/timestamp ตามที่คาดไว้)")
        sys.exit(0)


if __name__ == "__main__":
    main()

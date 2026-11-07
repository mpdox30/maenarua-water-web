# -*- coding: utf-8 -*-
"""
run_extras_colab.py -- ส่วนที่ "โน๊ตบุ๊คทำ แต่ Colab เดิมไม่ได้ทำ" (เพิ่ม 2026-11-07)

ที่มา: ช่วงที่ใช้ Colab อย่างเดียว 9 วัน เว็บอัปเดตไม่ครบ เพราะ Cell 12 push แค่ ~14 ไฟล์
(latest / flood_latest / reservoir_inflow / depth PNG) ในขณะที่โน๊ตบุ๊คอัปเดตเพิ่มอีกหลายส่วน:
monitoring.json, inflow_6h_display.json, wmb_daily_model.json, forecast_accuracy_log, water_ledger,
Reservoirs/inflow (บัญชีน้ำรายวัน), SAR output, shadow 6 ชม. และ "ข้อมูลสะสม" ฝั่ง WMB_Phayao (IMERG/โทรมาตร)

ไฟล์นี้รันครบทุกส่วนนั้นบน Colab (แต่ละ step แยก subprocess ล้มอันหนึ่งไม่บล็อกอันอื่น)
แล้ว commit+push ทั้ง 2 repo เฉพาะโฟลเดอร์ข้อมูลที่ pipeline สร้าง (allowlist) -- ไม่แตะโค้ด/HTML

ใช้ใน notebook (Cell ใหม่ หลัง Cell 12 / ก่อนเช็คช่องว่าง):
    import importlib, run_extras_colab as rx; importlib.reload(rx)
    rx.run_all(PROJECT_WEB, PROJECT_WMB, GITHUB_PAT)

กันรันชนกับโน๊ตบุ๊ค: ดู guard() -- อ่าน 01_data/run_state/last_run.json (ทั้งสองฝั่งเขียน)
"""
import base64
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

BKK = timezone(timedelta(hours=7))
STATE_REL = "01_data/run_state/last_run.json"

# โฟลเดอร์/ไฟล์ที่ pipeline สร้าง -- push เฉพาะที่เปลี่ยน และอยู่ใต้ prefix เหล่านี้เท่านั้น
WEB_PREFIXES = (
    "03_website/assets/data/",
    "01_data/Reservoirs/inflow/",
    "01_data/Reservoirs/inflow_auto/",
    "01_data/forecasting_results/",
    "01_data/gis/sar_output/",
    "01_data/gis/.sar_last_classified",
    "01_data/archive_live/",
    "01_data/Reservoirs/reference/hii_rainfall_archive/",
    "01_data/run_state/",
    "01_data/experiments/sixhourly_refresh_20260918/shadow_",
    "01_data/scripts and code/pipeline/ml_features_live.csv",
)
WMB_PREFIXES = (
    "09_live/daily_wmb_refresh/01_raw_data/",
    "09_live/daily_wmb_refresh/03_model/simulation/",
    "09_live/daily_wmb_refresh/wmb_daily_model_latest.json",
    "09_live/data/",
    "09_live/output/forecast_",
    "09_live/output/Flood_output_forecast_latest.csv",
    "01_raw_data/rainfall/weathernext_archive/",
    "01_raw_data/rainfall/weathernext_forecast_daily.csv",
    "01_raw_data/kwaan_level/kwaan_level_daily.csv",
    "01_raw_data/Reservoirs/บัญชีน้ำ/",
)
SKIP_SUFFIX = (".pyc", ".bak", ".tmp")


def _now():
    return datetime.now(BKK)


def _log(msg):
    print(f"[{_now():%H:%M:%S}] {msg}", flush=True)


# --------------------------------------------------------------------------- guard / marker
def read_state(web):
    p = Path(web) / STATE_REL
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def guard(web, host="colab", force=False, fresh_hours=5.0):
    """False = ไม่ควรรัน (อีกฝั่งเพิ่งอัปเดตครบแล้ววันนี้) -- ป้องกัน 2 ฝั่งเขียนทับกัน"""
    st = read_state(web)
    other = st.get("host")
    fin = st.get("finished_bkk")
    if force or not other or other == host or not fin:
        return True
    try:
        t = datetime.fromisoformat(fin)
    except Exception:
        return True
    age_h = (_now() - t).total_seconds() / 3600
    if age_h < fresh_hours:
        _log(f"!! {other} เพิ่งอัปเดตเสร็จเมื่อ {age_h:.1f} ชม.ก่อน ({fin}) -- ข้ามรอบนี้ "
             f"(ถ้าต้องการรันซ้ำจริง ใส่ force=True)")
        return False
    return True


def write_state(web, host, steps, ok_all):
    p = Path(web) / STATE_REL
    p.parent.mkdir(parents=True, exist_ok=True)
    prev = read_state(web)
    d = {
        "host": host,
        "finished_bkk": _now().isoformat(timespec="seconds"),
        "complete": bool(ok_all),
        "steps": steps,
    }
    if ok_all:
        d["last_complete_bkk"] = d["finished_bkk"]
        d["last_complete_host"] = host
    else:
        d["last_complete_bkk"] = prev.get("last_complete_bkk")
        d["last_complete_host"] = prev.get("last_complete_host")
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


# --------------------------------------------------------------------------- git helpers
def _auth_args(pat):
    tok = base64.b64encode(f"x-access-token:{pat}".encode()).decode()
    return ["-c", f"http.extraHeader=Authorization: Basic {tok}"]


def _git(repo, *a, pat=None, timeout=300):
    cmd = ["git", "-C", str(repo), "-c", "merge.autoStash=false", "-c", "rebase.autoStash=false", "-c", "pull.autoStash=false"] + (_auth_args(pat) if pat else []) + list(a)
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    r.stdout = r.stdout or ""
    r.stderr = r.stderr or ""
    if pat:
        r.stdout = (r.stdout or "").replace(pat, "***")
        r.stderr = (r.stderr or "").replace(pat, "***")
    return r


def changed_files(repo, prefixes):
    r = _git(repo, "-c", "core.quotepath=false", "status", "--porcelain", "-z", "--untracked-files=all")
    if r.returncode != 0:
        raise RuntimeError("git status ล้มเหลว: " + (r.stderr or "")[-300:])
    out = []
    for ent in (r.stdout or "").split("\0"):
        if len(ent) < 4:
            continue
        path = ent[3:]
        if path.endswith(SKIP_SUFFIX) or ".bak_" in path or "__pycache__" in path:
            continue
        if any(path.startswith(pre) for pre in prefixes):
            out.append(path)
    return out


def pull_latest(repo, pat):
    """ดึงของล่าสุดก่อนรัน (ให้ได้ข้อมูลสะสมที่โน๊ตบุ๊ค push ไว้) -- ไฟล์ที่ยังไม่ commit ถูก stash ก่อน"""
    _git(repo, "stash", "--include-untracked")
    r = _git(repo, "pull", "--no-rebase", "--no-edit", "origin", "master" if "water" in str(repo) else "main", pat=pat)
    ok = r.returncode == 0
    _log(f"pull {Path(repo).name}: {'OK' if ok else 'ล้มเหลว ' + (r.stderr or '')[-200:]}")
    return ok


def push_repo(repo, prefixes, branch, pat, msg, retries=3):
    files = changed_files(repo, prefixes)
    if not files:
        _log(f"{Path(repo).name}: ไม่มีไฟล์ข้อมูลเปลี่ยน -- ไม่ push")
        return True
    _git(repo, "config", "user.name", "Mae Na Rua Pipeline (Colab)")
    _git(repo, "config", "user.email", "mp.dox69@gmail.com")
    for i in range(0, len(files), 200):
        _git(repo, "add", "--", *files[i:i + 200])
    if _git(repo, "diff", "--cached", "--quiet").returncode == 0:
        _log(f"{Path(repo).name}: ไม่มีอะไรให้ commit")
        return True
    c = _git(repo, "commit", "-m", msg)
    if c.returncode != 0:
        _log(f"commit ล้มเหลว {Path(repo).name}: {(c.stderr or c.stdout)[-300:]}")
        return False
    for a in range(1, retries + 1):
        r = _git(repo, "push", "origin", f"HEAD:{branch}", pat=pat)
        if r.returncode == 0:
            _log(f"push {Path(repo).name} สำเร็จ ({len(files)} ไฟล์, ลองครั้งที่ {a})")
            return True
        err = r.stderr or ""
        if "fetch first" not in err and "non-fast-forward" not in err and "rejected" not in err:
            _log(f"push ล้มเหลว {Path(repo).name}: {err[-400:]}")
            return False
        # ไฟล์ที่ pipeline เพิ่งสร้างรอบนี้ให้ชนะ (-X ours) ไฟล์อื่นรวมตามปกติ
        p = _git(repo, "pull", "--no-rebase", "--no-edit", "--no-autostash", "-X", "ours", "origin", branch, pat=pat)
        if p.returncode != 0:
            _log(f"pull ระหว่างลอง push ล้มเหลว: {(p.stderr or p.stdout)[-300:]}")
            return False
    _log(f"push {Path(repo).name} ไม่สำเร็จหลังลอง {retries} ครั้ง -- รันเซลล์นี้ซ้ำได้ (commit ค้างจะถูก push รอบถัดไป)")
    return False


# --------------------------------------------------------------------------- steps
def build_steps(web, wmb):
    pipe = f"{web}/01_data/scripts and code/pipeline"
    exp6 = f"{web}/01_data/experiments/sixhourly_refresh_20260918"
    wref = f"{wmb}/09_live/daily_wmb_refresh"
    ledger_dir = f"{wmb}/01_raw_data/Reservoirs/บัญชีน้ำ"
    has_release = bool(os.environ.get("RESERVOIR_RELEASE_SHEET_CSV_URL"))
    steps = [
        # (ชื่อ, คำสั่ง, cwd, timeout วินาที, ข้ามถ้า)
        ("wmb_daily_refresh", [sys.executable, "run_daily_wmb_refresh.py"], wref, 1800, None),
        ("monitoring_builder", [sys.executable, "monitoring_data_builder.py"], pipe, 600, None),
        ("inflow_6h_display", [sys.executable, "inflow_6h_display_estimate.py"], pipe, 600, None),
        ("forecast_accuracy_logger", [sys.executable, "forecast_accuracy_logger.py"], pipe, 300, None),
        ("reservoir_orchestration", [sys.executable, "reservoir_daily_orchestration.py"], pipe, 900,
         None if has_release else "ไม่มี env RESERVOIR_RELEASE_SHEET_CSV_URL (ตั้งเป็น Colab Secret)"),
        ("ledger_recompute", [sys.executable, "recompute_corrected_ledger.py"], ledger_dir, 600,
         None if has_release else "ข้าม (ต้องรันหลัง reservoir_orchestration)"),
        ("ledger_json", [sys.executable, "build_water_ledger_json.py"], pipe, 300,
         None if has_release else "ข้าม (ต้องรันหลัง reservoir_orchestration)"),
        ("shadow_predict_6h", [sys.executable, "shadow_predict.py"], exp6, 1200, None),
    ]
    return steps


def run_all(web, wmb, pat, force=False, host="colab", do_pull=False, do_push=True):
    web, wmb = str(web), str(wmb)
    if not guard(web, host, force):
        return {"skipped": True}
    if do_pull:
        pull_latest(web, pat)
        pull_latest(wmb, pat)
    env = {**os.environ, "WEB_REPO_DIR": web, "WMB_ROOT": wmb, "PYTHONIOENCODING": "utf-8"}
    # ให้ import ข้ามโมดูลใน pipeline/ ได้เหมือนบนเครื่อง Windows
    env["PYTHONPATH"] = os.pathsep.join(
        [f"{web}/01_data/scripts and code/pipeline", f"{wmb}/colab_migration", env.get("PYTHONPATH", "")])
    results = {}
    for name, cmd, cwd, to, skip in build_steps(web, wmb):
        if skip:
            results[name] = f"skipped: {skip}"
            _log(f"-- {name}: ข้าม ({skip})")
            continue
        if not Path(cwd).exists() or not (Path(cwd) / cmd[-1]).exists():
            results[name] = "missing-script"
            _log(f"!! {name}: ไม่พบสคริปต์ {Path(cwd) / cmd[-1]}")
            continue
        t0 = time.time()
        try:
            r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=to)
            ok = r.returncode == 0
            results[name] = "ok" if ok else f"exit {r.returncode}"
            _log(f"{'OK ' if ok else '!! '} {name} ({time.time() - t0:.0f}s)")
            if not ok:
                print((r.stdout or "")[-600:])
                print("STDERR:", (r.stderr or "")[-900:])
        except subprocess.TimeoutExpired:
            results[name] = "timeout"
            _log(f"!! {name}: timeout {to}s")
        except Exception as e:
            results[name] = f"error {e}"
            _log(f"!! {name}: {e}")

    ok_all = all(v == "ok" or str(v).startswith("skipped") for v in results.values())
    write_state(web, host, results, ok_all)
    if do_push:
        stamp = _now().strftime("%Y-%m-%d %H:%M")
        push_repo(wmb, WMB_PREFIXES, "main", pat, f"Auto-update: WMB live data {stamp} (Colab)")
        push_repo(web, WEB_PREFIXES, "master", pat, f"Auto-update: site data + state {stamp} (Colab)")
    print("\nสรุป:", json.dumps(results, ensure_ascii=False, indent=1))
    if not ok_all:
        print("!! มี step ที่ไม่สำเร็จ -- ดูข้างบน (ส่วนที่ผ่านแล้วถูก push ไปแล้ว รันเซลล์นี้ซ้ำได้อย่างปลอดภัย)")
    return results

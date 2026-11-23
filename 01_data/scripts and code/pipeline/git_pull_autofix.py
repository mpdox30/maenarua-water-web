"""git_pull_autofix.py -- clear the files that make `git pull` refuse to merge, then let the caller retry.

Usage: python git_pull_autofix.py <path-to-saved-pull-output.txt>
  exit 0 = something was moved/stashed (caller should retry pull once)
  exit 1 = nothing recognised (caller should give up this round)

Handles the two git messages that silently blocked pushes (2026-11):
  * "The following untracked working tree files would be overwritten by merge:"
      -> files are MOVED to <repo parent>/_untracked_backup/<timestamp>/ (never deleted)
  * "Your local changes to the following files would be overwritten by merge:"
      -> files are stashed (git stash push -- <files>); nothing is lost
Never force-resets, never deletes.
"""
import re, shutil, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if len(sys.argv) < 2:
    print('usage: git_pull_autofix.py <pull_output.txt>'); sys.exit(1)
txt = Path(sys.argv[1]).read_text(encoding='utf-8', errors='replace').splitlines()


def block(header_re):
    out, on = [], False
    for ln in txt:
        if re.search(header_re, ln, re.I):
            on = True
            continue
        if on:
            if ln.startswith(('\t', '    ')) and ln.strip():
                out.append(ln.strip())
            elif ln.strip().lower().startswith(('please', 'aborting', 'error')):
                break
    return out


fixed = False
untracked = block(r'untracked working tree files would be overwritten')
if untracked:
    dest = ROOT.parent / '_untracked_backup' / time.strftime('%Y%m%d_%H%M%S')
    for rel in untracked:
        src = ROOT / rel
        if not src.exists():
            continue
        tgt = dest / rel
        tgt.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(tgt))
        fixed = True
    print('[autofix] moved %d untracked file(s) -> %s' % (len(untracked), dest))

dirty = block(r'local changes to the following files would be overwritten')
if dirty:
    r = subprocess.run(['git', 'stash', 'push', '-m', 'autofix-pre-merge ' + time.strftime('%Y%m%d_%H%M%S'), '--'] + dirty,
                       cwd=str(ROOT), capture_output=True, text=True)
    print('[autofix] stash %d tracked file(s): rc=%d %s' % (len(dirty), r.returncode, (r.stdout or r.stderr).strip()[:160]))
    fixed = fixed or r.returncode == 0

sys.exit(0 if fixed else 1)

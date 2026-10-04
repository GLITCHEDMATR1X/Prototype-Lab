"""Run every check in .dev/checks and print one summary (Pass 62).

    .dev\\RUN_CHECKS.bat                  (or: python .dev/run_checks.py)
    python .dev/run_checks.py pass61      only the checks whose names contain 'pass61'
    python .dev/run_checks.py --jobs 2    how many run at once (default 3)

Each check starts the game without a window and prints PASS/FAIL lines and a RESULT. Their
full output goes to .dev/check_logs/<name>.log. A summary is written to .dev/check_results.txt.
The whole set takes a few minutes; pass44 is the longest.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECKS = HERE / 'checks'
LOGS = HERE / 'check_logs'
TIMEOUT = 1500


def run_one(path: Path):
    started = time.perf_counter()
    log = LOGS / f'{path.stem}.log'
    try:
        with log.open('w', encoding='utf-8') as fh:
            proc = subprocess.run([sys.executable, str(path)], cwd=str(HERE.parent), stdout=fh,
                                  stderr=subprocess.STDOUT, timeout=TIMEOUT)
        code = proc.returncode
    except subprocess.TimeoutExpired:
        code = 'timeout'
    text = log.read_text(encoding='utf-8', errors='replace')
    fails = [ln[5:] for ln in text.splitlines() if ln.startswith('FAIL ')]
    passed = code == 0 and 'RESULT PASS' in text
    return path.stem, passed, code, fails, time.perf_counter() - started


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('only', nargs='*', help='run only checks whose names contain these')
    ap.add_argument('--jobs', type=int, default=3)
    args = ap.parse_args()
    LOGS.mkdir(exist_ok=True)
    checks = sorted(CHECKS.glob('pass*.py'), key=lambda p: int(''.join(c for c in p.stem if c.isdigit()) or 0))
    if args.only:
        checks = [c for c in checks if any(o in c.stem for o in args.only)]
    print(f'running {len(checks)} checks, {args.jobs} at a time...', flush=True)
    results = []
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        for name, passed, code, fails, secs in pool.map(run_one, checks):
            results.append((name, passed, code, fails, secs))
            print(f"  {'PASS' if passed else 'FAIL'}  {name:8s} {secs:6.0f} s"
                  + ('' if passed else f'   (exit {code}; see .dev/check_logs/{name}.log)'), flush=True)
            for f in fails[:5]:
                print(f'          - {f}', flush=True)
    bad = [r for r in results if not r[1]]
    lines = [f"{'PASS' if p else 'FAIL'} {n} ({s:.0f} s)" for n, p, _c, _f, s in results]
    lines.append(f'{len(results) - len(bad)} of {len(results)} passed')
    (HERE / 'check_results.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(lines[-1])
    return 0 if not bad else 1


if __name__ == '__main__':
    raise SystemExit(main())

"""Use Panda3D's image loader to verify Pygame proof images are valid 1080p RGB(A) assets."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from panda3d.core import PNMImage


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("images", nargs="+")
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    rows = []
    for raw in args.images:
        path = Path(raw)
        image = PNMImage()
        ok = image.read(str(path))
        row = {
            "path": str(path),
            "readable": bool(ok),
            "width": image.get_x_size() if ok else 0,
            "height": image.get_y_size() if ok else 0,
            "channels": image.get_num_channels() if ok else 0,
        }
        row["pass"] = bool(ok and row["width"] == 1920 and row["height"] == 1080 and row["channels"] >= 3)
        rows.append(row)
    report = {"panda3d_version": "1.10.16", "images": rows, "final_result": "PASS" if all(r["pass"] for r in rows) else "FAIL"}
    Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["final_result"] == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())

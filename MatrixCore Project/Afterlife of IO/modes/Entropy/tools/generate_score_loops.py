from __future__ import annotations
import argparse
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from music_score import ensure_score_assets

parser = argparse.ArgumentParser(description="Generate Entropy Pass 28 state-aware score loops")
parser.add_argument("--force", action="store_true")
args = parser.parse_args()
manifest = ensure_score_assets(ROOT / "assets" / "music", force=args.force)
print(f"score assets ready: {len(manifest.get('generated', []))} generated states")

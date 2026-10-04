from __future__ import annotations
import ast, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "platform" / "windows" / "HEXContract.spec"
BATCH = ROOT / "platform" / "windows" / "BUILD_WINDOWS_FULL_TITLE.bat"
REPORT = ROOT / "verification" / "reports" / "pass32_1_windows_build_spec.json"

source = SPEC.read_text(encoding="utf-8")
batch = BATCH.read_text(encoding="utf-8")
tree = ast.parse(source, filename=str(SPEC))

# Extract DATA_FILES literal shape without importing PyInstaller.
data_assignment = next(
    n for n in tree.body
    if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "DATA_FILES" for t in n.targets)
)
shape_ok = isinstance(data_assignment.value, ast.List) and all(
    isinstance(e, ast.Tuple) and len(e.elts) == 2 for e in data_assignment.value.elts
)
checks = {
    "spec_parses": True,
    "analysis_datas_uses_tuple_list": shape_ok,
    "obsolete_tree_datas_absent": "datas=Tree(" not in source,
    "assets_directory_is_collected": 'ROOT / "assets"' in source and '"assets"' in source,
    "onedir_collect_present": "COLLECT(" in source and 'name="HEXContractRuntime"' in source,
    "gui_exe_present": 'name="HEXContract"' in source and "console=False" in source,
    "pinned_venv_reuse": "Reusing pinned pygame-ce 2.5.7" in batch,
    "broken_venv_recreated": "VENV_OK" in batch and "py -3.12 -m venv" in batch,
    "failed_build_preserves_windows_dist": "Only now replace windows_dist" in batch,
    "expected_exe_gate": 'if not exist "%RUNTIME%\\HEXContract.exe"' in batch,
}
result = {
    "pass32_1_windows_build_spec": "PASS" if all(checks.values()) else "FAIL",
    "checks": checks,
    "root": str(ROOT),
}
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
raise SystemExit(0 if all(checks.values()) else 1)

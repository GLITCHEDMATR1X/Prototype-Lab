#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
s = (ROOT / "main.py").read_text()
p = (ROOT / "phase_progression.py").read_text()

checks = {
    "campaign completion authority": "def complete_ocean_campaign(self) -> bool:" in p,
    "ocean completion commits campaign": "phase_progression.complete_ocean_campaign()" in s,
    "victory freezes simulation dt": "if quit_confirm or phase_progression.campaign_complete:" in s,
    "campaign owns keyboard": "Campaign-complete state owns keyboard input until replay/quit." in s,
    "enter replay": "_restart_campaign_process()" in s and "pygame.K_KP_ENTER" in s,
    "fresh process replay": "os.execv(sys.executable, [sys.executable, *sys.argv])" in s,
    "victory objective": "campaign_complete=phase_progression.campaign_complete" in s and "CAMPAIGN COMPLETE" in (ROOT / "hud_layout.py").read_text(),
    "victory overlay": "THREE-FRONT CAMPAIGN COMPLETE" in s and "GROUND // AIR // OCEAN SECURED" in s,
    "completion clears fire": "mouse1 = False" in s and "mouse3 = False" in s,
    "completion closes guide": "help_visible = False" in s,
}
failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(("PASS" if ok else "FAIL"), name)
if failed:
    raise SystemExit(1)
print("pass12_campaign_complete: PASS")

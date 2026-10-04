from pathlib import Path
import importlib.util, json, sys
root=Path(__file__).resolve().parents[1]
sys.argv=[sys.argv[0],'--headless','--no-audio']
spec=importlib.util.spec_from_file_location('dreamcatcher_main',root/'main.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
g=mod.DreamCatcherAlternateGame()
checks=[]
def ck(name, cond, detail=''):
    checks.append(bool(cond)); print(('PASS' if cond else 'FAIL'), name, detail)
try:
    lore=json.loads((root/'data'/'dreamcatcher_lore.json').read_text())
    fr=lore['fragments'][0]
    ck('fragment contract', fr['id']=='dream_link_04', fr['id'])
    ck('archive channel', fr['channel']=='archive', fr['channel'])
    ck('Andrew not named early', 'ANDREW' not in ' '.join(fr['lines']).upper(), fr['lines'])
    ck('intrusion evidence', fr['lines']==['DREAM LINK TEST 04.','SECOND USER DETECTED.','OWNER UNAWARE.'], fr['lines'])
    g.tv_task.update({'state':'unissued','note_collected':False})
    ck('locked before task 01', g._active_archive_lore_fragment() is None)
    g.tv_task.update({'state':'completed','note_collected':True})
    active=g._active_archive_lore_fragment()
    ck('unlocks after task 01', active is not None and active['id']=='dream_link_04', active and active['id'])
    g.tv_channel=4; g.tv_power=True; g.tv_focused=True
    img=mod.PNMImage(160,120,1); img.fill(0.5)
    ck('archive overlay renders', g._render_archive_lore_overlay(img) is True)
    g.tv_channel=3
    img2=mod.PNMImage(160,120,1); img2.fill(0.5)
    ck('other channels untouched', g._render_archive_lore_overlay(img2) is False)
finally:
    try: g.destroy()
    except Exception: pass
print(f'PASS100_TOTAL={sum(checks)}/{len(checks)}')
sys.exit(0 if all(checks) else 1)

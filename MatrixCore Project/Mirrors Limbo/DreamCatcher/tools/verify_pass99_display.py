from __future__ import annotations
import importlib.util, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.argv=['main.py','--headless','--no-audio']
spec=importlib.util.spec_from_file_location('dreamcatcher_main', ROOT/'main.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
checks=[]
def ck(name, cond, detail=''):
    checks.append(bool(cond)); print(('PASS' if cond else 'FAIL'), name, detail)
ck('project metadata renamed', __import__('json').loads((ROOT/'data/house_layout.json').read_text()).get('project')=='DreamCatcher Alternate')
ck('default mode borderless', mod.DISPLAY_DEFAULTS['mode']=='borderless')
ck('default resolution 1920x1080', tuple(mod.DISPLAY_DEFAULTS['resolution'])==(1920,1080))
ck('resolution set complete', mod.DISPLAY_RESOLUTIONS==[(1280,720),(1600,900),(1920,1080),(2560,1440),(3840,2160)])
ck('new user data namespace', 'dreamcatcher' in str(mod.USER_DATA_DIR).lower())
g=mod.DreamCatcherAlternateGame(); g.taskMgr.remove('game-update')
old=dict(g.display_settings)
ck('pause display panel exists', hasattr(g,'display_panel'))
ck('fov initialized from settings', round(float(g.camLens.getFov()[0])) >= 60)
g._display_set_mode('windowed'); ck('mode switch state', g.display_settings['mode']=='windowed')
g.display_settings['resolution']=[1920,1080]; g._display_cycle_resolution(1); ck('resolution cycle', g.display_settings['resolution']==[2560,1440])
g.display_settings['fov']=74; g._display_adjust_fov(5); ck('fov live change', g.display_settings['fov']==79)
prev=g.display_settings['fps_meter']; g._display_toggle_fps(); ck('fps toggle', g.display_settings['fps_meter'] is (not prev))
for k,v in old.items(): g.display_settings[k]=v
g._save_display_settings(); g.userExit()
print(f'PASS99_TOTAL={sum(checks)}/{len(checks)}')
raise SystemExit(0 if all(checks) else 1)

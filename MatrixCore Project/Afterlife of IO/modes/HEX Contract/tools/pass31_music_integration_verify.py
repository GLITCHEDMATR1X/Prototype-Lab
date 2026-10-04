from __future__ import annotations
import importlib.util
import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MUSIC = ROOT / 'assets' / 'music'

class FakeError(Exception):
    pass

class FakeChannel:
    def fadeout(self, ms):
        return None

class FakeSound:
    def __init__(self, path):
        self.path = path
        self.volume = 1.0
    def set_volume(self, value):
        self.volume = float(value)
    def play(self, loops=0, fade_ms=0):
        return FakeChannel()

class FakeMusic:
    def __init__(self):
        self.calls=[]
        self.busy=False
        self.loaded=None
        self.volume=1.0
    def stop(self):
        self.calls.append(('stop',))
        self.busy=False
    def load(self, path):
        self.loaded=Path(path)
        self.calls.append(('load', self.loaded.name, self.loaded.parent.name))
    def set_volume(self, value):
        self.volume=float(value)
        self.calls.append(('volume', round(self.volume, 6)))
    def play(self, loops=0, fade_ms=0):
        self.busy=True
        self.calls.append(('play', loops, fade_ms))
    def get_busy(self):
        return self.busy

music = FakeMusic()
fake_pygame = types.ModuleType('pygame')
fake_pygame.error = FakeError
fake_pygame.time = types.SimpleNamespace(get_ticks=lambda: 100000)
fake_pygame.mixer = types.SimpleNamespace(
    get_init=lambda: (48000, -16, 2),
    get_num_channels=lambda: 24,
    set_num_channels=lambda n: None,
    Sound=FakeSound,
    music=music,
    Channel=FakeChannel,
)
sys.modules['pygame'] = fake_pygame
spec = importlib.util.spec_from_file_location('pass31_audio', ROOT/'game'/'audio.py')
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)
AudioManager = mod.AudioManager
settings={'master_volume':0.75,'sfx_volume':0.80,'ambience_volume':0.45,'music_volume':1.0}
a=AudioManager(ROOT, True, settings)

manifest=json.loads((MUSIC/'music_manifest.json').read_text(encoding='utf-8'))
norm=json.loads((MUSIC/'normalization_report.json').read_text(encoding='utf-8'))
expected={
    'main': MUSIC/'main'/'MCF28.ogg',
    'purge': MUSIC/'battle'/'MCF12.ogg',
    'recovery': MUSIC/'battle'/'MCF18.ogg',
    'rescue': MUSIC/'battle'/'MCF22.ogg',
    'sovereign': MUSIC/'battle'/'MCF26.ogg',
}
checks={}
checks['five_tracks_present']=all(p.is_file() and p.stat().st_size>100000 for p in expected.values()) and len(list(MUSIC.rglob('*.ogg')))==5
checks['manifest_routes_exact']=a.music_routes==expected
checks['all_normalized_about_minus20']=all(-20.2 <= float(v['output_integrated_lufs']) <= -19.8 for v in norm.values())
checks['music_gain_capped_below_sfx']=a._effective_music_gain() <= settings['master_volume']*settings['sfx_volume']*AudioManager.MUSIC_TO_SFX_RATIO_CAP + 1e-9

def route(state, quest=None, sovereign=False, expected_name=''):
    before=len(music.calls)
    a.set_context(state, quest, sovereign=sovereign)
    new=music.calls[before:]
    loaded=[c for c in new if c[0]=='load']
    plays=[c for c in new if c[0]=='play']
    return bool(loaded and loaded[-1][1]==expected_name and plays and plays[-1][1]==-1)

checks['main_loops']=route('TITLE', expected_name='MCF28.ogg')
checks['purge_loops']=route('MISSION','purge',expected_name='MCF12.ogg')
checks['sovereign_loops']=route('MISSION','purge',sovereign=True,expected_name='MCF26.ogg')
checks['return_main_loops']=route('CONTRACT_BOARD',expected_name='MCF28.ogg')
checks['recovery_loops']=route('MISSION','recovery',expected_name='MCF18.ogg')
checks['rescue_loops']=route('MISSION','rescue',expected_name='MCF22.ogg')
# Every actual route switch begins by stopping the prior stream before loading.
loads=[i for i,c in enumerate(music.calls) if c[0]=='load']
checks['stop_before_every_load']=all(any(music.calls[j][0]=='stop' for j in range(max(0,i-2),i)) for i in loads)
checks['all_play_calls_infinite']=all(c[1]==-1 for c in music.calls if c[0]=='play')

result={'pass':all(checks.values()),'checks':checks,'routes':{k:str(v.relative_to(ROOT)) for k,v in expected.items()},'fake_music_calls':[(c[0],)+tuple(str(x) for x in c[1:]) for c in music.calls], 'effective_music_gain_at_max_slider':a._effective_music_gain(),'sfx_gain':settings['master_volume']*settings['sfx_volume']}
out=ROOT/'verification'/'reports'/'pass31_music_integration.json'
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))
raise SystemExit(0 if result['pass'] else 1)

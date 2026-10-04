"""Headless verifier for Entropy Pass 28 — State-Aware Music."""
from __future__ import annotations

import ast
import hashlib
import json
import math
import struct
import sys
import wave
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from music_score import (
    LOOP_SECONDS,
    SAMPLE_RATE,
    SCORE_GENERATOR_VERSION,
    STATE_BASE_VOLUME,
    STATE_COLLAPSE,
    STATE_EXPEDITION,
    STATE_GLEEBS,
    STATE_HOME,
    STATE_SHIP_RECOVERY,
    STATE_SILENCE,
    STATE_TRACKS,
    ensure_score_assets,
    score_state_for,
)

checks=[]
def req(condition,label,detail=None):
    ok=bool(condition)
    checks.append({'ok':ok,'label':label,'detail':detail})
    if not ok:
        raise AssertionError(label if detail is None else f'{label}: {detail}')

music_root=ROOT/'assets'/'music'
manifest=ensure_score_assets(music_root,force=False)
req(manifest.get('generator_version')==SCORE_GENERATOR_VERSION,'score manifest generator version')
req((music_root/'MCF24.mp3').is_file(),'original MCF24 expedition theme present')
sha=hashlib.sha256((music_root/'MCF24.mp3').read_bytes()).hexdigest()
req(sha=='6fd45c5d6b3d894b37f81df0253ab9e044f7dbc8a07ef75bb3b4fc3c815aa52d','MCF24 remains byte-identical to Pass 27',sha)

asset_stats=[]
for state in (STATE_HOME,STATE_SHIP_RECOVERY,STATE_COLLAPSE,STATE_GLEEBS):
    path=music_root/STATE_TRACKS[state]
    req(path.is_file(),f'{state} generated score exists',path.name)
    with wave.open(str(path),'rb') as wf:
        channels=wf.getnchannels(); rate=wf.getframerate(); width=wf.getsampwidth(); frames=wf.getnframes()
        raw=wf.readframes(frames)
    duration=frames/rate
    req(channels==2,f'{state} score is stereo',channels)
    req(rate==SAMPLE_RATE,f'{state} score is 48 kHz',rate)
    req(width==2,f'{state} score is 16-bit PCM',width)
    req(abs(duration-LOOP_SECONDS)<0.001,f'{state} score has expected loop duration',duration)
    samples=struct.unpack('<'+'h'*(len(raw)//2),raw)
    peak=max(abs(v) for v in samples)/32767.0 if samples else 0.0
    req(peak<=0.93,f'{state} score leaves peak headroom',round(peak,4))
    # Compare a short loop-edge window RMS delta. The generator uses periodic
    # oscillators, so the join should remain small rather than producing a click.
    frame_count=min(512,frames//4)
    start=samples[:frame_count*2]
    end=samples[-frame_count*2:]
    delta=math.sqrt(sum((a-b)**2 for a,b in zip(start,end))/max(1,len(start)))/32767.0
    req(delta<0.22,f'{state} score loop edge remains bounded',round(delta,5))
    asset_stats.append({'state':state,'file':path.name,'duration':duration,'peak':round(peak,6),'edge_rms_delta':round(delta,6)})

# Route matrix: campaign state wins where appropriate; critical collapse overrides
# HOME/expedition but never the frozen ship-recovery sequence.
def m(phase,collapse='STABLE',complete=False):
    return SimpleNamespace(campaign_phase=phase,collapse_state=collapse,campaign_complete=complete)

routes=[
    (m('home','STABLE'),False,False,STATE_HOME),
    (m('home','UNSTABLE'),False,False,STATE_HOME),
    (m('home','CRITICAL'),False,False,STATE_COLLAPSE),
    (m('ship_recovery','CRITICAL'),False,False,STATE_SHIP_RECOVERY),
    (m('expedition','STABLE'),False,False,STATE_EXPEDITION),
    (m('expedition','UNSTABLE'),False,False,STATE_EXPEDITION),
    (m('expedition','CRITICAL'),False,False,STATE_COLLAPSE),
    (m('expedition','SUPERNOVA'),False,False,STATE_COLLAPSE),
    (m('expedition','BLACK HOLE'),False,False,STATE_COLLAPSE),
    (m('delivery','STABLE'),False,False,STATE_GLEEBS),
    (m('complete','STABLE',True),False,True,STATE_GLEEBS),
    (m('expedition','CRITICAL'),True,False,STATE_SILENCE),
]
for idx,(mission,failure,complete,expected) in enumerate(routes):
    actual=score_state_for(mission,failure_active=failure,campaign_complete_active=complete)
    req(actual==expected,f'route {idx+1} resolves {expected}',actual)

req(max(STATE_BASE_VOLUME.values())<=0.62,'authored score trim never exceeds 0.62',STATE_BASE_VOLUME)
req(min(v for k,v in STATE_BASE_VOLUME.items() if k!=STATE_SILENCE)>=0.50,'active score trims remain audible',STATE_BASE_VOLUME)

core=(ROOT/'space_core.py').read_text(encoding='utf-8')
ast.parse(core,filename='space_core.py')
req('pygame.mixer.music.play(loops=-1)' in core,'every selected stream uses infinite looping')
req('pygame.mixer.music.stop()' in core,'state switch explicitly stops previous stream')
req('music.sync(score_state_for(' in core,'main loop synchronizes authoritative score state')
req('self.index' not in core[core.index('class MusicPlayer'):core.index('# Cockpit art / HUD integration')],'sequential playlist index removed')
req('self.master_volume * self.music_volume' in core,'music category remains independent from SFX/ambience')

sync_block=core[core.index('    def sync(self, state: str'):core.index('    def start(self, state: str')]
req(sync_block.index('pygame.mixer.music.stop()') < sync_block.index('pygame.mixer.music.load(path)'),'stop occurs before load')
req(sync_block.index('pygame.mixer.music.play(loops=-1)') < sync_block.index('pygame.mixer.music.set_volume(self._scaled_volume())'),'volume reapplied after load/play')

out={
    'pass':28,
    'status':'PASS',
    'checks_passed':sum(1 for c in checks if c['ok']),
    'checks_total':len(checks),
    'route_cases':len(routes),
    'mcf24_sha256':sha,
    'generated_assets':asset_stats,
    'state_base_volume':STATE_BASE_VOLUME,
    'checks':checks,
}
(ROOT/'Entropy_Pass28_music_validation.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:out[k] for k in ('status','checks_passed','checks_total','route_cases')},indent=2))

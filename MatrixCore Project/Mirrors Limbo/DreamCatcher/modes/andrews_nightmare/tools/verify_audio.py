from __future__ import annotations
from pathlib import Path
import json, wave
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
MUSIC=ROOT/'assets'/'audio'/'music'
SFX=ROOT/'assets'/'audio'/'sfx'
expected_music={
'01_intercept_hum.wav','02_empty_carrier.wav','03_sleep_channel.wav',
'04_green_static.wav','05_false_room.wav','06_dreamcatcher_core.wav'}
expected_sfx={
'sleeper_disturb.wav','stabilizer.wav','instance_collapse.wav','null_layer.wav',
'null_exit.wav','gleebs_trace.wav','memory_seam.wav','false_sleeper_resolve.wav',
'room_recovered.wav','relay_online.wav','sleeper_resonance.wav'}
checks=[]
def ck(name, ok, detail): checks.append((name,bool(ok),detail))
ck('music_names', {p.name for p in MUSIC.glob('*.wav')}==expected_music, sorted(p.name for p in MUSIC.glob('*.wav')))
ck('sfx_names', {p.name for p in SFX.glob('*.wav')}==expected_sfx, sorted(p.name for p in SFX.glob('*.wav')))
summary=[]
for kind,folder in [('music',MUSIC),('sfx',SFX)]:
    for p in sorted(folder.glob('*.wav')):
        with wave.open(str(p),'rb') as w:
            ch=w.getnchannels(); sw=w.getsampwidth(); sr=w.getframerate(); n=w.getnframes(); raw=w.readframes(n)
        a=np.frombuffer(raw,dtype='<i2').reshape(-1,ch).astype(np.float32)/32768.0
        peak=float(np.max(np.abs(a))); rms=float(np.sqrt(np.mean(a*a))); dc=float(np.max(np.abs(np.mean(a,axis=0))))
        dur=n/sr
        ck(f'{kind}:{p.name}:format', ch==2 and sw==2 and sr==32000, (ch,sw,sr))
        ck(f'{kind}:{p.name}:peak', 0.08 < peak < 0.90, round(peak,5))
        ck(f'{kind}:{p.name}:dc', dc < 0.01, round(dc,6))
        if kind=='music':
            seam=float(np.max(np.abs(a[0]-a[-1])))
            ck(f'{kind}:{p.name}:duration', 30.0 <= dur <= 55.0, dur)
            ck(f'{kind}:{p.name}:seam', seam < 0.035, round(seam,6))
        else:
            ck(f'{kind}:{p.name}:duration', 0.5 <= dur <= 3.5, dur)
        summary.append({'file':str(p.relative_to(ROOT)),'duration_s':round(dur,3),'peak':round(peak,5),'rms':round(rms,5),'dc':round(dc,6)})
print(json.dumps({'pass':all(x[1] for x in checks),'checks':len(checks),'failures':[x[0] for x in checks if not x[1]],'assets':summary},indent=2))
for n,ok,d in checks: print(('PASS' if ok else 'FAIL'),n,d)
raise SystemExit(0 if all(x[1] for x in checks) else 1)

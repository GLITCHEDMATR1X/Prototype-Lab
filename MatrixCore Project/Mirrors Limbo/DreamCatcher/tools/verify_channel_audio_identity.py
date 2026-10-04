from pathlib import Path
import json, sys, wave, hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
cfg=json.loads((ROOT/'data/tv_channel_audio.json').read_text())
errors=[]; rows=[]; hashes=set()
channels=cfg.get('channels',[])
if len(channels)!=25: errors.append(f'expected 25 channels, found {len(channels)}')
for c in channels:
    p=ROOT/c['asset']
    if not p.is_file(): errors.append(f'missing {c["id"]}: {c["asset"]}'); continue
    h=hashlib.sha256(p.read_bytes()).hexdigest()
    if h in hashes: errors.append(f'duplicate byte-identical loop: {c["id"]}')
    hashes.add(h)
    try:
        with wave.open(str(p),'rb') as w:
            sr=w.getframerate(); ch=w.getnchannels(); sw=w.getsampwidth(); frames=w.getnframes(); raw=w.readframes(frames)
        if ch!=1 or sw!=2: errors.append(f'{c["id"]}: expected mono 16-bit WAV')
        if sr!=22050: errors.append(f'{c["id"]}: expected 22050 Hz, got {sr}')
        dur=frames/sr
        if dur < 7.9: errors.append(f'{c["id"]}: loop too short {dur:.2f}s')
        x=np.frombuffer(raw,dtype='<i2').astype(np.float64)/32768.0
        peak=float(np.max(np.abs(x))); rms=float(np.sqrt(np.mean(x*x)))
        if rms < 0.01: errors.append(f'{c["id"]}: effectively silent rms={rms:.4f}')
        if peak > .96: errors.append(f'{c["id"]}: clipping risk peak={peak:.4f}')
        # first/last discontinuity must be small enough to avoid an obvious click at setLoop boundary
        boundary=abs(float(x[-1]-x[0]))
        if boundary > .01: errors.append(f'{c["id"]}: loop boundary discontinuity {boundary:.5f}')
        rows.append((c['index'],c['id'],dur,rms,peak,boundary,h[:12]))
    except Exception as e:
        errors.append(f'{c["id"]}: invalid WAV: {e}')
if cfg.get('schema_version',0)<2: errors.append('tv_channel_audio schema not upgraded to identity authority')
if not all(c.get('placeholder_kind')=='procedural_channel_identity' for c in channels): errors.append('not all channel audio entries declare procedural identity placeholders')
print('index id duration rms peak boundary sha256')
for row in rows: print('%02d %-11s %5.2f %0.4f %0.4f %0.6f %s'%row)
print(f'UNIQUE_LOOPS={len(hashes)}/{len(channels)}')
if errors:
    print('FAIL')
    for e in errors: print('-',e)
    sys.exit(1)
print('PASS')

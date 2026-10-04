from pathlib import Path
import json, re, sys, wave
ROOT=Path(__file__).resolve().parents[1]
errors=[]
tv=json.loads((ROOT/'data/analog_tv_system.json').read_text())
vis=json.loads((ROOT/'data/tv_channel_visuals.json').read_text())
aud=json.loads((ROOT/'data/tv_channel_audio.json').read_text())
voice=json.loads((ROOT/'data/alternate_voice_lines.json').read_text())
main=(ROOT/'main.py').read_text()
if len(tv['channels'])!=25: errors.append(f"expected 25 TV channels, found {len(tv['channels'])}")
if len(vis['channels'])!=25: errors.append(f"expected 25 visual profiles, found {len(vis['channels'])}")
if len(aud['channels'])!=25: errors.append(f"expected 25 audio profiles, found {len(aud['channels'])}")
ids=[c['id'] for c in tv['channels']]
if ids != [c['id'] for c in vis['channels']] or ids != [c['id'] for c in aud['channels']]: errors.append('channel id/order mismatch')
for c in vis['channels']:
    fam=c['visual_family']
    if f'family == "{fam}"' not in main: errors.append(f'missing renderer: {fam}')
    p=ROOT/c['audio_asset']
    if not p.exists(): errors.append(f'missing audio: {p.relative_to(ROOT)}')
    else:
        try:
            with wave.open(str(p),'rb') as w:
                if w.getnframes()<=0: errors.append(f'empty WAV: {p.name}')
        except Exception as e: errors.append(f'bad WAV {p.name}: {e}')
if len(voice.get('lines',[])) < 10: errors.append('voice placeholder catalog unexpectedly small')
for line in voice.get('lines',[]):
    p=ROOT/line['audio']
    if not p.exists(): errors.append(f'missing voice placeholder: {line["id"]}')
if 'assets/audio/tv_warning2.wav' in main: errors.append('stale missing tv_warning2.wav reference still present')
if 'glitchtv_archive_inventory.json' in main: errors.append('stale inventory runtime reference in main.py')
print(f'TV_CHANNELS={len(tv["channels"])} VISUALS={len(vis["channels"])} AUDIO_LOOPS={len(aud["channels"])} VOICE_LINES={len(voice.get("lines",[]))}')
if errors:
    print('FAIL')
    for e in errors: print('-',e)
    sys.exit(1)
print('PASS')

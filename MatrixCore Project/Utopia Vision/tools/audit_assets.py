from __future__ import annotations

from array import array
from pathlib import Path
import json
import math
import struct
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]
TEXTURES = [
    'north_civic_lattice.png','east_innovation_pulse.png','south_garden_flow.png','west_foundry_signal.png','core_unity_signal.png',
    'north_pedestrian_pavers.png','east_pedestrian_pulse.png','south_pedestrian_flow.png','west_pedestrian_foundry.png','core_pedestrian_forum.png',
]


def png_size(path: Path):
    data = path.read_bytes()[:24]
    if len(data) < 24 or data[:8] != b'\x89PNG\r\n\x1a\n' or data[12:16] != b'IHDR':
        raise ValueError(f'not_png:{path}')
    return struct.unpack('>II', data[16:24])


texture_sizes = {}
for name in TEXTURES:
    path = ROOT / 'textures' / name
    if not path.exists():
        raise SystemExit(f'ASSET_AUDIT_FAIL missing_texture={name}')
    size = png_size(path)
    texture_sizes[name] = size
    if size[0] < 512 or size[1] < 512:
        raise SystemExit(f'ASSET_AUDIT_FAIL undersized_texture={name} size={size}')

cfg_path = ROOT / 'audio' / 'ambience' / 'ambience_zones.json'
try:
    cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
except Exception as exc:
    raise SystemExit(f'ASSET_AUDIT_FAIL ambience_json={exc}')
if not isinstance(cfg, dict) or not isinstance(cfg.get('zones'), list):
    raise SystemExit('ASSET_AUDIT_FAIL ambience_schema')

for zone in cfg['zones']:
    if not isinstance(zone, dict):
        raise SystemExit('ASSET_AUDIT_FAIL ambience_zone_not_object')
    rel = Path(str(zone.get('asset', '')))
    if not str(rel) or rel.is_absolute() or '..' in rel.parts:
        raise SystemExit(f'ASSET_AUDIT_FAIL unsafe_asset_path={rel}')
    asset = (ROOT / rel).resolve()
    try:
        asset.relative_to(ROOT.resolve())
    except ValueError:
        raise SystemExit(f'ASSET_AUDIT_FAIL escaped_asset_path={rel}')
    if not asset.exists():
        raise SystemExit(f'ASSET_AUDIT_FAIL missing_ambience_asset={rel}')

ocean = ROOT / 'audio' / 'ambience' / 'ocean_loop.wav'
with wave.open(str(ocean), 'rb') as wav:
    channels = wav.getnchannels()
    width = wav.getsampwidth()
    rate = wav.getframerate()
    frames_n = wav.getnframes()
    raw = wav.readframes(frames_n)
if channels not in (1, 2) or width != 2 or rate < 16000 or frames_n <= 0:
    raise SystemExit(f'ASSET_AUDIT_FAIL ocean_format channels={channels} width={width} rate={rate} frames={frames_n}')
samples = array('h')
samples.frombytes(raw)
if sys.byteorder != 'little':
    samples.byteswap()
peak = max(abs(v) for v in samples) / 32768.0
if peak >= 0.98:
    raise SystemExit(f'ASSET_AUDIT_FAIL ocean_peak={peak:.4f}')
duration = frames_n / float(rate)
if duration < 8.0:
    raise SystemExit(f'ASSET_AUDIT_FAIL ocean_too_short={duration:.2f}')
# Loop-edge discontinuity: compare first and last frame, normalized to full scale.
first = samples[:channels]
last = samples[-channels:]
seam = max(abs(int(a) - int(b)) for a, b in zip(first, last)) / 32768.0
if seam > 0.05:
    raise SystemExit(f'ASSET_AUDIT_FAIL ocean_loop_seam={seam:.4f}')
peak_db = 20.0 * math.log10(max(peak, 1e-12))

music_cfg_path = ROOT / 'audio' / 'music' / 'district_music.json'
try:
    music_cfg = json.loads(music_cfg_path.read_text(encoding='utf-8'))
except Exception as exc:
    raise SystemExit(f'ASSET_AUDIT_FAIL district_music_json={exc}')
expected_music = {
    'core':'core_unity_forum.wav',
    'north':'north_corporate_terrace.wav',
    'east':'east_innovation_pulse.wav',
    'south':'south_mirage_promenade.wav',
    'west':'west_foundry_works.wav',
}
if not isinstance(music_cfg,dict) or not isinstance(music_cfg.get('tracks'),dict):
    raise SystemExit('ASSET_AUDIT_FAIL district_music_schema')
music_hashes=set()
for key, filename in expected_music.items():
    raw_track=music_cfg['tracks'].get(key)
    if not isinstance(raw_track,dict):
        raise SystemExit(f'ASSET_AUDIT_FAIL missing_music_track={key}')
    rel=Path(str(raw_track.get('asset','')))
    if rel.is_absolute() or '..' in rel.parts:
        raise SystemExit(f'ASSET_AUDIT_FAIL unsafe_music_path={rel}')
    asset=(ROOT/rel).resolve()
    try:
        asset.relative_to(ROOT.resolve())
    except ValueError:
        raise SystemExit(f'ASSET_AUDIT_FAIL escaped_music_path={rel}')
    if asset.name != filename or not asset.exists():
        raise SystemExit(f'ASSET_AUDIT_FAIL missing_music_asset={key}:{rel}')
    with wave.open(str(asset),'rb') as wav:
        mch=wav.getnchannels(); mwidth=wav.getsampwidth(); mrate=wav.getframerate(); mn=wav.getnframes(); mraw=wav.readframes(mn)
    if mch not in (1,2) or mwidth != 2 or mrate < 16000 or mn <= 0:
        raise SystemExit(f'ASSET_AUDIT_FAIL music_format={key} channels={mch} width={mwidth} rate={mrate} frames={mn}')
    ms=array('h'); ms.frombytes(mraw)
    if sys.byteorder != 'little': ms.byteswap()
    mpeak=max(abs(v) for v in ms)/32768.0
    mseam=max(abs(int(a)-int(b)) for a,b in zip(ms[:mch],ms[-mch:]))/32768.0
    mdur=mn/float(mrate)
    mrms=(sum(float(v)*float(v) for v in ms)/max(1,len(ms)))**0.5/32768.0
    if mpeak >= 0.95 or mrms < 0.035 or mdur < 8.0 or mseam > 0.01:
        raise SystemExit(f'ASSET_AUDIT_FAIL music_contract={key} peak={mpeak:.4f} rms={mrms:.4f} duration={mdur:.2f} seam={mseam:.5f}')
    import hashlib
    music_hashes.add(hashlib.sha256(mraw).hexdigest())
if len(music_hashes) != 5:
    raise SystemExit('ASSET_AUDIT_FAIL district_music_not_distinct')


gleebs_cfg_path = ROOT / 'audio' / 'characters' / 'gleebs' / 'gleebs_audio.json'
try:
    gleebs_cfg = json.loads(gleebs_cfg_path.read_text(encoding='utf-8'))
except Exception as exc:
    raise SystemExit(f'ASSET_AUDIT_FAIL gleebs_audio_json={exc}')
for key, min_duration, seam_limit in (('purr', 4.0, 0.01), ('spark', 0.08, 1.0)):
    raw_cfg = gleebs_cfg.get(key, {})
    rel = Path(str(raw_cfg.get('asset','')))
    if rel.is_absolute() or '..' in rel.parts:
        raise SystemExit(f'ASSET_AUDIT_FAIL unsafe_gleebs_audio_path={key}:{rel}')
    asset = (ROOT / rel).resolve()
    if not asset.exists():
        raise SystemExit(f'ASSET_AUDIT_FAIL missing_gleebs_audio={key}:{rel}')
    with wave.open(str(asset), 'rb') as wav:
        gch=wav.getnchannels(); gwidth=wav.getsampwidth(); grate=wav.getframerate(); gn=wav.getnframes(); graw=wav.readframes(gn)
    if gch != 1 or gwidth != 2 or grate < 16000 or gn <= 0:
        raise SystemExit(f'ASSET_AUDIT_FAIL gleebs_audio_format={key} channels={gch} width={gwidth} rate={grate} frames={gn}')
    gs=array('h'); gs.frombytes(graw)
    if sys.byteorder != 'little': gs.byteswap()
    gpeak=max(abs(v) for v in gs)/32768.0
    gdur=gn/float(grate)
    gseam=abs(int(gs[0])-int(gs[-1]))/32768.0
    grms=(sum(float(v)*float(v) for v in gs)/max(1,len(gs)))**0.5/32768.0
    if gpeak >= 0.95 or (key == 'purr' and grms < 0.035) or gdur < min_duration or (key == 'purr' and gseam > seam_limit):
        raise SystemExit(f'ASSET_AUDIT_FAIL gleebs_audio_contract={key} peak={gpeak:.4f} rms={grms:.4f} duration={gdur:.2f} seam={gseam:.5f}')
mist_texture = ROOT / 'assets' / 'textures' / 'physical_mist_wisp.png'
if not mist_texture.exists() or png_size(mist_texture)[0] < 128:
    raise SystemExit('ASSET_AUDIT_FAIL physical_mist_texture')

for required in ('main.py','README.md','DESIGN_AUTHORITY.md','RUN_GAME.bat','run_game.sh','requirements.txt'):
    if not (ROOT / required).exists():
        raise SystemExit(f'ASSET_AUDIT_FAIL missing_file={required}')

print(
    'ASSET_AUDIT_PASS '
    f'textures={len(TEXTURES)} min_texture=512 '
    f'ocean_channels={channels} ocean_rate={rate} ocean_duration={duration:.2f} '
    f'ocean_peak_dbfs={peak_db:.2f} loop_seam={seam:.5f} zones={len(cfg["zones"])} district_music_tracks={len(expected_music)} distinct_music=5 gleebs_audio=2 physical_mist=1'
)

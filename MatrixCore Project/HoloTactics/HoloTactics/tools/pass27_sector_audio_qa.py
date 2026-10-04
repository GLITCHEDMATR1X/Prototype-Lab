from __future__ import annotations

import hashlib
import json
import wave
from pathlib import Path

from holotactics_audio import (
    HoloSfx,
    MUSIC_CUES,
    SECTOR_MUSIC_CUES,
    ensure_music_assets,
    validate_music_assets,
)

ROOT = Path(__file__).resolve().parents[1]

class FakeTrack:
    PLAYING = 2
    READY = 1
    def __init__(self, name: str):
        self.name=name; self.loop=False; self.volume=1.0; self.plays=0; self.stops=0; self._status=self.READY
    def setLoop(self, v): self.loop=bool(v)
    def setVolume(self, v): self.volume=float(v)
    def play(self): self.plays+=1; self._status=self.PLAYING
    def stop(self): self.stops+=1; self._status=self.READY
    def status(self): return self._status

class FakeLoader:
    def __init__(self): self.tracks={}
    def loadSfx(self, path): return FakeTrack(str(path))
    def loadMusic(self, path):
        t=FakeTrack(str(path)); self.tracks[str(path)]=t; return t


def wav_stats(path: Path):
    with wave.open(str(path), 'rb') as w:
        frames=w.readframes(w.getnframes())
        first=int.from_bytes(frames[:2], 'little', signed=True)
        last=int.from_bytes(frames[-2:], 'little', signed=True)
        return {
            'rate': w.getframerate(), 'channels': w.getnchannels(), 'frames': w.getnframes(),
            'duration': w.getnframes()/w.getframerate(), 'first': first, 'last': last,
            'seam_delta': abs(last-first), 'sha256': hashlib.sha256(frames).hexdigest(),
        }


def main():
    ensure_music_assets(ROOT)
    checks=[]
    def check(name, ok, detail=''):
        checks.append({'name':name,'pass':bool(ok),'detail':detail})
    check('five_sector_music_mappings', sorted(SECTOR_MUSIC_CUES)==[1,2,3,4,5])
    check('sector_cues_unique', len(set(SECTOR_MUSIC_CUES.values()))==5)
    check('all_music_assets_valid', validate_music_assets(ROOT)==[], str(validate_music_assets(ROOT)))

    stats={}
    for sector,cue in SECTOR_MUSIC_CUES.items():
        spec=MUSIC_CUES[cue]
        path=ROOT/spec.filename
        st=wav_stats(path); stats[str(sector)]={'cue':cue,'file':spec.filename,**st}
        check(f'sector_{sector}_wav_44k_mono', st['rate']==44100 and st['channels']==1)
        check(f'sector_{sector}_loop_seam', st['seam_delta'] < 1200, f"delta={st['seam_delta']}")
    check('sector_waveforms_distinct', len({v['sha256'] for v in stats.values()})==5)

    loader=FakeLoader(); audio=HoloSfx(loader, ROOT)
    c1=SECTOR_MUSIC_CUES[1]; c2=SECTOR_MUSIC_CUES[2]
    check('play_sector1', audio.play_music(c1) and audio.active_music_key==c1)
    t1=audio.music[c1]
    plays_before=t1.plays
    check('same_cue_no_restart', audio.play_music(c1) and t1.plays==plays_before)
    check('switch_sector2', audio.play_music(c2) and audio.active_music_key==c2)
    check('previous_track_stopped', t1.stops==1, f"stops={t1.stops}")
    check('new_track_looped', audio.music[c2].loop is True)
    audio.toggle_music(); check('mute_stops_music', audio.music_muted and audio.music[c2].stops>=1)
    audio.toggle_music(); check('unmute_resumes_current_sector', (not audio.music_muted) and audio.active_music_key==c2 and audio.music[c2].plays>=2)

    passed=sum(1 for c in checks if c['pass'])
    out={'passed':passed,'total':len(checks),'checks':checks,'sector_stats':stats}
    (ROOT/'reports'/'pass27_audio_proof.json').write_text(json.dumps(out, indent=2))
    print(f'Pass 27 audio identity QA: {passed}/{len(checks)} PASS')
    for c in checks:
        if not c['pass']: print('FAIL',c)
    raise SystemExit(0 if passed==len(checks) else 1)

if __name__=='__main__': main()

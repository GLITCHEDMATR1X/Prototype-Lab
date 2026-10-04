from pathlib import Path
import importlib.util, json, sys
ROOT=Path(__file__).resolve().parents[1]
# Import source without constructing ShowBase. The test exercises only the pooled cue dispatcher.
sys.argv=['audio_pool_logic_test']
spec=importlib.util.spec_from_file_location('ascii_matter_pass30', ROOT/'main.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

class FakeSound:
    def __init__(self): self.stops=0; self.times=[]; self.plays=0
    def stop(self): self.stops+=1
    def setTime(self,v): self.times.append(float(v))
    def play(self): self.plays+=1

obj=mod.ASCIIMatterLab.__new__(mod.ASCIIMatterLab)
fire=[FakeSound() for _ in range(mod.WEAPON_AUDIO_POOL_FIRE)]
impact=[FakeSound() for _ in range(mod.WEAPON_AUDIO_POOL_IMPACT)]
obj.weapon_sfx={'left_fire':fire,'left_impact':impact}
obj.weapon_audio_cursor={'left_fire':0,'left_impact':0}
obj._winsound=None
obj.weapon_audio_specs={}
for _ in range(mod.WEAPON_AUDIO_POOL_FIRE*2+3): obj._play_weapon_sfx('left_fire')
for _ in range(mod.WEAPON_AUDIO_POOL_IMPACT*2+1): obj._play_weapon_sfx('left_impact')
checks={
 'fire_pool_size':len(fire)==12,
 'impact_pool_size':len(impact)==8,
 'all_fire_voices_used':all(v.plays>=2 for v in fire),
 'all_impact_voices_used':all(v.plays>=2 for v in impact),
 'fire_cursor_rotates':obj.weapon_audio_cursor['left_fire']==3,
 'impact_cursor_rotates':obj.weapon_audio_cursor['left_impact']==1,
 'every_play_rewinds_voice':all(len(v.times)==v.plays and all(t==0.0 for t in v.times) for v in fire+impact),
 'no_single_voice_monopoly':max(v.plays for v in fire)-min(v.plays for v in fire)<=1,
}
out={'schema':'ascii_matter.pass30.audio_pool_logic.v1','result':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'fire_play_counts':[v.plays for v in fire],'impact_play_counts':[v.plays for v in impact]}
(ROOT/'verification/pass30_audio_pool_logic.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
raise SystemExit(0 if out['result']=='PASS' else 1)

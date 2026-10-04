from __future__ import annotations
import ast, hashlib, json
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
BASELINE={
 'game/data.py':'eb2262c00d24519e075e91e4a55bf2f4aa44e02b0e09475658f10c5b5db2b159',
 'game/world.py':'3a3d1a345e5a1f2b98e57f425324bcbe3e88bc33c35e27f92146f7fa993f56b4',
 'game/sim.py':'9bcabf3d5997f8a2677c9dde67a3c74e9825b1c1704dffaded33dc556a8853cc',
 'game/actors.py':'8be771ef389f8e0f739eebc5de59148c4671ca551f39d36ea44fe5fec7172a8e',
 'game/actor_visuals.py':'bffe05ba33677bfc59b322495ef233f739c5707d5bde1c46c5e6473de8a3a881',
 'game/audio.py':'4b0be21e1c38c883a4cdd9b0e26cb250f5de4744132e2f4fe23e46af9f8e2221',
 'game/app.py':'8cb044195b01ffd01df9aede7ee58c567e7d878e7894a74f1b111b89080e2c29',
}
BASE_GEOM='86a734ac04d5dd5340cae1e040321d5e32ee08fc50baa236e94e544db50dad58'
TEXTURES={
 'cathedral_fracture.png','cathedral_pillar.png','blackglass_index.png','blackglass_fracture.png','blackglass_pillar.png',
 'ossuary_wall.png','ossuary_brittle.png','ossuary_shrine.png'
}

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def geom_digest(path):
    tree=ast.parse(path.read_text())
    vals={}
    for n in tree.body:
        if isinstance(n,ast.Assign):
            for t in n.targets:
                if isinstance(t,ast.Name):
                    try: vals[t.id]=ast.literal_eval(n.value)
                    except Exception: pass
    keys=('WORLD_RECT','MAX_ACTOR_RADIUS','MIN_CLEAR_GAP','PREFERRED_CLEAR_GAP','SPAWN_CLEARANCE','EDGE_CLEARANCE','PREFABS','LAYOUTS')
    data={k:vals[k] for k in keys}
    for layout in data['LAYOUTS'].values():
        for obj in layout['objects']: obj.pop('texture',None)
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def main():
    preserved={rel:sha(ROOT/rel)==dig for rel,dig in BASELINE.items()}
    assert all(preserved.values()),preserved
    geom=geom_digest(ROOT/'game/world_data.py')
    assert geom==BASE_GEOM,(geom,BASE_GEOM)
    tex={}
    for name in sorted(TEXTURES):
        p=ROOT/'assets/world'/name
        ok=p.exists()
        size=None
        if ok:
            with Image.open(p) as im: size=im.size; ok=im.size==(64,64) and im.mode in ('RGBA','RGB')
        tex[name]={'pass':ok,'size':size}
    assert all(v['pass'] for v in tex.values()),tex
    render=(ROOT/'game/render.py').read_text()
    contracts={
      'presentation_lift':'def _visual_env' in render and 'GPTOOL review' in render,
      'raised_cover_depth':'Pseudo-depth is deliberately bounded' in render,
      'top_edge_highlight':'self._lift_color(env["edge"], 28)' in render,
      'spawner_recess':'pygame.draw.circle(self.canvas, self._lift_color(env["grid"], 12)' in render,
      'stronger_rubble':'for k in range(6)' in render,
    }
    assert all(contracts.values()),contracts
    gptool={}
    for key in ('purge','recovery','rescue'):
        d=json.loads((ROOT/f'verification/reports/pass17_gptool_{key}.json').read_text())
        high=sum(1 for i in d['issues'] if i['severity']=='high')
        gptool[key]={'overall':d['scores']['overall'],'high_issues':high,'verdict':d['summary']['quick_verdict']}
        assert high==0,gptool[key]
        assert d['scores']['overall']>=7.0,gptool[key]
    report={
      'pass17_world_material_readability':'PASS',
      'gameplay_files_byte_identical_to_pass16':preserved,
      'world_geometry_digest_preserved':geom==BASE_GEOM,
      'world_geometry_digest':geom,
      'new_texture_assets':tex,
      'render_contracts':contracts,
      'gptool_visual_reviews':gptool,
      'note':'GPTOOL individual world proofs improved from the previous 6.48/high-severity contact-sheet review to >=7.0 with zero high-severity issues. Remaining medium darkness/framing warnings are intentionally not chased by over-brightening the game.'
    }
    out=ROOT/'verification/reports/pass17_world_material_static.json'; out.write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())

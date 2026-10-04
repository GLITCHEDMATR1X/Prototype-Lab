#!/usr/bin/env python3
from __future__ import annotations
import ast, hashlib, math, random, sys, wave
from heapq import heappush, heappop
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'dreamcrawler_core.py'
results=[]

def check(name, cond, detail=''):
    ok=bool(cond); results.append((name,ok,detail)); print(('PASS' if ok else 'FAIL'), name, detail)
    return ok

text=SRC.read_text(encoding='utf-8')
tree=ast.parse(text)
check('Python AST', True)
check('Game-folder anchored paths', 'BASE_DIR = os.path.dirname(os.path.abspath(__file__))' in text and '_path("assets", "sfx"' in text)
check('Standalone supported', 'DREAMCRAWLER_REQUIRE_MATRIX' in text and 'FORCE_MATRIX_LAUNCH = os.getenv' in text)
check('Attack is event-edge triggered', 'elif e.key == pygame.K_SPACE:' in text and 'attack_pressed = True' in text)
check('Attack cooldown exists', 'p.attack_cooldown <= 0.0' in text and 'p.attack_cooldown = 0.34' in text)
check('Crawler uses A*', 'self.path = astar(current, goal' in text)
check('Crawler collision resolves', 'resolve_circle(nx, ny, grid, radius=8.0)' in text)
check('Crawler update uses limited player perception', 'self.monster.update(dt, self.players, self.grid)' in text)
check('Footstep cue wired', 'self._play_spatial_sfx("step"' in text)
check('Footsteps emit crawler noise', 'self.monster.hear_noise(p.x, p.y, 6.2 if p.ai else 6.8, "step")' in text)
check('Four crawler profiles present', all(name in text for name in ('"listener"','"watcher"','"stalker"','"warden"')))
check('Crawler sight requires LOS', 'line_of_sight(grid, mt[0], mt[1], pt[0], pt[1])' in text)
check('Crawler has awareness states', all(s in text for s in ('"idle"','"investigate"','"chase"','"stalk"','"return"')))
check('Player chase alert cue wired', 'play_sfx("alert", 0.58)' in text)
check('Monster sprite factory present', 'def make_monster_sprite(seed):' in text and 'pygame.mask.from_surface' in text)
check('Monster uses shaped sprite', 'self.base = make_monster_sprite(seed)' in text and 'noisy_surface((30, 34)' not in text)
check('Knowledge meetings require proximity', 'self.knowledge_exchange_radius = TILE * 2.35' in text and 'math.hypot(a.x - b.x, a.y - b.y) > self.knowledge_exchange_radius' in text)
check('Knowledge meetings require line of sight', 'line_of_sight(self.grid, at[0], at[1], bt[0], bt[1])' in text)
check('Knowledge network runs during play', 'self._process_knowledge_meetings()' in text)
check('No geometry knowledge sharing', 'receiver.known_open.update' not in text and 'receiver.known_walls.update' not in text)
check('Actionable knowledge sharing', 'receiver.known_stairs = sender.known_stairs' in text and 'receiver.known_monster = sender.known_monster' in text and 'receiver.known_weapons.update' in text and 'receiver.known_treasures.update' in text)

# Extract the pure map/path functions from source to test actual authored logic without importing pygame.
needed={'clamp','in_bounds','carve_room','carve_hall','generate_grid','is_wall','astar','merge_expedition_knowledge','direction_word','line_of_sight','crawler_profile_for_seed','crawler_profile_summary','resolve_circle'}
body=[]
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name in needed:
        body.append(node)
    elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'CRAWLER_PROFILES' for t in node.targets):
        body.append(node)
    elif isinstance(node, ast.ClassDef) and node.name == 'Monster':
        body.append(node)
mod=ast.Module(body=body,type_ignores=[]); ast.fix_missing_locations(mod)
ns={'math':math,'random':random,'heappush':heappush,'heappop':heappop,
    'GRID_W':78,'GRID_H':50,'WALL':1,'FLOOR':0,'STAIRS':3,'TILE':20,'PLAYER_R':7.0,
    'make_monster_sprite':lambda seed: None}
exec(compile(mod,str(SRC),'exec'),ns)

profiles=[ns['crawler_profile_for_seed'](i) for i in range(4)]
check('Profile seed rotation', profiles==['listener','watcher','stalker','warden'], str(profiles))
check('Profile summaries readable', all(':' in ns['crawler_profile_summary'](p) for p in profiles))

class DummyPlayerSense:
    def __init__(self,name,x,y,alive=True):
        self.name=name; self.x=x; self.y=y; self.alive=alive

open_grid=[[0 for _ in range(78)] for _ in range(50)]
Monster=ns['Monster']
listener=Monster(5.5*20,5.5*20,seed=0,home_tile=(5,5))
watcher=Monster(5.5*20,5.5*20,seed=1,home_tile=(5,5))
check('Listener hears distant footstep', listener.hear_noise(13.0*20,5.5*20,8.0,'step'))
check('Watcher ignores same distant footstep', not watcher.hear_noise(13.0*20,5.5*20,8.0,'step'))
far=DummyPlayerSense('Far',14.0*20,5.5*20)
watcher.update(0.1,[far],open_grid)
check('Watcher long sight enters chase', watcher.state=='chase' and watcher.target_name=='Far', watcher.state)
listener2=Monster(5.5*20,5.5*20,seed=0,home_tile=(5,5))
listener2.update(0.1,[far],open_grid)
check('Listener short sight stays idle at same range', listener2.state=='idle', listener2.state)
far.x=30*20
watcher.update(0.1,[far],open_grid)
check('Lost sight becomes investigation', watcher.state=='investigate' and watcher.last_known is not None, watcher.state)
warden=Monster(5.5*20,5.5*20,seed=3,home_tile=(5,5))
check('Warden ignores remote footstep outside territory', not warden.hear_noise(25*20,5.5*20,20.0,'step'))
warden.x=18*20; warden.y=5.5*20
warden.update(0.1,[],open_grid)
check('Warden returns toward stair region when calm', warden.state in ('return','idle') and warden.path_target is not None, warden.state)
stalker_group=Monster(5.5*20,5.5*20,seed=2,home_tile=(5,5))
p1=DummyPlayerSense('A',10*20,5.5*20); p2=DummyPlayerSense('B',11*20,5.5*20)
stalker_group.update(0.1,[p1,p2],open_grid)
check('Stalker shadows grouped explorers', stalker_group.state=='stalk', stalker_group.state)
stalker_iso=Monster(5.5*20,5.5*20,seed=2,home_tile=(5,5))
stalker_iso.update(0.1,[p1],open_grid)
check('Stalker commits on isolated explorer', stalker_iso.state=='chase', stalker_iso.state)

class DummyKnowledge:
    def __init__(self):
        self.known_open=set()
        self.known_walls=set()
        self.known_treasures=set()
        self.known_weapons=set()
        self.known_stairs=None
        self.known_monster=None
        self.known_fragment=None

sender=DummyKnowledge(); receiver=DummyKnowledge()
sender.known_open={(1,1),(2,2)}; sender.known_walls={(3,3)}
sender.known_treasures={(10,10),(11,11)}; sender.known_weapons={(20,20)}
sender.known_stairs=(30,30); sender.known_monster=(25,25)
shared=ns['merge_expedition_knowledge'](sender,receiver)
check('Relay copies stairs', receiver.known_stairs==(30,30) and shared['stairs'])
check('Relay copies crawler last-known', receiver.known_monster==(25,25) and shared['monster'])
check('Relay copies supply discoveries', receiver.known_treasures==sender.known_treasures and receiver.known_weapons==sender.known_weapons)
check('Relay preserves private map', not receiver.known_open and not receiver.known_walls)
relay=DummyKnowledge(); ns['merge_expedition_knowledge'](receiver,relay)
check('Relayed knowledge can propagate onward', relay.known_stairs==(30,30) and relay.known_monster==(25,25) and relay.known_weapons=={(20,20)})
check('Direction wording deterministic', ns['direction_word']((5,5),(9,5))=='east' and ns['direction_word']((5,5),(5,1))=='north')
reachable=0
path_min=10**9
for seed in range(200):
    g,start,stairs=ns['generate_grid'](seed)
    path=ns['astar'](start,stairs,lambda t: ns['in_bounds'](*t) and not ns['is_wall'](g,*t))
    if path and all(not ns['is_wall'](g,*t) for t in path):
        reachable+=1; path_min=min(path_min,len(path))
check('200/200 generated rooms reachable',reachable==200,f'{reachable}/200; shortest path {path_min}')

# Audio integrity and expected cues.
expected={'spawn','exit','step','caught','hit','loot','alert'}
found={p.stem for p in (ROOT/'assets'/'sfx').glob('*' + '.wav')}
check('All SFX WAV cues present',expected<=found,','.join(sorted(found)))
for p in sorted(ROOT.glob('assets' + '/**/' + '*' + '.wav')):
    try:
        with wave.open(str(p),'rb') as w:
            valid=w.getframerate()==44100 and w.getsampwidth()==2 and w.getnframes()>100
            info=f'{w.getnchannels()}ch {w.getframerate()}Hz {w.getnframes()/w.getframerate():.2f}s'
    except Exception as e:
        valid=False; info=str(e)
    check(f'WAV {p.relative_to(ROOT)}',valid,info)

# Package hygiene.
forbidden=[]
for p in ROOT.rglob('*'):
    if '__pycache__' in p.parts or p.suffix=='.pyc' or p.name.endswith('~'):
        forbidden.append(str(p.relative_to(ROOT)))
check('No cache/temp residue',not forbidden,','.join(forbidden))

ok=all(r[1] for r in results)
out=ROOT/'validation.txt'
out.write_text('\n'.join(f"{'PASS' if passed else 'FAIL'} | {name} | {detail}" for name,passed,detail in results)+f"\n\nFINAL: {'PASS' if ok else 'FAIL'} ({sum(r[1] for r in results)}/{len(results)})\n",encoding='utf-8')
print(f"\nFINAL {'PASS' if ok else 'FAIL'} {sum(r[1] for r in results)}/{len(results)}")
sys.exit(0 if ok else 1)

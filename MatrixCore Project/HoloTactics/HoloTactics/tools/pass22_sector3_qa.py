from holotactics_core import GameState

checks=[]
def check(name, cond):
    checks.append((name, bool(cond)))
    if not cond:
        raise AssertionError(name)

def place_adjacent(state, node_id):
    gx, gy = state.nodes[node_id].pos
    candidates=[(gx-1,gy),(gx+1,gy),(gx,gy-1),(gx,gy+1)]
    for pos in candidates:
        if state.in_bounds(pos) and state.unit_at(pos) is None and not state.is_node_position(pos):
            state.units['gleebs'].pos=pos
            state.selected_unit_id='gleebs'
            state.cursor=state.nodes[node_id].pos
            state.units['gleebs'].acted=False
            return
    raise AssertionError(f'no adjacent tile for {node_id}')

s=GameState(sector_index=3)
check('sector3 names fracture anchors', [s.nodes[k].name for k in ('patch','die','memory')] == ['Fracture Anchor West','Fracture Anchor Center','Fracture Anchor East'])
check('sector3 starts 0/3', s.fracture_anchor_count()==0 and not s.core_destroyed and not s.memory_collected)
check('three anchors begin fractured', all(s.tiles[s.nodes[k].pos].state=='fracture' for k in ('patch','die','memory')))
check('objective identifies patch pulse', 'Patch Pulse' in s.objective_text() and '0/3' in s.objective_text())

# System ticks must not silently clear mission anchors.
for _ in range(4):
    s.system_phase()
check('mission fractures persist through system phase', all(s.tiles[s.nodes[k].pos].state=='fracture' for k in ('patch','die','memory')))

# Standing on an anchor is hazardous but does not complete it.
west=s.nodes['patch'].pos
s.units['gleebs'].pos=west
hp=s.units['gleebs'].hp
s._resolve_tile_entry(s.units['gleebs'], s.tiles[west])
check('walking onto anchor does not stabilize', s.nodes['patch'].captured_by is None and s.fracture_anchor_count()==0)
check('walking onto anchor remains hazardous', s.units['gleebs'].hp==hp-1)

# Non-Gleebs cannot use the objective action.
s.selected_unit_id='guard'; s.cursor=west; s.units['guard'].acted=False
check('only Gleebs can patch anchors', not s.use_gleebs_patch_pulse() and s.fracture_anchor_count()==0)

# Any order is legal: Center, East, West.
for idx,node_id in enumerate(('die','memory','patch'), start=1):
    place_adjacent(s,node_id)
    check(f'{node_id} patch succeeds', s.use_gleebs_patch_pulse())
    check(f'{node_id} marked stable', s.nodes[node_id].captured_by=='player' and s.tiles[s.nodes[node_id].pos].state=='stable')
    check(f'count after {node_id}', s.fracture_anchor_count()==idx)
    if idx < 3:
        check(f'gate remains bound after {idx}', not s.core_destroyed and not s.extraction_open())

check('all anchors auto-collapse gate', s.fracture_anchors_stabilized() and s.core_destroyed and s.memory_collected)
check('extraction opens automatically', s.extraction_open() and s.tiles[s.nodes['extract'].pos].state=='extraction')
check('stability gate recorded captured', s.nodes['core'].captured_by=='player')

# Direct attack must never be the Sector 3 solution.
s2=GameState(sector_index=3)
s2.selected_unit_id='guard'; s2.units['guard'].pos=(s2.nodes['core'].pos[0]-1,s2.nodes['core'].pos[1]); s2.cursor=s2.nodes['core'].pos
check('sector3 gate rejects direct attack', not s2.attack_cursor() and not s2.core_destroyed)

# Finish route using an ordinary squad unit once open.
s.units['runner'].pos=s.nodes['extract'].pos
s._resolve_tile_entry(s.units['runner'], s.tiles[s.nodes['extract'].pos])
check('sector3 extraction completes', s.extraction_reached and s.victory())

# Neighboring sectors preserve their identities.
s1=GameState(sector_index=1)
check('sector1 original Memory Node retained', s1.nodes['memory'].name=='Memory Node' and s1.nodes['core'].name=='Game Master Core')
s2=GameState(sector_index=2)
check('sector2 relay identity retained', s2.nodes['memory'].name=='Signal Relay Alpha' and s2.nodes['patch'].name=='Signal Relay Beta')

print(f'Pass 22 Sector 3 QA: {len(checks)}/{len(checks)} PASS')
for name,_ in checks:
    print('PASS', name)

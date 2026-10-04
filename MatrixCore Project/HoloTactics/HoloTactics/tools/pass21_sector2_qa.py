from holotactics_core import GameState

checks = []
def check(name, cond):
    if not cond:
        raise AssertionError(name)
    checks.append(name)

def enter(st, uid, node_id):
    unit = st.units[uid]
    pos = st.nodes[node_id].pos
    unit.pos = pos
    st._resolve_tile_entry(unit, st.tiles[pos])

# New Sector 2 identity.
s = GameState(sector_index=2)
check("sector2 relay names", s.nodes["memory"].name == "Signal Relay Alpha" and s.nodes["patch"].name == "Signal Relay Beta")
check("sector2 starts locked", not s.core_destroyed and not s.extraction_open())
enter(s, "runner", "memory")
check("relay alpha squad capturable", s.memory_collected and s.nodes["memory"].captured_by == "player")
check("one relay does not unlock", not s.core_destroyed and not s.extraction_open())
enter(s, "guard", "patch")
check("relay beta squad capturable", s.patch_node_captured())
check("both relays collapse route lock", s.core_destroyed and s.nodes["core"].captured_by == "player")
check("both relays open extraction", s.extraction_open() and s.tiles[s.nodes["extract"].pos].state == "extraction")
check("objective advances to extraction", s.objective_text() == "Reach the Extraction Gate")
enter(s, "gleebs", "extract")
check("sector2 can complete", s.victory())

# Reverse capture order must also work.
r = GameState(sector_index=2)
enter(r, "guard", "patch")
check("beta-first remains locked", r.patch_node_captured() and not r.core_destroyed)
enter(r, "runner", "memory")
check("reverse order synchronizes", r.core_destroyed and r.extraction_open())

# Route Lock cannot be bypassed by the old direct-core attack.
a = GameState(sector_index=2)
a.selected_unit_id = "runner"
a.units["runner"].pos = (a.nodes["core"].pos[0] - 1, a.nodes["core"].pos[1])
a.cursor = a.nodes["core"].pos
check("route lock rejects direct attack", a.attack_cursor() is False and not a.core_destroyed)

# Neighboring accepted mission rule stays unchanged.
b = GameState(sector_index=1)
enter(b, "runner", "memory")
check("sector1 memory remains Gleebs-only", not b.memory_collected)
enter(b, "gleebs", "memory")
check("sector1 original memory rule preserved", b.memory_collected and not b.core_destroyed)

print(f"Pass 21 Sector 2 QA: {len(checks)}/{len(checks)} PASS")
for item in checks:
    print("PASS", item)

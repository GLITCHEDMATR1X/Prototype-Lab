from __future__ import annotations

import os
os.environ.setdefault('GPT_BRIDGE_SMOKE','1')

from holotactics_actor_specs import ACTOR_VISUAL_SPECS, validate_actor_visual_specs
from main import HoloTacticsApp

checks=[]
issues=validate_actor_visual_specs()
assert not issues, issues
checks.append('actor visual specs valid')

app=HoloTacticsApp()
try:
    required_fragments={
        'gleebs': ('gleebs_left_ear','gleebs_right_ear','gleebs_cyan_orb','gleebs_red_orb'),
        'guard': ('guard_anchor_shield','guard_heavy_core'),
        'runner': ('runner_phase_fin_upper','runner_phase_fin_lower'),
        'anomaly': ('anomaly_left_blade','anomaly_right_blade','anomaly_broken_mass'),
        'sentry': ('sentry_target_eye','sentry_left_fin','sentry_right_fin','sentry_barrel'),
    }
    for actor_id, fragments in required_fragments.items():
        ids=[uid for uid in app.unit_nodes if uid==actor_id or uid.startswith(actor_id)]
        assert ids, actor_id
        node=app.unit_nodes[ids[0]]
        names={np.getName() for np in node.findAllMatches('**')}
        for frag in fragments:
            assert frag in names, (actor_id, frag)
        checks.append(f'{actor_id} silhouette components present')

    # Bound each representative piece in its own coordinates.  Keep tactical footprint/height restrained.
    for actor_id in ('gleebs','guard','runner','anomaly','sentry'):
        uid=next(uid for uid in app.unit_nodes if uid==actor_id or uid.startswith(actor_id))
        node=app.unit_nodes[uid]
        bounds=node.getTightBounds(node)
        assert bounds and bounds[0] is not None and bounds[1] is not None, actor_id
        lo,hi=bounds
        width=max(hi.x-lo.x, hi.y-lo.y)
        height=hi.z-lo.z
        spec=ACTOR_VISUAL_SPECS[actor_id]
        assert width <= spec.footprint_radius*2.35 + 0.08, (actor_id,width,spec.footprint_radius)
        assert height <= spec.max_height + 0.10, (actor_id,height,spec.max_height)
        assert height >= 0.65, (actor_id,height)
        checks.append(f'{actor_id} tactical bounds valid')

    # Enemy/player rings retain faction coding.
    assert app._actor_ring_color('anomaly_0')[0] > 0.9
    assert app._actor_ring_color('sentry_0')[0] > 0.9
    assert app._actor_ring_color('gleebs')[1] > 0.9
    checks.append('faction ring coding preserved')
finally:
    app.destroy()

print(f'Pass 26 Actor Visual QA: {len(checks)}/{len(checks)} PASS')
for c in checks:
    print('PASS',c)

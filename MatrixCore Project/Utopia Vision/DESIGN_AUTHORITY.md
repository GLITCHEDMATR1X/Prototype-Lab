# Pass 59 Design Authority

Base: Pass 58 — AR Public Annex Coverage.

Primary target: continue the AR coverage audit and remove the tree presentation the user rejected. No new gameplay systems.

Confirmed AR issue:
- Full-screen AR inspection showed broad `promenade_node` pads as flat muted rectangles at close range, interrupting otherwise textured boulevards.
- Physical park slabs also sat above the broad district AR ground fields, so their plain green surfaces could leak through the AR presentation from some approaches.

Pass 59 repair:
- remove all city/exterior tree creation and corresponding trunk collision/shadow sources;
- retain parks in physical reality but hide their physical slabs from the AR camera;
- add eight district-textured AR park counterparts matching the real footprints;
- convert all 24 promenade node pads from flat color boxes to district-textured AR pavement;
- add an AR coverage smoke gate requiring tree-free runtime state, 8/8 park coverage and 24/24 textured node pads.

Frozen systems:
- Pass 58 annex AR exterior coverage;
- Pass 57 transit clearance and gate traversal;
- Pass 56 surface winding;
- residents, Gleebs, interiors, Utopia project systems, weather, celestial system, audio, controls and AR optimization logic.

Reject if any tree geometry/collision remains, park surfaces leak as physical green in AR, promenade node pads return to broad flat blocks, or any frozen regression test fails.

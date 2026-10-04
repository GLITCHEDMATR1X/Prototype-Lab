from pathlib import Path
import ast, json
ROOT=Path(__file__).resolve().parents[1]
src=(ROOT/'main.py').read_text()
tree=ast.parse(src)
methods={n.name:n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
body=json.loads((ROOT/'assets/cache/generic_male_ascii.json').read_text())
checks={
 'dense_body_2200': body.get('sample_count')==2200 and len(body.get('points',[]))==2200,
 'vector_ascii_batching': 'ASCII_STROKES' in src and 'GeomLines' in src and '_rebuild_glyph_batch' in methods,
 'one_batch_per_rig_branch': 'self.glyph_batches' in src and 'self.binding_members' in src,
 'distance_lod': '_update_render_lod' in methods and 'LOD_KEEP_THRESHOLDS' in src and 'LOD_BAL_DISTANCE' in src,
 'single_firetime_hit_query': "hit = self._find_shot_hit(cam_start, far, hit_threshold)" in src,
 'broad_phase_binding_bounds': '_build_binding_bounds' in methods and "self.perf_counters['shot_binding_checks']" in src,
 'no_projectile_rescan': "hit=self._find_shot_hit(old" not in src and "hit = self._find_shot_hit(old" not in src,
 'cached_joint_local_target': '_cache_hit_target' in methods and '_cached_hit_world' in methods,
 'localized_damage_members': 'self.binding_members.get(bind' in src,
 'wound_batch_rebuild': '_wound_affected_bindings' in methods and '_refresh_wound_colors' in methods,
 'settled_fragment_no_redundant_transform': 'if not f.settled:\n                f.node.setPos(f.pos); f.node.setR(f.roll)' in src,
 'hud_text_cache': 'if txt != self.status_cache' in src,
 'internal_detail_lod': '_set_internal_detail_visible' in methods,
 'shared_projectile_geometry': 'self.projectile_proto.get(key)' in src,
 'static_rifle_flatten': 'fill_root.flattenStrong(); wire_root.flattenStrong()' in src,
 'threaded_render_pipeline': 'threading-model Cull/Draw' in src,
 'shorter_far_plane': 'self.camLens.setNearFar(0.05, 60.0)' in src,
 'impact_reactions_preserved': '_apply_impact_reaction' in methods and '_update_impact_reactions' in methods,
}
result='PASS' if all(checks.values()) else 'FAIL'
out={'schema':'ascii_matter.pass28.performance_hotpath.v1','result':result,'checks':checks}
(ROOT/'verification').mkdir(exist_ok=True)
(ROOT/'verification/pass28_performance_hotpath.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
raise SystemExit(0 if result=='PASS' else 1)

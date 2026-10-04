from __future__ import annotations
import ast, json, wave, sys
from pathlib import Path
sys.dont_write_bytecode = True

ROOT=Path(__file__).resolve().parents[1]
checks=[]
def check(name, cond, detail=''):
    checks.append((name,bool(cond),str(detail)))
    print(('PASS' if cond else 'FAIL'), name, detail)
    return bool(cond)

# Source syntax and JSON parse.
for p in sorted(ROOT.rglob('*.py')):
    if '__pycache__' in p.parts: continue
    try:
        source=p.read_text(encoding='utf-8')
        ast.parse(source, filename=str(p))
        compile(source, str(p), 'exec')
        check('syntax:'+str(p.relative_to(ROOT)), True)
    except Exception as e:
        check('syntax:'+str(p.relative_to(ROOT)), False, e)
for p in sorted(ROOT.rglob('*.json')):
    if p.name in {'source_manifest_pass04.json','source_manifest_pass05.json','source_manifest_pass06.json'}:
        continue
    try:
        json.loads(p.read_text(encoding='utf-8'))
        check('json:'+str(p.relative_to(ROOT)), True)
    except Exception as e:
        check('json:'+str(p.relative_to(ROOT)), False, e)

# Audio integrity.
audio=list((ROOT/'assets/audio').rglob('*.wav'))
check('audio_wav_count', len(audio)==46, len(audio))
for p in sorted(audio):
    try:
        with wave.open(str(p),'rb') as w:
            ch=w.getnchannels(); sw=w.getsampwidth(); rate=w.getframerate(); frames=w.getnframes(); dur=frames/max(rate,1)
        category=p.relative_to(ROOT/'assets/audio').parts[0]
        expected_ch=1 if category in {'sfx','transition'} else 2
        check('wav:'+str(p.relative_to(ROOT)), ch==expected_ch and sw==2 and rate==22050 and frames>0, f'ch={ch} rate={rate} dur={dur:.2f}s')
    except Exception as e:
        check('wav:'+str(p.relative_to(ROOT)), False, e)

adapter=(ROOT/'standalone_native_adapter.py').read_text(encoding='utf-8')
# Native lifecycle / task hygiene.
for token in ['class HoloVerseNativeMode','def enter(self)','def update(self, dt: float)','def get_result(self)','def exit(self)','def get_native_contract(self)','def create_mode(host']:
    check('adapter_token:'+token, token in adapter)
check('adapter_no_ShowBase_constructor', 'ShowBase(' not in adapter)
check('adapter_audio_runtime_cleanup', 'VectorArenaAudioRuntime' in adapter and 'audio_runtime.stop()' in adapter)
check('adapter_tab_host_owned', '"tab"' in adapter and 'return_to_holoverse' in adapter)
check('adapter_no_enemy_task_sprawl', 'taskMgr.add' not in adapter)
check('adapter_spatial_breach', 'start_positional_loop("breach_core_loop.wav"' in adapter)

# Pass 03 inherited tactical layer.
check('gate_telegraph_runtime', 'def _schedule_spawn_from_script' in adapter and 'def _update_spawn_gate_visuals' in adapter)
check('guardian_special_runtime', 'def _update_guardian_special' in adapter and 'guardian_specials_used' in adapter)
check('hazard_runtime', 'def _build_hazard_pool' in adapter and 'def _update_wave_hazards' in adapter and 'hazard_activations' in adapter)
check('tactical_steering', all(token in adapter for token in ('flank_left','flank_right','boss_support','rear_left','rear_right')))

# Pass 04 upgrade/modal contract.
for token in ['def _open_upgrade_choice','def _select_upgrade','def _update_upgrade_choice','upgrade_pending','upgrade_overlay_root','arena_mutation_profile']:
    check('pass04_token:'+token, token in adapter)
check('upgrade_modal_pauses_combat', 'if self._update_upgrade_choice():\n            return\n        self._update_player(dt)' in adapter)
check('upgrade_modal_no_timeout', 'upgrade_choice_timer' not in adapter and 'upgrade_timeout' not in adapter)
check('upgrade_keyboard_123', all(f'self._select_upgrade({i})' in adapter for i in (1,2,3)))
check('combat_clickthrough_block', '_block_combat_input_until_release' in adapter and 'if not self.upgrade_pending' in adapter)
check('upgrade_hazard_pause', 'if self.wave_complete_pending or self.upgrade_pending' in adapter)
check('upgrade_held_key_guard', 'self._upgrade_key_latches[slot] = self._key_down(str(slot))' in adapter)
check('armor_cap_centralized', 'min(78.0' not in adapter and 'min(82.0' not in adapter and 'self.max_armor' in adapter)
check('result_upgrade_telemetry', all(token in adapter for token in ('"upgrade_stacks"','"upgrades_selected"','"arena_mutation_name"','"arena_mutations_survived"')))

# HoloVerse responder.
manifest=json.loads((ROOT/'holoverse/holoverse_dimension.json').read_text())
identity=json.loads((ROOT/'holoverse/identity.json').read_text())
check('holoverse_compatibility_native', manifest.get('compatibility')=='native')
check('holoverse_native_adapter', manifest.get('native_adapter')=='standalone_native_adapter.py')
check('holoverse_identity', bool(identity.get('dimension_id')))

# Audio profile and new cues.
profile=json.loads((ROOT/'audio_profile.json').read_text())
check('music_variants_3', len(profile.get('music_variants',[]))==3)
check('ambience_loops_2', len(profile.get('ambience_loops',[]))==2)
check('positional_events', len(profile.get('positional_events',[]))>=10)
pass03_audio=('gate_charge','flank_alarm','guardian_charge','guardian_slam','hazard_warning','hazard_discharge')
check('pass03_audio_preserved', all(k in profile.get('events',{}) for k in pass03_audio))
pass04_audio=('upgrade_offer','upgrade_select','mutation_shift')
check('pass04_audio_events', all(k in profile.get('events',{}) for k in pass04_audio))
check('pass04_sfx_files', all((ROOT/'assets/audio/sfx'/(k+'.wav')).is_file() for k in pass04_audio))


# Pass 05 enemy evolution / Guardian phase contract.
pass05_audio=('enemy_evolution','guardian_phase2','guardian_phase3','doctrine_shift')
check('pass05_audio_events', all(k in profile.get('events',{}) for k in pass05_audio))
check('pass05_sfx_files', all((ROOT/'assets/audio/sfx'/(k+'.wav')).is_file() for k in pass05_audio))
check('pass05_adapter_evolution_import', 'from vector_arena_evolution import' in adapter)
check('pass05_enemy_progression_runtime', 'apply_enemy_progression(enemy.variant, self.wave_set, self.wave_kind)' in adapter)
check('pass05_guardian_phase_runtime', 'guardian_phase_for(enemy.hp, enemy.max_hp)' in adapter and 'guardian_phase_profile' in adapter)
check('pass05_doctrine_banner', 'DOCTRINE' not in adapter or 'doctrine_name' in adapter)
check('pass05_result_telemetry', all(t in adapter for t in ('"enemy_evolution_spawns"','"highest_evolution_level_seen"','"guardian_phase_transitions"','"encounter_doctrine"')))

# Pass 06 arena families / large-arena runtime contract.
check('pass06_arena_module_import', 'from vector_arena_arenas import' in adapter)
check('pass06_dynamic_arena_radius', 'self.current_arena_radius' in adapter and 'MAX_ARENA_RADIUS' in adapter)
check('pass06_geometry_rebuild', 'def _build_arena_geometry' in adapter and 'def _clear_arena_geometry' in adapter)
check('pass06_profile_reconstruct', 'def _apply_arena_profile' in adapter and 'self._apply_arena_profile(set_number, rebuild=True)' in adapter)
check('pass06_dynamic_weapon_range', 'self.current_arena_radius * 1.12' in adapter and 'self.current_arena_radius * 1.15' in adapter)
check('pass06_result_telemetry', all(t in adapter for t in ('"arena_family_name"','"arena_diameter"','"largest_arena_radius"','"arena_family_transitions"')))
check('pass07_result_architecture_telemetry', all(t in adapter for t in ('"arena_architecture"','"arena_architecture_piece_count"')))
check('pass07_no_layout_reposition_runtime', 'tx, ty = layout[i]' not in adapter and 'COVER_LAYOUTS[int(layout_index)' not in adapter)
check('pass07_enemy_hard_cover_push', 'def _push_enemy_out_of_cover' in adapter and 'self._push_enemy_out_of_cover(enemy)' in adapter)
check('pass07_hitscan_cover_occlusion', 'def _architecture_blocks_segment' in adapter and 'self._architecture_blocks_segment(eye, target)' in adapter)
check('pass07_repulsor_cover_occlusion', 'forward.dot(aim) >= 0.48 and not self._architecture_blocks_segment(eye, target)' in adapter)
check('pass07_radial_boundary_visual_authority', 'vector_arena_pass07_radial_boundary_ring_' in adapter and 'self.current_arena_radius' in adapter)
check('pass07_no_square_boundary_visual_lie', 'solid_armored_wall_north' not in adapter and 'solid_armored_wall_south' not in adapter)
check('pass07_combat_clips_to_radial_boundary', 'def _clip_segment_to_arena_boundary' in adapter and 'def _clip_combat_segment' in adapter)
check('pass07_spawn_gates_phase_safe_visuals', 'phase_safe_spawn_gate' in adapter and 'left_hardlight_pylon' in adapter and 'right_hardlight_pylon' in adapter)
check('pass07_spawn_gates_not_opaque_fake_cover', '_solid_box_node(f"vector_arena_fps_spawn_gate_' not in adapter)

# Pure-Python director + progression contracts.
try:
    sys.path.insert(0, str(ROOT))
    from vector_arena_waves import build_wave_plan, wave_kind_for, WAVE_SET_SIZE, MAX_ACTIVE_THREATS, GATE_LABELS, TACTIC_ROLES
    from vector_arena_progression import upgrade_choices, upgrade_effects, arena_mutation_for_set, apply_mutation_to_plan, UPGRADE_IDS
    from vector_arena_evolution import enemy_evolution_for, apply_enemy_progression, encounter_doctrine_for, guardian_phase_for, guardian_phase_profile, EVOLUTION_MAX_LEVEL
    from vector_arena_arenas import (arena_profile_for_set, spawn_points_for_profile, hazard_points_for_profile,
        breach_points_for_profile, architecture_pieces_for_profile, validate_architecture, first_architecture_hit, ARENA_FAMILIES, BASE_ARENA_RADIUS, MAX_ARENA_RADIUS, validate_profiles)
    plans=[apply_mutation_to_plan(build_wave_plan(w),(w-1)//5+1,MAX_ACTIVE_THREATS) for w in range(1,61)]
    check('wave_set_size_5', WAVE_SET_SIZE==5, WAVE_SET_SIZE)
    check('wave_types_present', {p['kind'] for p in plans}.issuperset({'ASSAULT','HORDE','BREACH','ELITE','OVERLOAD','BLACKOUT','GUARDIAN'}), sorted({p['kind'] for p in plans}))
    check('guardian_every_fifth', all(wave_kind_for(w)=='GUARDIAN' for w in range(5,61,5)))
    check('active_cap_bounded', all(1 <= p['max_active'] <= MAX_ACTIVE_THREATS for p in plans), max(p['max_active'] for p in plans))
    check('horde_exceeds_concurrent_cap', any(p['kind']=='HORDE' and len(p['queue'])>p['max_active'] for p in plans))
    check('breach_requires_core', all(p['required_breaches']>=1 for p in plans if p['kind']=='BREACH'))
    check('overload_heat_rule', all(p['heat_gain']>1 and p['heat_cool']<1 for p in plans if p['kind']=='OVERLOAD'))
    # Pass 07: generic Cover Layouts remain legacy data only. Runtime architecture
    # must come from one family-specific authority so visible solids and blockers cannot drift.
    check('pass07_legacy_layout_removed', 'COVER_LAYOUTS' not in (ROOT/'vector_arena_waves.py').read_text(encoding='utf-8') and 'COVER_LAYOUTS' not in adapter)
    check('pass07_authoritative_architecture_source', 'architecture_pieces_for_profile(self.arena_profile)' in adapter)
    check('pass07_visible_blocker_parity_source', '_CoverBlock(pos=Vec3(pos.x, pos.y, 0)' in adapter and 'authoritative_solid' in adapter)

    check('spawn_script_matches_queue', all(len(p['spawn_script'])==len(p['queue']) for p in plans))
    check('spawn_gate_indices_valid', all(0 <= d['gate'] < len(GATE_LABELS) for p in plans for d in p['spawn_script']))
    check('spawn_telegraphs_bounded', all(float(d['telegraph']) >= 0.36 for p in plans for d in p['spawn_script']), min(float(d['telegraph']) for p in plans for d in p['spawn_script']))
    check('spawn_roles_valid', all(d['role'] in TACTIC_ROLES for p in plans for d in p['spawn_script']))
    opening=plans[:5]
    check('opening_set_no_rear_ambush', all(d['gate'] not in {5,6} for p in opening for d in p['spawn_script']))
    check('later_sets_can_rear_pressure', any(d['gate'] in {5,6} for p in plans[5:] for d in p['spawn_script']))
    check('horde_contains_flanks', all(any(d['role'] in {'flank_left','flank_right'} for d in p['spawn_script']) for p in plans if p['kind']=='HORDE'))
    check('guardian_front_gate', all(d['gate']==1 for p in plans if p['kind']=='GUARDIAN' for d in p['spawn_script'] if d['variant']=='guardian'))
    check('hazards_only_special_types', all(bool(p['hazard']['enabled']) == (p['kind'] in {'OVERLOAD','BLACKOUT','GUARDIAN'}) for p in plans))
    check('hazard_telegraph_fair', all((not p['hazard']['enabled']) or float(p['hazard']['telegraph']) >= .95 for p in plans))
    check('hazard_damage_bounded_60', all((not p['hazard']['enabled']) or 0 < float(p['hazard']['damage']) <= 38 for p in plans))

    # Long-run issue regression: population stops growing and hazards never one-shot.
    far=[apply_mutation_to_plan(build_wave_plan(w),(w-1)//5+1,MAX_ACTIVE_THREATS) for w in (100,200,500)]
    check('late_wave_population_cap', all(len(p['queue']) <= 90 for p in far), [len(p['queue']) for p in far])
    check('late_hazard_damage_cap', all((not p['hazard']['enabled']) or p['hazard']['damage'] <= 38 for p in far), [p['hazard']['damage'] for p in far])
    check('late_active_cap', all(p['max_active'] <= 22 for p in far), [p['max_active'] for p in far])

    choices=upgrade_choices({})
    check('upgrade_three_equal_categories', len(choices)==3 and [c['id'] for c in choices]==list(UPGRADE_IDS), [c['id'] for c in choices])
    check('upgrade_slots_123', [c['slot'] for c in choices]==[1,2,3])
    base=upgrade_effects({})
    weapon=upgrade_effects({'VOLT_LATTICE':2})
    shell=upgrade_effects({'REACTIVE_SHELL':2})
    phase=upgrade_effects({'PHASE_RECOVERY':2})
    check('weapon_upgrade_effect', weapon['weapon_damage_mult'] > base['weapon_damage_mult'])
    check('shell_upgrade_effect', shell['max_armor'] > base['max_armor'] and shell['incoming_damage_mult'] < base['incoming_damage_mult'])
    check('phase_upgrade_effect', phase['hazard_damage_mult'] < base['hazard_damage_mult'] and phase['repulsor_cooldown_mult'] < base['repulsor_cooldown_mult'])
    mutations=[arena_mutation_for_set(i) for i in range(1,14)]
    check('set1_stable', mutations[0]['id']=='STABLE_MATRIX')
    check('mutation_families_cycle', {m['id'] for m in mutations[1:]}.issuperset({'GATE_OVERCLOCK','PHASE_FRACTURE','REDLINE_GRID','BREACH_RESONANCE'}))
    check('mutation_telegraph_floor', all(float(m['telegraph_mult']) >= .78 for m in mutations))

    # Pass 06 arena-family / size progression.
    arena_validation=validate_profiles()
    arena_samples=[arena_profile_for_set(i) for i in range(1,31)]
    arena_radii=[a['radius'] for a in arena_samples]
    check('arena_family_count_5', len(ARENA_FAMILIES)==5, len(ARENA_FAMILIES))
    check('arena_wire_palettes_distinct', len({tuple(a['wire_primary'][:3]) for a in ARENA_FAMILIES})==5)
    check('arena_radius_starts_118', arena_radii[0]==BASE_ARENA_RADIUS, arena_radii[0])
    check('arena_radius_nondecreasing', all(a<=b for a,b in zip(arena_radii,arena_radii[1:])), arena_radii[:8])
    check('arena_radius_max_228', max(arena_radii)==MAX_ARENA_RADIUS and all(r<=MAX_ARENA_RADIUS for r in arena_radii), max(arena_radii))
    check('arena_becomes_much_larger', arena_profile_for_set(5)['area_ratio'] >= 3.0, round(arena_profile_for_set(5)['area_ratio'],3))
    check('arena_set6_max_size', arena_profile_for_set(6)['radius']==MAX_ARENA_RADIUS, arena_profile_for_set(6)['radius'])
    # Pass 07 strategic architecture contracts across 30 sets, including all
    # five families at both early and maximum arena sizes.
    architecture_reports=[validate_architecture(a) for a in arena_samples]
    check('pass07_architecture_names_distinct', len({a['architecture'] for a in ARENA_FAMILIES})==5, [a['architecture'] for a in ARENA_FAMILIES])
    check('pass07_architecture_piece_counts_bounded', all(8 <= r['piece_count'] <= 12 for r in architecture_reports), sorted({r['piece_count'] for r in architecture_reports}))
    check('pass07_no_architecture_overlap', all(not r['overlaps'] for r in architecture_reports), [r for r in architecture_reports if r['overlaps']][:2])
    check('pass07_center_spawn_clearance', all(not r['center_conflicts'] for r in architecture_reports), [r for r in architecture_reports if r['center_conflicts']][:2])
    check('pass07_spawn_gate_clearance', all(not r['gate_conflicts'] for r in architecture_reports), [r for r in architecture_reports if r['gate_conflicts']][:2])
    check('pass07_no_boundary_blockers', all(not r['boundary_conflicts'] for r in architecture_reports), [r for r in architecture_reports if r['boundary_conflicts']][:2])
    check('pass07_breach_points_not_blocked', all(not r['objective_conflicts'] for r in architecture_reports), [r for r in architecture_reports if r['objective_conflicts']][:2])
    check('pass07_hazard_points_not_blocked', all(not r['hazard_conflicts'] for r in architecture_reports), [r for r in architecture_reports if r['hazard_conflicts']][:2])
    check('pass07_all_targets_reachable', all(r['routes_reachable'] for r in architecture_reports), [r for r in architecture_reports if not r['routes_reachable']][:2])
    check('pass07_no_unreachable_targets', all(not r['unreachable_targets'] for r in architecture_reports), [r['unreachable_targets'] for r in architecture_reports if r['unreachable_targets']][:2])
    check('pass07_navigation_cells_nonzero', all(r['reachable_cells'] > 500 for r in architecture_reports), min(r['reachable_cells'] for r in architecture_reports))
    check('arena_spawn_points_inside_boundary', all((x*x+y*y)**0.5 < a['radius']-16 for a in arena_samples[:10] for x,y in spawn_points_for_profile(a)))
    check('arena_hazards_inside_boundary', all((x*x+y*y)**0.5 < a['radius']-20 for a in arena_samples[:10] for x,y in hazard_points_for_profile(a)))
    check('arena_breaches_inside_weaponable_space', all((x*x+y*y)**0.5 < a['radius']*.80 for a in arena_samples[:10] for x,y in breach_points_for_profile(a)))
    check('pass07_profile_validator_clear', bool(arena_validation.get('architecture_all_clear')), arena_validation)
    # Hitscan authority is the same authored architecture, so cover that looks solid
    # blocks fire and open vertical space remains unblocked.
    hit_contract=[]
    for a in arena_samples[:5]:
        piece=architecture_pieces_for_profile(a)[0]
        blocked=first_architecture_hit(a,(0.0,0.0,4.4),(piece['x'],piece['y'],4.4))
        clear=first_architecture_hit(a,(0.0,0.0,4.4),(0.0,0.0,80.0))
        hit_contract.append((a['id'],bool(blocked),clear is None))
    check('pass07_solid_cover_blocks_hitscan', all(x[1] for x in hit_contract), hit_contract)
    check('pass07_open_space_not_falsely_blocked', all(x[2] for x in hit_contract), hit_contract)

    # Pass 05 evolution pacing/readability.
    variants=('stalker','sentry','wraith','brute','guardian')
    base_evos={v:enemy_evolution_for(v,1) for v in variants}
    check('evolution_set1_baseline', all(e['level']==0 for e in base_evos.values()), base_evos)
    late=[apply_enemy_progression(v,20,'GUARDIAN' if v=='guardian' else 'ELITE') for v in variants]
    check('evolution_level_bounded', all(0 <= e['level'] <= EVOLUTION_MAX_LEVEL for e in late), [e['level'] for e in late])
    check('evolution_hp_bounded', all(1.0 <= e['hp_mult'] <= 1.46 for e in late), [round(e['hp_mult'],3) for e in late])
    check('evolution_speed_bounded', all(1.0 <= e['speed_mult'] <= 1.24 for e in late), [round(e['speed_mult'],3) for e in late])
    check('evolution_damage_bounded', all(1.0 <= e['damage_mult'] <= 1.24 for e in late), [round(e['damage_mult'],3) for e in late])
    check('evolution_attack_cooldown_floor', all(e['attack_cooldown_mult'] >= 0.78 for e in late), [round(e['attack_cooldown_mult'],3) for e in late])
    doctrines=[encounter_doctrine_for(k,4) for k in ('ASSAULT','HORDE','BREACH','ELITE','OVERLOAD','BLACKOUT','GUARDIAN')]
    check('doctrines_named_all_wave_types', all(d['active'] and d['name'] for d in doctrines), [d['name'] for d in doctrines])
    check('doctrine_no_population_override', all('active_bonus' not in d and 'spawn_count' not in d for d in doctrines))
    phases=[guardian_phase_profile(i) for i in (1,2,3)]
    check('guardian_three_phases', [p['name'] for p in phases]==['SENTINEL','OVERDRIVE','REDLINE'], [p['name'] for p in phases])
    check('guardian_phase_thresholds', guardian_phase_for(100,100)==1 and guardian_phase_for(60,100)==2 and guardian_phase_for(20,100)==3)
    check('guardian_telegraph_floor', all(p['telegraph_mult'] >= 0.82 for p in phases), [p['telegraph_mult'] for p in phases])
    check('guardian_damage_mult_bounded', all(p['damage_mult'] <= 1.14 for p in phases), [p['damage_mult'] for p in phases])
    pool_capacity={'stalker':12,'wraith':6,'sentry':6,'brute':5,'guardian':3}
    deadlocks=[]
    for w in range(1,201):
        plan=apply_mutation_to_plan(build_wave_plan(w),(w-1)//5+1,MAX_ACTIVE_THREATS)
        queue=list(plan['queue']); active={k:0 for k in pool_capacity}; safety=0
        while queue or any(active.values()):
            safety += 1
            if safety > 10000:
                deadlocks.append((w,'safety')); break
            spawned=False
            while sum(active.values()) < plan['max_active'] and queue:
                pick=None
                for qi,var in enumerate(queue):
                    if active[var] < pool_capacity[var]: pick=qi; break
                if pick is None: break
                var=queue.pop(pick); active[var]+=1; spawned=True
            if any(active.values()):
                var=max(active, key=lambda k: active[k]); active[var]-=1
            elif queue and not spawned:
                deadlocks.append((w,'no_spawn_slot')); break
    check('pooled_feed_no_deadlock_200_waves', not deadlocks, deadlocks[:5])
except Exception as e:
    check('director_progression_import', False, e)

# Common issue / package hygiene checks.
residue=[p for p in ROOT.rglob('*') if p.is_file() and (p.suffix in {'.pyc','.log','.tmp'} or '__pycache__' in p.parts)]
check('package_residue_zero', not residue, [str(p.relative_to(ROOT)) for p in residue])
check('no_absolute_windows_paths', 'C:\\' not in adapter and 'D:\\' not in adapter)
check('readme_pass07_title', 'Pass 07' in (ROOT/'README.md').read_text(encoding='utf-8').splitlines()[0])

passed=sum(1 for _,ok,_ in checks if ok); total=len(checks)
out={'schema':'vector_arena_strategic_architecture_pass07_validation_v1','passed':passed,'total':total,'failed':[n for n,ok,_ in checks if not ok]}
ver=ROOT/'verification'; ver.mkdir(exist_ok=True)
(ver/'validation.json').write_text(json.dumps(out,indent=2)+'\n')
(ver/'validation.txt').write_text(f'Vector Arena Strategic Arena Architecture Pass 07\n{passed}/{total} PASS\nFAILED={out["failed"]}\n',encoding='utf-8')
print(f'RESULT {passed}/{total}')
raise SystemExit(0 if passed==total else 1)

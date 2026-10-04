from __future__ import annotations
import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
checks = []

def check(name, cond, detail=""):
    checks.append((name, bool(cond), detail))

for path in ROOT.rglob("*.py"):
    if "__pycache__" in path.parts:
        continue
    try:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        check(f"syntax:{path.relative_to(ROOT)}", True)
    except SyntaxError as exc:
        check(f"syntax:{path.relative_to(ROOT)}", False, str(exc))

required = [
    "main.py", "requirements.txt", "README.md", "RUN_ANDREWS_NIGHTMARE.bat",
    "game/app.py", "game/world.py", "game/player.py", "game/dreamer.py", "game/vision.py", "game/ui.py", "game/audio.py",
    "PASS17_PLAN.md", "PASS17_REPORT.md", "assets/audio/README.txt", "assets/models/sleeper_continuous.bam",
]
for rel in required:
    check(f"required:{rel}", (ROOT / rel).exists())

variant_dir = ROOT / "assets" / "textures" / "dream_variants"
variants = sorted(variant_dir.glob("*.png")) if variant_dir.exists() else []
check("dream_variant_directory", variant_dir.is_dir(), str(variant_dir))
check("dream_variant_count", len(variants) == 26, len(variants))

main = (ROOT / "main.py").read_text(encoding="utf-8")
app = (ROOT / "game/app.py").read_text(encoding="utf-8")
world = (ROOT / "game/world.py").read_text(encoding="utf-8")
vision = (ROOT / "game/vision.py").read_text(encoding="utf-8")
dreamer = (ROOT / "game/dreamer.py").read_text(encoding="utf-8")
ui = (ROOT / "game/ui.py").read_text(encoding="utf-8")
readme = (ROOT / "README.md").read_text(encoding="utf-8")

check("pass17_identity_main", "Pass 17" in main and "Ceiling Loop" in main)
check("pass17_identity_window", "Pass 17 Ceiling Loop" in app)
check("release_qa_scenes", all(tok in main for tok in ['"dreamer-recovered"', '"release-mosh"', '"released"']))
check("release_qa_driver", "_prepare_qa_release_mosh" in app and '"release-mosh"' in app)

# Pass 11 Continuity Errors contract.
check("return_zone", '"return": ZoneStyle' in world and 'self._paint_rect(-13, -6, 3, 6, "return")' in world)
check("return_real_recess", 'self._paint_rect(-17, -14, 4, 5, "return")' in world and 'return-false-exit' in world)
check("return_false_exit_back_wall", '(-18, 4) not in self.world.walkable' in app)
check("return_memory_bracket", 'return-memory-bracket' in world and 'return_memory_shifted' in world)
check("return_memory_only_unseen", 'observed = dot > math.cos(math.radians(52.0))' in world and 'not self._return_memory_shifted and not observed' in world)
check("return_memory_no_collision_authority", 'return-memory-v-a' in world and 'CollisionBox' in world)
check("return_anomaly_qa_scenes", all(tok in main for tok in ['"return-room"', '"return-near"', '"return-memory-a"', '"return-memory-b"']))
check("return_anomaly_runtime_task", 'self.world.update_anomalies(pos.x, pos.y, time_s, self.player.heading)' in app)

# Pass 10 Dream Anomalies contract.
check("unlit_zone", '"unlit": ZoneStyle' in world and 'self._paint_rect(3, 8, -15, -8, "unlit")' in world)
check("echo_zone", '"echo": ZoneStyle' in world and 'self._paint_rect(-9, -5, 18, 23, "echo")' in world)
check("witness_zone", '"witness": ZoneStyle' in world and 'self._paint_rect(-10, -6, -9, -6, "witness")' in world)
check("anomaly_update_task", "_update_world_anomalies" in app and '"dream-anomalies"' in app)
check("lightless_afterglow", "_unlit_afterglow" in world and "lightless_afterglow_lags_player" in app)
check("echo_memory_bleed", "_echo_bleed_nodes" in world and "echo_memory_resolves_on_approach" in app)
check("witness_scaffold", "witness-scaffold" in world and "witness-floor-brace" in world and "witness-wall-tether" in world)
check("cycle_anomaly_variation", "_anomaly_signature" in world and "witness_shifts_between_cycles" in app)
check("anomaly_qa_scenes", all(tok in main for tok in ['"lightless-room"', '"echo-room"', '"witness-alcove"']))

# Pass 09 Uneven Dreamspace contract.
check("depth_texture_capture", "depthtex=self.depth_tex" in vision and "depth_tex" in vision)
check("depth_linearization", "linear_depth_m" in vision and "u_near" in vision and "u_far" in vision)
check("distance_blur_shader", "distance_blur" in vision and "blur_start" in vision and "blur_end" in vision)
check("focus_assist_shader", "u_focus_assist" in vision and "set_focus_assist" in vision)
check("authored_darkness", "darkness_at" in world and "u_darkness" in vision)
check("falsehall_zone", '"falsehall": ZoneStyle' in world and 'self._paint_rect(19, 36, 5, 6, "falsehall")' in world)
check("falsehall_room", '"focus": ZoneStyle' in world and 'self._paint_rect(37, 42, 2, 9, "focus")' in world)
check("falsehall_lens", "dream_lens_fov_offset" in world and "_update_dream_lens" in app)
check("falsehall_real_opening", "falsehall-far-threshold" in world)
check("hidden_glasses", "forgotten-glasses" in world and "glasses_near" in world and "collect_glasses" in world)
check("hidden_glasses_optional", "FOCUS // CORRECTED" in app and "E // WEAR" in app)
check("new_qa_scenes", all(tok in main for tok in ['"false-hall"', '"dark-room"', '"glasses"', '"glasses-on"']))

# Pass 12 Intercepted Instances contract.
audio = (ROOT / "game/audio.py").read_text(encoding="utf-8")
check("sleeper_user_language", "SLEEPER // RECONSTRUCTING" in app and "SLEEPER // GONE" in app)
check("false_sleeper_authored_roots", "_false_sleeper_roots" in world and "false-sleeper" in world)
check("false_sleeper_seed_subset", "indices[:2 +" in world and "_false_sleeper_profile_indices" in world)
check("gleebs_trace_unidentified", "intercept-shadow-trace" in world and "trace-ear-l" in world and "trace-eye" in world)
check("gleebs_trace_lookaway_rule", "_gleebs_trace_seen" in world and "_gleebs_trace_vanished" in world and "self._gleebs_trace_root.hide()" in world)
check("memory_seam_zone", '"seam": ZoneStyle' in world and 'self._paint_rect(3, 4, -3, -2, "seam")' in world)
check("memory_seam_reveal", "def _reveal_memory_seam" in world and "_memory_seam_revealed" in world)
check("memory_seam_real_shortcut", 'self._paint_rect(5, 6, -8, -6, "seam")' in world)
check("instance_profile_signature", "_instance_signature" in world and "_apply_instance_variant" in world)
check("curated_glasses_anchors", "_glasses_anchors" in world and "_set_glasses_anchor_for_cycle" in world)
check("null_layer_world", "def enter_null_layer" in world and "null_exit_near" in world and "complete_null_exit" in world)
check("null_layer_vision_bypass", "u_null_layer" in vision and "set_null_layer" in vision)
check("null_layer_hides_sleeper", "def enter_null_layer" in dreamer and "null_layer_hidden" in dreamer)
check("null_layer_prompt", "E // DISCONNECT" in app)
check("automatic_instance_collapse", "_start_instance_collapse" in app and "_perform_instance_collapse" in app and "_finish_instance_collapse" in app)
check("automatic_collapse_hides_sleeper", "self.dreamer.release()" in app and "self.world.instance_complete = True" in app)
check("no_manual_release_prompt", "E // RELEASE DREAMER" not in app)
check("audio_owner", "class NightmareAudio" in audio and "self.music_dir" in audio)
check("audio_track_scan", 'self.music_dir' in audio and 'self.sfx_dir' in audio)
check("datamosh_audio_sag", "setPlayRate" in audio and "begin_datamosh" in audio and "finish_datamosh" in audio)
check("null_layer_stops_music", "def enter_null_layer" in audio and "self.stop_current()" in audio)
check("pass12_qa_scenes", all(tok in main for tok in ['"false-sleeper"', '"gleebs-trace"', '"memory-seam"', '"null-layer"', '"null-exit"', '"instance-collapse"']))


# Pass 14 generated-audio contract.
music_dir = ROOT / "assets" / "audio" / "music"
sfx_dir = ROOT / "assets" / "audio" / "sfx"
music_files = sorted(music_dir.glob("*.wav"))
sfx_files = sorted(sfx_dir.glob("*.wav"))
check("pass14_music_count", len(music_files) == 6, len(music_files))
check("pass16_sfx_count", len(sfx_files) == 11, len(sfx_files))
check("pass14_native_wav_loops", all(p.suffix.lower() == ".wav" for p in music_files), len(music_files))
check("pass14_null_layer_cue", 'play_sfx("null_layer"' in app and 'self.audio.enter_null_layer()' in app)
check("pass14_gleebs_audio_event", 'event == "gleebs_trace"' in app and 'events.append("gleebs_trace")' in world)
check("pass14_memory_audio_event", 'event == "memory_shift"' in app and 'events.append("memory_shift")' in world)
check("pass14_false_sleeper_audio", 'false_sleeper_resolve' in app and 'false_sleeper_count' in world)
check("pass14_recovery_audio", 'room_recovered' in app and 'relay_online' in app)
check("pass14_collapse_no_double_disturb", 'begin_datamosh(play_disturb_sfx=False)' in app)
check("pass14_seeded_playlist_start", "playlist_seed=self.dream_seed" in app and "self._playlist_seed" in audio)

# Pass 13 Shifting Intercepts contract.
check("route_profiles_authored", "ROUTE_PROFILES" in world and world.count('("archive", "feedback", "dead", "buffer")') >= 1)
check("route_profile_seed_frozen", "route_profile_index" in world and "route_signature" in world and "^ 23" in world)
check("dynamic_node_targets", 'next_target = {"relay": self.route_zones[0]}' in world and "target_zone = next_target[zone]" in world)
check("dynamic_route_node_order", "route_node_order" in world and "self.world.route_node_order" in app)
check("route_not_changed_by_dream_cycle", "self.route_zones" in world and "route_frozen_across_dream_cycles" in app)
check("first_recovery_reveals_seam", "if self.stabilized_count == 1" in world and "_reveal_memory_seam()" in world)
check("false_sleepers_decay", "def _apply_destabilization_response" in world and "remaining = max(0, len(profile) - self.stabilized_count)" in world)
check("pass13_qa_scenes", all(tok in main for tok in ['"first-target"', '"false-sleeper-weakened"']))
check("all_route_profiles_tested", "all_six_route_profiles_seedable" in app and "route_profile_uses_all_core_rooms" in app)

# Pass 08 recovery mechanics remain as internal compatibility/QA authority, but
# the player-facing end condition is now automatic Pass 13 instance collapse.
check("dreamer_recovery_state", "recovery_progress" in dreamer and "set_recovery_progress" in dreamer)
check("dreamer_release_state", "self.released" in dreamer and "def release(" in dreamer)
check("dreamer_release_hides_live_entity", "self.root.hide()" in dreamer)
check("recovery_reduces_speed", "self._base_speed * (1.0 - 0.44 * p)" in dreamer)
check("recovery_pulls_ghosts_in", "pull = 1.0 - 0.82 * p" in dreamer)
check("world_recovery_fraction", "dreamer_recovery_fraction" in world and "self.route_complete" in world)
check("app_syncs_recovery", "_sync_dreamer_recovery" in app and "dreamer_recovery_fraction" in app)
check("no_permanent_release_hud", "objective" not in ui.lower())

# Existing route authority remains, but target order is now one of six authored profiles.
check("route_profiles_cover_core_rooms", "ROUTE_PROFILES" in world and '"buffer"' in world)
check("route_completion", 'if zone == "buffer"' in world and "self.route_complete = True" in world)
check("target_room_visual_override", "_apply_stabilized_zone_overrides" in world)
check("world_arrival_task", "_update_route_progress" in app and "linked-stability-route" in app)

# Existing gameplay and visual authorities must remain.
check("vision_temporal_feedback", "FEEDBACK_FRAG_SHADER" in vision and "history_tex" in vision and "feedback_buffer" in vision)
check("dreamer_observation_preserved", "is_observed_by_player" in dreamer and "simulate_step" in dreamer)
check("dream_cycle_preserved", "advance_dream_cycle" in world and "dream_variants" in world)
check("branch_archive_preserved", 'self._paint_rect(-10, -6, -3, 2, "archive")' in world)
check("branch_feedback_preserved", 'self._paint_rect(14, 18, 3, 8, "feedback")' in world)
check("branch_dead_preserved", 'self._paint_rect(-18, -14, 9, 14, "dead")' in world)
check("collision_authority_preserved", "can_stand" in world and "CollisionBox" in world)
check("respawn_cycle_preserved", "self.world.advance_dream_cycle()" in app and "_perform_datamosh_relocation" in app)

# Pass 15 Visual Foundation Recovery contract.
model_path = ROOT / "assets" / "models" / "sleeper_continuous.bam"
check("pass15_sleeper_model_present", model_path.is_file() and model_path.stat().st_size > 100000, model_path.stat().st_size if model_path.exists() else 0)
check("pass15_sleeper_single_surface", "sleeper_continuous.bam" in dreamer and "_make_box_geom" not in dreamer and "_box_part" not in dreamer)
check("pass15_sleeper_no_primitive_anatomy", all(tok not in dreamer for tok in ['add("head"', 'add("torso"', 'add("pelvis"', 'add("arm_l"']))
check("pass15_sleeper_whole_body_echoes_only", "sleeper-registration-" in dreamer and "_signal_tears" not in dreamer and "_parts" not in dreamer)
check("pass15_depth_blur_strength", "blur_start = 3.6" in vision and "blur_end = 11.2" in vision and "16.0" in vision)
check("pass15_focus_drift", "sin(u_time * 0.29)" in vision and "sin(u_time * 0.113" in vision)
check("pass15_no_event_posterization", "floor(color * levels)" not in vision)
check("pass15_predictive_motion_frozen", "_event_motion" in vision and "_recent_motion" in vision and "predictive_motion" in vision)
check("pass15_teleport_not_camera_motion", "travel > 1.45" in vision and "return" in vision)
check("pass15_mild_pre_switch_corruption", "self.event = 0.34 * math.sin" in vision)
check("pass15_falsehall_stronger_lens", "offset = -18.0 + 36.0 * smooth" in world)
check("pass15_side_qa_scene", '"sleeper-side"' in main and '"sleeper-side"' in app)
check("pass15_focus_matched_qa", '"vision-blur"' in main and '"vision-clear"' in main and 'set_focus_assist(1.0)' in app)
check("pass15_mosh_sequence_tool", (ROOT / "tools" / "capture_mosh_sequence.py").exists())

# Pass 16 Visitor Resonance contract.
check("pass16_resonance_task", "_update_sleeper_resonance" in app and '"sleeper-resonance"' in app)
check("pass16_safe_observation_band", "2.45 <= distance <= 7.25" in app and "dt / 1.45" in app)
check("pass16_once_per_recovery_stage", "_resonance_triggered_stage" in app and "stage != self._resonance_triggered_stage" in app)
check("pass16_world_only_reward", "set_resonance_view" in world and "current_route_target" in world)
check("pass16_false_sleepers_suppressed", "for root in self._false_sleeper_roots" in world and "root.hide()" in world)
check("pass16_focus_reward", "self.vision.set_focus_assist(0.74)" in app)
check("pass16_continuous_sleeper_signal", "set_resonance_strength" in dreamer and "resonance_strength" in dreamer)
check("pass16_audio_cue", 'play_sfx("sleeper_resonance"' in app and (sfx_dir / "sleeper_resonance.wav").exists())
check("pass16_qa_scenes", all(tok in main for tok in ['"resonance-charge"', '"resonance-read"', '"resonance-target-read"']))

# Pass 17 Ceiling Loop contract.
check("pass17_shared_ceiling_authority", "self.ceiling_height = WALL_HEIGHT" in world and 'getattr(self.world, "ceiling_height"' in dreamer)
check("pass17_vertical_wrap_state", "ceiling_loop_state" in dreamer and "ceiling_loop_progress" in dreamer and "_update_ceiling_loop" in dreamer)
check("pass17_same_continuous_visual_instance", "instanceTo(self._ceiling_holder)" in dreamer and "sleeper-ceiling-holder" in dreamer)
check("pass17_close_observation_band", "_ceiling_trigger_min = 1.10" in dreamer and "_ceiling_trigger_max = 2.32" in dreamer and 'self.dreamer.ceiling_loop_state == "idle"' in app)
check("pass17_floor_contact_contract", "not self.ceiling_passage_open" in dreamer and "ceiling_passage_open" in dreamer)
check("pass17_safe_return", "distance < 2.38" in dreamer and 'self.ceiling_loop_state = "holding"' in dreamer)
check("pass17_qa_scenes", all(tok in main for tok in ['"sleeper-sink"', '"sleeper-ceiling"', '"sleeper-under"']))
check("pass17_regression_tests", "pass17_ceiling_loop_triggers_from_close_gaze" in app and "pass17_floor_contact_safe_only_when_tucked" in app)

for token in [
    "WASD", "SHIFT", "SPACE", "CTRL", "ESC", "F11",
    "six authored route orders", "Deep Buffer",
    "Sleepers and false Sleepers", "Memory seam", "Null Layer",
    "temporal", "Distance", "False-near", "Lightless Gallery",
    "Echo Room", "Witness Alcove", "Return Room", "assets/audio/music",
    "Visitor Resonance", "Ceiling Loop", "sleeper_continuous.bam",
]:
    check(f"readme_contract:{token}", token in readme)

summary = {
    "pass": all(ok for _, ok, _ in checks),
    "checks": len(checks),
    "failures": [n for n, ok, _ in checks if not ok],
}
print(json.dumps(summary, indent=2))
for name, ok, detail in checks:
    print(("PASS" if ok else "FAIL"), name, detail)
sys.exit(0 if summary["pass"] else 1)

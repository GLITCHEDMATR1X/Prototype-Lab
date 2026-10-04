from __future__ import annotations

import json
import math
import random
from pathlib import Path

from direct.showbase.ShowBase import ShowBase
from panda3d.core import AntialiasAttrib, ClockObject, Fog, Filename, Point3, WindowProperties

from gx_common import shared
from gx_common.travel import WorldTravel
from .audio import NightmareAudio
from .dreamer import DreamerController
from .player import FirstPersonController
from .settings import DEFAULTS as SETTINGS_DEFAULTS, load_settings, save_settings
from .ui import NightmareUI
from .vision import NightmareVision
from .world import NightmareWorld


class AndrewsNightmareApp(ShowBase):
    def __init__(self, args, project_root: Path):
        super().__init__(windowType="offscreen" if args.offscreen else None)
        self.args = args
        self.world_travel = None
        self.project_root = project_root
        self.settings = load_settings()
        # Mirror's Limbo owns mouse feel, FOV preference, display mode and volume.
        # Deterministic QA/self-test runs keep Andrew's own fixed values.
        self._shared_settings = None
        if not (args.offscreen or args.qa_shot or args.self_test or args.smoke_test):
            self._shared_settings = shared.load_settings()
            if self._shared_settings["present"]:
                self.settings["mouse_sensitivity"] = self._shared_settings["mouse_sensitivity"]
                self.settings["invert_y"] = self._shared_settings["invert_y"]
                self.settings["fov"] = shared.world_fov(SETTINGS_DEFAULTS["fov"], self._shared_settings["fov"], 70.0, 105.0)
                self.settings["borderless"] = self._shared_settings["display_mode"] != "windowed"
        if args.windowed:
            self.settings["borderless"] = False
        self.disableMouse()
        self.render.setAntialias(AntialiasAttrib.MAuto)
        self.setBackgroundColor(0.008, 0.005, 0.012, 1)
        self._setup_window()
        if getattr(args, "dream_seed", None) is not None:
            self.dream_seed = int(args.dream_seed)
        elif args.offscreen or args.qa_shot or args.self_test or args.smoke_test:
            self.dream_seed = 6060
        else:
            self.dream_seed = random.SystemRandom().randrange(1, 2**31 - 1)
        self.world = NightmareWorld(self, project_root, dream_seed=self.dream_seed)
        spawn_pos, spawn_h = self.world.spawn
        self.player = FirstPersonController(
            self,
            self.world,
            spawn_pos,
            spawn_h,
            self.settings,
            input_enabled=not (args.offscreen or args.qa_shot or args.self_test),
        )
        self._relocation_index = 0
        self.dreamer = DreamerController(self, self.world, self.player, on_encounter=self._on_dreamer_encounter)
        self.vision = NightmareVision(self, self.world, self.player)
        self.ui = NightmareUI(self)
        self.audio = NightmareAudio(self, project_root, enabled=not bool(getattr(args, "no_audio", False)), playlist_seed=self.dream_seed)
        if self._shared_settings is not None and not getattr(args, "no_audio", False):
            shared.apply_master_volume(self, self._shared_settings["master_volume"])
        self._completion_recorded = False
        self.audio.start_instance(self.world.dream_cycle)
        self.paused = False
        self._dreamer_release_in_progress = False
        self._instance_collapse_in_progress = False
        self._interaction_flash_until = 0.0
        self._last_route_zone = None
        self.taskMgr.add(self._update_route_progress, "linked-stability-route", sort=50)
        self.taskMgr.add(self._update_interaction_prompt, "interaction-prompt", sort=52)
        self._lens_offset = 0.0
        self.taskMgr.add(self._update_dream_lens, "dream-lens", sort=44)
        self.taskMgr.add(self._update_world_anomalies, "dream-anomalies", sort=46)
        self._resonance_charge = 0.0
        self._resonance_triggered_stage = -1
        self._resonance_active_until = 0.0
        self._resonance_focus = 0.0
        self.taskMgr.add(self._update_sleeper_resonance, "sleeper-resonance", sort=47)
        self._setup_fog()
        self._bind_app_controls()
        self._window_state = self.settings["borderless"]
        self.accept("window-event", self._window_event)

        if args.qa_shot:
            self._configure_qa_view(args.qa_scene)
            self._qa_frame = 0
            self._qa_mosh_prepared = False
            self.taskMgr.add(self._qa_frame_driver, "qa-frame-driver", sort=90)
        if args.smoke_test:
            self.taskMgr.doMethodLater(1.2, self._finish_smoke, "smoke-finish")
        if args.self_test:
            self._start_self_test()

        self.world_travel = WorldTravel(self, project_root, 'andrews_nightmare',
            before_leave=self._travel_before_leave, on_error=self._travel_failed,
            activate=self._travel_activate)
        self.world_travel.start_receiving()

    def _travel_before_leave(self):
        save_settings(self.settings)
        self.player.set_paused(True)

    def _save_settings(self):
        """Save Andrew's own file and push the shared keys back to Mirror's Limbo."""
        save_settings(self.settings)
        if self._shared_settings is not None:
            shared.update_settings(
                mouse_sensitivity=self.settings["mouse_sensitivity"],
                fov=shared.limbo_fov_from_world(self.settings["fov"], SETTINGS_DEFAULTS["fov"]),
                display_mode="borderless" if self.settings["borderless"] else "windowed",
            )

    def _record_completion(self, ending):
        if self._completion_recorded or self.args.self_test or self.args.qa_shot:
            return
        self._completion_recorded = True
        shared.record_completion("andrews_nightmare", ending)

    def _travel_failed(self, message):
        print('GX_TRAVEL ' + message, flush=True)
        self.paused = True
        self.player.set_paused(True); self.dreamer.set_paused(True); self.ui.set_paused(True)
        self.ui.set_status('DREAMCATCHER UNAVAILABLE — NIGHTMARE RESTORED')

    def _travel_activate(self):
        self.paused = False
        self.player.set_paused(False); self.dreamer.set_paused(False); self.ui.set_paused(False)

    def userExit(self):
        if getattr(self, 'world_travel', None):
            self.world_travel.close()
        if getattr(self, 'audio', None):
            self.audio.stop_current()
        super().userExit()

    def return_to_dreamcatcher(self):
        """Wake in DreamCatcher. Allowed from pause, or any time once the instance is complete."""
        if not (self.paused or self.world.instance_complete):
            return False
        if self.world_travel and not self.world_travel.busy:
            return self.world_travel.go('dreamcatcher_alternate', returning=True)
        return False

    def _setup_window(self):
        if not self.win:
            return
        props = WindowProperties()
        props.setTitle("Andrew's Nightmare")
        if self.args.offscreen or self.args.qa_shot or self.args.self_test:
            return
        if self.settings["borderless"]:
            dw = self.pipe.getDisplayWidth() or 1920
            dh = self.pipe.getDisplayHeight() or 1080
            props.setSize(dw, dh)
            props.setOrigin(0, 0)
            props.setUndecorated(True)
            props.setFullscreen(False)
        else:
            props.setSize(1280, 720)
            props.setUndecorated(False)
            props.setFullscreen(False)
        self.win.requestProperties(props)

    def _update_dream_lens(self, task):
        # The player's configured FOV remains authority everywhere except the
        # authored false-near corridor.  Smoothing prevents a visible camera snap
        # at the threshold and preserves mouse/control behavior.
        pos = self.player.root.getPos(self.render)
        target = float(self.world.dream_lens_fov_offset(pos.x, pos.y))
        dt = min(ClockObject.getGlobalClock().getDt(), 0.05)
        blend = min(1.0, dt * 4.5)
        self._lens_offset += (target - self._lens_offset) * blend
        effective = max(58.0, min(112.0, float(self.settings["fov"]) + self._lens_offset))
        self.camLens.setFov(effective)
        return task.cont

    def _update_world_anomalies(self, task):
        pos = self.player.root.getPos(self.render)
        if self.args.qa_shot:
            time_s = 4.0
        else:
            time_s = ClockObject.getGlobalClock().getFrameTime()
        events = self.world.update_anomalies(pos.x, pos.y, time_s, self.player.heading) or ()
        for event in events:
            if event == "gleebs_trace":
                self.audio.play_sfx("gleebs_trace", volume=0.48)
            elif event == "memory_shift":
                self.audio.play_sfx("memory_seam", volume=0.34)
        return task.cont

    def _update_sleeper_resonance(self, task):
        """Risk/reward gaze mechanic: read the Sleeper without touching them.

        Holding the real Sleeper in view from an uncomfortable but safe distance
        briefly clears Andrew's eyesight, suppresses false Sleepers, and strengthens
        the current in-world route clue.  There is no meter and no topology change.
        The reward can trigger once for each recovery stage.
        """
        if self.args.self_test or (self.args.qa_shot and self.args.qa_scene not in ("resonance-charge", "resonance-read")):
            return task.cont
        if self.args.qa_shot and self.args.qa_scene == "resonance-charge":
            self.world.set_resonance_view(False)
            self.vision.set_focus_assist(0.17)
            self.dreamer.set_resonance_strength(0.72)
            return task.cont
        if self.args.qa_shot and self.args.qa_scene == "resonance-read":
            self.world.set_resonance_view(True)
            self.world.update_resonance_pulse(2.4)
            self.vision.set_focus_assist(0.74)
            self.dreamer.set_resonance_strength(1.0)
            return task.cont
        if self.world.null_layer or self.dreamer.released or self._instance_collapse_in_progress:
            self._resonance_charge = 0.0
            self._resonance_focus = 0.0
            self.world.set_resonance_view(False)
            self.dreamer.set_resonance_strength(0.0)
            return task.cont
        if self.vision.active:
            self._resonance_charge = 0.0
            self._resonance_active_until = 0.0
            self._resonance_focus = 0.0
            self.world.set_resonance_view(False)
            self.dreamer.set_resonance_strength(0.0)
            self.vision.set_focus_assist(0.0)
            return task.cont

        now = ClockObject.getGlobalClock().getFrameTime()
        dt = min(ClockObject.getGlobalClock().getDt(), 0.05)
        if now < self._resonance_active_until:
            self._resonance_focus += (0.74 - self._resonance_focus) * min(1.0, dt * 7.0)
            self.vision.set_focus_assist(self._resonance_focus)
            self.dreamer.set_resonance_strength(1.0)
            self.world.set_resonance_view(True)
            self.world.update_resonance_pulse(now)
            return task.cont

        if self._resonance_active_until > 0.0:
            self._resonance_active_until = 0.0
            self.world.set_resonance_view(False)

        stage = self.world.stabilized_count
        can_trigger = stage != self._resonance_triggered_stage and not self.world.route_complete
        observed = bool(self.dreamer.observed)
        distance = self.dreamer.distance_to_player()
        in_band = 2.45 <= distance <= 7.25
        valid = (
            can_trigger
            and observed
            and in_band
            and self.dreamer.ceiling_loop_state == "idle"
            and not self.paused
            and not self.vision.active
            and not self.player.control_locked
        )

        if valid:
            self._resonance_charge = min(1.0, self._resonance_charge + dt / 1.45)
        else:
            self._resonance_charge = max(0.0, self._resonance_charge - dt / 0.42)

        # Charging itself gives only a restrained optical response.  The full read
        # state is the reward, so normal gameplay does not become permanently sharp.
        target_focus = 0.24 * self._resonance_charge
        self._resonance_focus += (target_focus - self._resonance_focus) * min(1.0, dt * 8.5)
        self.vision.set_focus_assist(self._resonance_focus)
        self.dreamer.set_resonance_strength(self._resonance_charge)

        if self._resonance_charge >= 0.999 and can_trigger:
            self._resonance_triggered_stage = stage
            self._resonance_charge = 0.0
            self._resonance_active_until = now + 6.6
            target = self.world.set_resonance_view(True)
            self.audio.play_sfx("sleeper_resonance", volume=0.58)
            self.vision.set_focus_assist(0.74)
            self._resonance_focus = 0.74
            self.dreamer.set_resonance_strength(1.0)
            if target:
                self.ui.set_interaction("SLEEPER // SIGNAL OPEN")
                self._interaction_flash_until = now + 0.85
        return task.cont

    def _setup_fog(self):
        self._fog = Fog("dream-distance")
        self._fog.setLinearRange(23.0, 49.0)
        self.render.setFog(self._fog)
        self._apply_cycle_environment()

    def _apply_cycle_environment(self):
        fog, bg = self.world.cycle_environment_colors()
        if hasattr(self, "_fog"):
            self._fog.setColor(*fog)
        self.setBackgroundColor(bg[0], bg[1], bg[2], 1.0)

    def _bind_app_controls(self):
        self.accept("escape", self.toggle_pause)
        self.accept("enter", self._resume_from_enter)
        self.accept("f11", self.toggle_window_mode)
        self.accept("[", self.adjust_fov, [-2.0])
        self.accept("]", self.adjust_fov, [2.0])
        self.accept("-", self.adjust_mouse, [-0.01])
        self.accept("=", self.adjust_mouse, [0.01])
        self.accept("q", self.quit_if_paused)
        self.accept("e", self._try_stabilize)

    def _resume_from_enter(self):
        if self.paused:
            self.toggle_pause()

    def toggle_pause(self):
        if self.world_travel and self.world_travel.busy:
            return
        if self.args.qa_shot or self.args.self_test or self.vision.active:
            return
        self.paused = not self.paused
        self.player.set_paused(self.paused)
        self.dreamer.set_paused(self.paused)
        self.ui.set_paused(self.paused)
        self.ui.set_status(self._settings_status())

    def quit_if_paused(self):
        self.return_to_dreamcatcher()

    def _window_event(self, win):
        if not win or not hasattr(win, "getProperties") or self.args.qa_shot or self.args.self_test:
            return
        props = win.getProperties()
        if (props.getMinimized() or not props.getForeground()) and not self.paused:
            self.paused = True
            self.player.set_paused(True)
            self.dreamer.set_paused(True)
            self.ui.set_paused(True)
            self.ui.set_status(self._settings_status())

    def toggle_window_mode(self):
        if not self.win or self.args.qa_shot or self.args.self_test:
            return
        borderless = not self.settings["borderless"]
        self.settings["borderless"] = borderless
        props = WindowProperties()
        if borderless:
            dw = self.pipe.getDisplayWidth() or 1920
            dh = self.pipe.getDisplayHeight() or 1080
            props.setSize(dw, dh)
            props.setOrigin(0, 0)
            props.setUndecorated(True)
            props.setFullscreen(False)
        else:
            props.setSize(1280, 720)
            props.setUndecorated(False)
            props.setFullscreen(False)
        self.win.requestProperties(props)
        self._save_settings()
        self.ui.set_status(self._settings_status())

    def adjust_fov(self, delta):
        self.settings["fov"] = max(70.0, min(105.0, self.settings["fov"] + delta))
        self.camLens.setFov(self.settings["fov"])
        self._save_settings()
        self.ui.set_status(self._settings_status())

    def adjust_mouse(self, delta):
        lo, hi = shared.LIMBO_SENSITIVITY_RANGE
        self.settings["mouse_sensitivity"] = max(lo, min(hi, self.settings["mouse_sensitivity"] + delta))
        self._save_settings()
        self.ui.set_status(self._settings_status())

    def _settings_status(self):
        return f"FOV {self.settings['fov']:.0f}  //  MOUSE {self.settings['mouse_sensitivity']:.3f}"

    def _try_stabilize(self):
        if self.paused or self.vision.active or self.player.control_locked:
            return
        pos = self.player.root.getPos(self.render)

        if self.world.null_layer:
            if self.world.null_exit_near(pos.x, pos.y) and self.world.complete_null_exit():
                self.audio.play_sfx("null_exit")
                self.ui.set_interaction("CONNECTION // CLOSED")
                self._interaction_flash_until = ClockObject.getGlobalClock().getFrameTime() + 2.0
                # The true disconnect ends the nightmare: wake Andrew's host in DreamCatcher.
                self._record_completion("null_disconnect")
                self.player.set_control_locked(True)
                self.taskMgr.doMethodLater(2.6, self._wake_after_disconnect, "null-exit-wake")
            return

        if self.world.glasses_near(pos.x, pos.y):
            if self.world.collect_glasses():
                self.audio.play_sfx("null_layer", volume=0.72)
                self.world.enter_null_layer()
                self.vision.set_null_layer(True)
                self.dreamer.enter_null_layer()
                self.audio.enter_null_layer()
                self._apply_cycle_environment()
                self.ui.set_interaction("FOCUS // CORRECTED")
                self._interaction_flash_until = ClockObject.getGlobalClock().getFrameTime() + 1.15
            return

        node = self.world.nearest_stabilizer(pos.x, pos.y)
        if node is None:
            return
        if node.active:
            if node.target_zone in self.world.visited_stabilized_zones:
                text = f"{self.world.target_display_name(node.target_zone)} // LINK COMPLETE"
            else:
                text = f"{self.world.target_display_name(node.target_zone)} // STABLE — GO THERE"
            self.ui.set_interaction(text)
            self._interaction_flash_until = ClockObject.getGlobalClock().getFrameTime() + 1.0
            return
        if not node.unlocked:
            self.ui.set_interaction("STABILITY RELAY // NO CARRIER")
            self._interaction_flash_until = ClockObject.getGlobalClock().getFrameTime() + 0.8
            return
        false_before = self.world.false_sleeper_count
        seam_before = self.world.memory_seam_revealed
        activated = self.world.stabilize_nearest(pos.x, pos.y)
        if activated:
            self.audio.play_sfx("stabilizer")
            seam_revealed_now = (not seam_before and self.world.memory_seam_revealed)
            if seam_revealed_now:
                self.audio.play_sfx("memory_seam", volume=0.42)
            elif self.world.false_sleeper_count < false_before:
                # Avoid stacking three cues on the first recovery; later decoy
                # dissolves receive their own restrained signal.
                self.audio.play_sfx("false_sleeper_resolve", volume=0.32)
            self._sync_dreamer_recovery()
            target = self.world.target_display_name(activated.target_zone)
            self.ui.set_interaction(f"{target} // STABILIZED — INTERCEPT WEAKENED")
            self._interaction_flash_until = ClockObject.getGlobalClock().getFrameTime() + 1.35

    def _update_route_progress(self, task):
        if self.args.self_test or self.paused or self.vision.active:
            return task.cont
        pos = self.player.root.getPos(self.render)
        zone = self.world.zone_at(pos.x, pos.y)
        if zone != self._last_route_zone:
            self._last_route_zone = zone
            event = self.world.register_zone_visit(zone)
            if event:
                kind, node = event
                self._sync_dreamer_recovery()
                now = ClockObject.getGlobalClock().getFrameTime()
                if kind == "relay" and node is not None:
                    self.audio.play_sfx("room_recovered", volume=0.42)
                    self.audio.play_sfx("relay_online", volume=0.30)
                    name = self.world.target_display_name(zone)
                    next_name = self.world.target_display_name(node.target_zone)
                    self.ui.set_interaction(f"{name} // STABLE — RELAY TO {next_name} ONLINE")
                    self._interaction_flash_until = now + 1.45
                elif kind == "complete":
                    self.audio.play_sfx("room_recovered", volume=0.46)
                    self.ui.set_interaction("DEEP BUFFER // INTERCEPT DESTABILIZING")
                    self._interaction_flash_until = now + 1.9
        return task.cont

    def _wake_after_disconnect(self, task):
        if not self.return_to_dreamcatcher():
            # Travel failed: _travel_failed paused the game with a status line; give control back.
            self.player.set_control_locked(False)
        return task.done

    def _update_interaction_prompt(self, task):
        if (self.args.qa_shot and self.args.qa_scene not in ("interaction", "relay-link")) or self.args.self_test or self.paused or self.vision.active:
            self.ui.set_interaction(None)
            return task.cont
        now = ClockObject.getGlobalClock().getFrameTime()
        if now < self._interaction_flash_until:
            return task.cont
        pos = self.player.root.getPos(self.render)
        if self.world.null_layer:
            if self.world.null_exit_near(pos.x, pos.y):
                self.ui.set_interaction("E // DISCONNECT")
            else:
                self.ui.set_interaction(None)
            return task.cont
        if self.world.glasses_near(pos.x, pos.y):
            self.ui.set_interaction("E // WEAR")
            return task.cont
        if self.world.instance_complete:
            self.ui.set_interaction("Q // WAKE IN DREAMCATCHER")
            return task.cont
        node = self.world.nearest_stabilizer(pos.x, pos.y)
        if node is None:
            self.ui.set_interaction(None)
        elif node.active:
            target = self.world.target_display_name(node.target_zone)
            if node.target_zone in self.world.visited_stabilized_zones:
                self.ui.set_interaction(f"{target} // LINK COMPLETE")
            else:
                self.ui.set_interaction(f"{target} // STABLE — GO THERE")
        elif node.unlocked:
            target = self.world.target_display_name(node.target_zone)
            self.ui.set_interaction(f"E // STABILIZE {target}")
        else:
            self.ui.set_interaction("STABILITY RELAY // DORMANT")
        return task.cont

    def _sync_dreamer_recovery(self):
        progress = self.world.dreamer_recovery_fraction
        self.dreamer.set_recovery_progress(progress)
        if self.world.route_complete and not self.dreamer.released and not self.world.null_layer:
            if self.args.qa_shot or self.args.self_test:
                self.dreamer.set_release_ready(True)
            else:
                self._start_instance_collapse()

    def _start_instance_collapse(self):
        if self._instance_collapse_in_progress or self.dreamer.released or self.world.null_layer:
            return
        self._instance_collapse_in_progress = True
        self.player.set_control_locked(True)
        self.dreamer.set_control_locked(True)
        self.audio.play_sfx("instance_collapse")
        self.audio.begin_datamosh(play_disturb_sfx=False)
        self.ui.set_interaction("INSTANCE // DESTABILIZING")
        self._interaction_flash_until = ClockObject.getGlobalClock().getFrameTime() + 1.3
        started = self.vision.trigger_datamosh(self._perform_instance_collapse, self._finish_instance_collapse)
        if not started:
            self._instance_collapse_in_progress = False
            self.player.set_control_locked(False)
            self.dreamer.set_control_locked(False)

    def _perform_instance_collapse(self):
        self.dreamer.release()
        self.world.instance_complete = True

    def _finish_instance_collapse(self):
        self.audio.stop_current()
        self.player.set_control_locked(False)
        self.dreamer.set_control_locked(False)
        self._instance_collapse_in_progress = False
        self.ui.set_interaction("INSTANCE // INTERCEPT BROKEN")
        self._interaction_flash_until = ClockObject.getGlobalClock().getFrameTime() + 2.2
        self._record_completion("intercept_broken")

    def _start_dreamer_release(self):
        if self._dreamer_release_in_progress or not self.dreamer.can_release():
            return
        self._dreamer_release_in_progress = True
        self.player.set_control_locked(True)
        self.dreamer.set_control_locked(True)
        self.ui.set_interaction("SLEEPER // RECONSTRUCTING")
        self._interaction_flash_until = ClockObject.getGlobalClock().getFrameTime() + 1.0
        started = self.vision.trigger_datamosh(self._perform_dreamer_release, self._finish_dreamer_release)
        if not started:
            self._dreamer_release_in_progress = False
            self.player.set_control_locked(False)
            self.dreamer.set_control_locked(False)

    def _perform_dreamer_release(self):
        # No teleport occurs here.  The physical Dreamer vanishes while the
        # temporal feedback buffer still contains its previous frames, causing
        # the figure to smear into the room as the old image is overwritten.
        self.dreamer.release()

    def _finish_dreamer_release(self):
        self.player.set_control_locked(False)
        self.dreamer.set_control_locked(False)
        self._dreamer_release_in_progress = False
        self.ui.set_interaction("SLEEPER // GONE")
        self._interaction_flash_until = ClockObject.getGlobalClock().getFrameTime() + 2.0

    # ------------------------------------------------------------------
    # Dreamer encounter / relocation
    # ------------------------------------------------------------------
    def _on_dreamer_encounter(self, dreamer):
        if self.paused or self.vision.active or dreamer.release_ready or dreamer.released:
            return
        self.player.set_control_locked(True)
        dreamer.set_control_locked(True)
        dreamer.set_encounter_cooldown(3.0)
        self.audio.begin_datamosh()
        started = self.vision.trigger_datamosh(self._perform_datamosh_relocation, self._finish_datamosh)
        if not started:
            self.player.set_control_locked(False)
            dreamer.set_control_locked(False)

    def _choose_relocation(self):
        anchors = self.world.relocation_anchors
        current = self.player.root.getPos(self.render)
        # Cycle, but reject any destination too close to the current position.
        for _ in range(len(anchors)):
            anchor = anchors[self._relocation_index % len(anchors)]
            self._relocation_index = (self._relocation_index + 1) % len(anchors)
            pos, heading, dreamer_pos = anchor
            if math.hypot(pos.x - current.x, pos.y - current.y) >= 5.0:
                return anchor
        return anchors[self._relocation_index % len(anchors)]

    def _perform_datamosh_relocation(self):
        pos, heading, dreamer_pos = self._choose_relocation()
        self.player.teleport(pos, heading)
        self.dreamer.set_position(dreamer_pos.x, dreamer_pos.y, 180.0)
        # A Dreamer catch is this game's respawn/re-entry event.  The world keeps
        # its topology but slightly re-remembers textures, trim colors and lights.
        # Because the datamosh history still contains the old cycle, the palette
        # shift is inherited through the corruption rather than cutting cleanly.
        self.world.advance_dream_cycle()
        self._apply_cycle_environment()
        self.dreamer.set_encounter_cooldown(3.25)

    def _finish_datamosh(self):
        self.audio.finish_datamosh(self.world.dream_cycle, advance_track=True)
        self.player.set_control_locked(False)
        self.dreamer.set_control_locked(False)

    # ------------------------------------------------------------------
    # QA
    # ------------------------------------------------------------------
    def _configure_qa_view(self, scene):
        views = {
            "spawn": ((0.0, -18.0, 0.0), (0.0, -5.0), (0.0, 12.45, 180.0)),
            "junction": ((0.1, -4.2, 0.0), (0.0, -3.0), (0.0, 12.45, 180.0)),
            "lattice": ((8.2, 4.5, 0.0), (6.0, -2.0), (0.0, 12.45, 180.0)),
            "analog": ((-8.0, 10.8, 0.0), (-90.0, -2.0), (0.0, 12.45, 180.0)),
            "buffer": ((0.0, 17.5, 0.0), (0.0, -2.0), (0.0, 12.45, 180.0)),
            "stable": ((6.0, 22.2, 0.0), (28.0, -3.0), (0.0, 12.45, 180.0)),
            "archive": ((-2.6, -0.2, 0.0), (90.0, -2.0), (0.0, 12.45, 180.0)),
            "feedback": ((10.6, 5.8, 0.0), (-90.0, -2.0), (-8.0, 11.8, 180.0)),
            "dead": ((-10.6, 11.8, 0.0), (90.0, -2.0), (7.8, 6.3, 180.0)),
            "stabilized": ((-14.2, 12.0, 0.0), (90.0, -1.0), (0.0, 9.0, 180.0)),
            "interaction": ((-1.05, -2.0, 0.0), (90.0, -1.0), (0.0, 9.0, 180.0)),
            "relay-link": ((0.1, -3.8, 0.0), (22.0, -2.0), (0.0, 12.45, 180.0)),
            "archive-stable": ((-2.6, -0.2, 0.0), (90.0, -2.0), (0.0, 12.45, 180.0)),
            "feedback-stable": ((10.6, 5.8, 0.0), (-90.0, -2.0), (-8.0, 11.8, 180.0)),
            "route-complete": ((0.0, 17.6, 0.0), (0.0, -2.0), (7.8, 6.3, 180.0)),
            "dreamer": ((0.0, 4.2, 0.0), (0.0, -1.5), (0.0, 11.9, 180.0)),
            "dreamer-close": ((0.0, 7.55, 0.0), (0.0, -1.5), (0.0, 10.05, 180.0)),
            "sleeper-side": ((0.0, 7.55, 0.0), (0.0, -1.5), (0.0, 10.05, 90.0)),
            "vision-blur": ((19.4, 6.0, 0.0), (-90.0, -1.5), (0.0, 12.45, 180.0)),
            "vision-clear": ((19.4, 6.0, 0.0), (-90.0, -1.5), (0.0, 12.45, 180.0)),
            "dreamer-recovered": ((0.0, 7.40, 0.0), (0.0, -1.5), (0.0, 10.05, 180.0)),
            "release-mosh": ((0.0, 7.40, 0.0), (0.0, -1.5), (0.0, 10.05, 180.0)),
            "released": ((0.0, 7.40, 0.0), (0.0, -1.5), (0.0, 10.05, 180.0)),
            "mosh": ((0.0, 7.1, 0.0), (0.0, -1.0), (0.0, 10.0, 180.0)),
            "cycle-a": ((-0.1, -3.8, 0.0), (0.0, -2.0), (0.0, 12.45, 180.0)),
            "cycle-b": ((-0.1, -3.8, 0.0), (0.0, -2.0), (0.0, 12.45, 180.0)),
            "false-hall": ((19.4, 6.0, 0.0), (-90.0, -1.5), (0.0, 12.45, 180.0)),
            "false-hall-near": ((31.0, 6.0, 0.0), (-90.0, -1.5), (0.0, 12.45, 180.0)),
            "dark-room": ((-13.0, 12.0, 0.0), (90.0, -2.0), (0.0, 12.45, 180.0)),
            "glasses": ((38.6, 8.2, 0.0), (-82.0, -12.0), (0.0, 12.45, 180.0)),
            "glasses-on": ((19.4, 6.0, 0.0), (-90.0, -1.5), (0.0, 12.45, 180.0)),
            "lightless-room": ((2.7, -11.5, 0.0), (-90.0, -3.0), (0.0, 12.45, 180.0)),
            "lightless-deep": ((6.6, -11.5, 0.0), (90.0, -2.0), (0.0, 12.45, 180.0)),
            "echo-room": ((-2.6, 20.5, 0.0), (90.0, -2.0), (0.0, 12.45, 180.0)),
            "echo-near": ((-6.3, 20.5, 0.0), (90.0, -2.0), (0.0, 12.45, 180.0)),
            "witness-alcove": ((-7.5, -4.2, 0.0), (180.0, -2.0), (0.0, 12.45, 180.0)),
            "witness-near": ((-8.0, -7.0, 0.0), (180.0, -1.0), (0.0, 12.45, 180.0)),
            "return-room": ((-8.7, 5.0, 0.0), (90.0, -2.0), (0.0, 12.45, 180.0)),
            "return-near": ((-15.6, 5.0, 0.0), (90.0, -1.5), (0.0, 12.45, 180.0)),
            "return-memory-a": ((-9.0, 4.5, 0.0), (-90.0, -1.0), (0.0, 12.45, 180.0)),
            "return-memory-b": ((-9.0, 4.5, 0.0), (-90.0, -1.0), (0.0, 12.45, 180.0)),
            "false-sleeper": ((7.52, -10.6, 0.0), (180.0, -2.0), (0.0, 12.45, 180.0)),
            "gleebs-trace": ((-9.50, 4.35, 0.0), (0.0, -1.0), (0.0, 12.45, 180.0)),
            "memory-seam": ((1.25, -2.0, 0.0), (-90.0, -2.0), (0.0, 12.45, 180.0)),
            "null-layer": ((0.0, 18.0, 0.0), (0.0, -2.0), (0.0, 12.45, 180.0)),
            "null-exit": ((0.0, 24.4, 0.0), (0.0, -1.0), (0.0, 12.45, 180.0)),
            "instance-collapse": ((0.0, 7.40, 0.0), (0.0, -1.5), (0.0, 10.05, 180.0)),
            "first-target": ((0.0, -2.0, 0.0), (0.0, -2.0), (0.0, 12.45, 180.0)),
            "false-sleeper-weakened": ((7.52, -10.6, 0.0), (180.0, -2.0), (0.0, 12.45, 180.0)),
            "resonance-charge": ((0.0, 6.15, 0.0), (0.0, -1.5), (0.0, 10.05, 180.0)),
            "resonance-read": ((0.0, 6.15, 0.0), (0.0, -1.5), (0.0, 10.05, 180.0)),
            "resonance-target-normal": ((-0.45, -0.1, 0.0), (90.0, -2.0), (0.0, 12.45, 180.0)),
            "resonance-target-read": ((-0.45, -0.1, 0.0), (90.0, -2.0), (0.0, 12.45, 180.0)),
            "false-sleeper-resonance": ((7.52, -10.6, 0.0), (180.0, -2.0), (0.0, 12.45, 180.0)),
            "sleeper-sink": ((0.0, 7.45, 0.0), (0.0, -2.0), (0.0, 10.05, 180.0)),
            "sleeper-ceiling": ((0.0, 7.45, 0.0), (0.0, 4.5), (0.0, 10.05, 180.0)),
            "sleeper-under": ((0.0, 10.68, 0.0), (180.0, 18.0), (0.0, 10.05, 180.0)),
        }
        pos, hpr, dreamer = views.get(scene, views["spawn"])
        self.player.teleport(Point3(*pos), hpr[0])
        self.player.pitch = hpr[1]
        self.camera.setP(hpr[1])
        self.dreamer.set_position(*dreamer)
        self.dreamer.manual_mode = True
        if scene == "sleeper-sink":
            self.dreamer.force_ceiling_loop(0.54, "sinking")
        elif scene in ("sleeper-ceiling", "sleeper-under"):
            self.dreamer.force_ceiling_loop(1.0, "holding")
        if scene == "vision-clear":
            # QA-only matched view: isolate distance-focus behavior without entering Null Layer.
            self.vision.set_focus_assist(1.0)
        elif scene == "vision-blur":
            self.vision.set_focus_assist(0.0)
        if scene == "first-target":
            first = self.world.route_zones[0]
            first_views = {
                "archive": ((-2.6, -0.2, 0.0), 90.0, -2.0),
                "feedback": ((10.6, 5.8, 0.0), -90.0, -2.0),
                "dead": ((-10.6, 11.8, 0.0), 90.0, -2.0),
            }
            node = self.world.stability_nodes["relay-node"]
            self.world.stabilize_nearest(node.pos.x, node.pos.y, max_distance=0.7)
            fpos, fh, fp = first_views[first]
            self.player.teleport(Point3(*fpos), fh)
            self.player.pitch = fp
            self.camera.setP(fp)
        if scene == "false-sleeper-resonance" and self.world._false_sleeper_roots:
            for root in self.world._false_sleeper_roots:
                root.hide()
            self.world._false_sleeper_profile_indices = (0, 1, 2)
            self.world._false_sleeper_visible_indices = (0, 1, 2)
            self.world._false_sleeper_roots[1].show()
            self.world.set_resonance_view(True)
            self.world.update_resonance_pulse(2.4)
            self.vision.set_focus_assist(0.74)
        if scene == "false-sleeper" and self.world._false_sleeper_roots:
            for root in self.world._false_sleeper_roots:
                root.hide()
            self.world._false_sleeper_profile_indices = (0, 1, 2)
            self.world._false_sleeper_visible_indices = (0, 1, 2)
            self.world._false_sleeper_roots[1].show()
        if scene == "false-sleeper-weakened" and self.world._false_sleeper_roots:
            for root in self.world._false_sleeper_roots:
                root.hide()
            self.world._false_sleeper_profile_indices = (0, 1, 2)
            self.world._false_sleeper_visible_indices = (0, 1, 2)
            # Three room recoveries are enough to erase the false-Sleeper layer.
            self._qa_activate_route_through(self.world.route_zones[2])
            self.world._apply_destabilization_response()
        if scene == "resonance-charge":
            self.dreamer.set_resonance_strength(0.72)
            self.vision.set_focus_assist(0.17)
        elif scene in ("resonance-read", "resonance-target-read"):
            self.dreamer.set_resonance_strength(1.0)
            self.vision.set_focus_assist(0.74)
            self.world.set_resonance_view(True)
            self.world.update_resonance_pulse(2.4)
        if scene == "gleebs-trace" and self.world._gleebs_trace_root is not None:
            pos, heading = self.world._gleebs_trace_anchors[0]
            self.world._gleebs_trace_root.setPos(pos)
            self.world._gleebs_trace_root.setH(heading)
            self.world._gleebs_trace_root.show()
            for eye in self.world._gleebs_trace_eyes:
                eye.show()
        if scene == "memory-seam":
            self.world._reveal_memory_seam()
        if scene in ("null-layer", "null-exit"):
            self.world.glasses_collected = True
            if self.world.glasses_root:
                self.world.glasses_root.hide()
            self.world.enter_null_layer()
            self.vision.set_null_layer(True)
            self.dreamer.enter_null_layer()
            self._apply_cycle_environment()
        if scene == "return-memory-b":
            # Trigger the environmental recomposition while looking away, then
            # turn back for a matched screenshot of the changed bracket.
            self.world.update_anomalies(-9.0, 4.5, 2.0, 90.0)
            self.player.teleport(Point3(-9.0, 4.5, 0.0), -90.0)
            self.player.pitch = -1.0
            self.camera.setP(-1.0)
        if scene == "glasses":
            self.world.glasses_pos = Point3(40.25, 8.35, 0.0)
            if self.world.glasses_root:
                self.world.glasses_root.setPos(40.25, 8.35, 0.24)
                self.world.glasses_root.show()
        if scene == "glasses-on":
            self.world.glasses_collected = True
            if self.world.glasses_root:
                self.world.glasses_root.hide()
            self.world.enter_null_layer()
            self.vision.set_null_layer(True)
            self.dreamer.enter_null_layer()
            self._apply_cycle_environment()
        if scene == "cycle-b":
            self.world.apply_dream_cycle(1, force=True)
            self._apply_cycle_environment()
        elif scene == "cycle-a":
            self.world.apply_dream_cycle(0, force=True)
            self._apply_cycle_environment()
        if scene == "stabilized":
            # Legacy QA name now shows a remotely stabilized Dead Channel.
            self._qa_activate_route_through("dead")
        elif scene == "archive-stable":
            self._qa_activate_route_through("archive")
        elif scene == "feedback-stable":
            self._qa_activate_route_through("feedback")
        elif scene == "route-complete":
            self._qa_activate_route_through("buffer")
            self.world.register_zone_visit("buffer")
            self._sync_dreamer_recovery()
        elif scene in ("dreamer-recovered", "release-mosh", "released", "instance-collapse"):
            self._qa_activate_route_through("buffer")
            self.world.register_zone_visit("buffer")
            self._sync_dreamer_recovery()
            if scene == "released":
                self.dreamer.release()
        self.ui.crosshair.hide()
        if scene not in ("interaction", "relay-link"):
            self.ui.set_interaction(None)

    def _qa_activate_route_through(self, target_zone: str):
        # Follow the run's authored Pass 13 route rather than assuming the old
        # Archive -> Feedback -> Dead order.
        for node_id in self.world.route_node_order:
            node = self.world.stability_nodes[node_id]
            if not node.unlocked:
                self.world.register_zone_visit(node.zone)
            activated = self.world.stabilize_nearest(node.pos.x, node.pos.y, max_distance=0.7)
            target = node.target_zone
            if activated is None and not node.active:
                break
            if target == target_zone:
                break
            self.world.register_zone_visit(target)

    def _qa_frame_driver(self, task):
        # Deterministic visual QA uses frame counts rather than wall-clock delays.
        # This keeps shader time/history identical across development and fresh
        # package runs even when filesystem/loading speed differs.
        self._qa_frame += 1
        if self.args.qa_scene in ("mosh", "release-mosh", "instance-collapse") and not self._qa_mosh_prepared and self._qa_frame >= 8:
            self._qa_mosh_prepared = True
            if self.args.qa_scene in ("release-mosh", "instance-collapse"):
                self._prepare_qa_release_mosh(task)
            else:
                self._prepare_qa_mosh(task)
        target = 24 if self.args.qa_scene in ("mosh", "release-mosh", "instance-collapse") else 18
        if self._qa_frame >= target:
            self._capture_qa(task)
            return task.done
        return task.cont

    def _prepare_qa_mosh(self, task):
        # Capture the pressure-hall frame, then jump to the lattice chamber and
        # freeze the post-process mid-transition so the screenshot proves old/new
        # image persistence in a single actual Panda frame.
        self.graphicsEngine.renderFrame()
        # Temporal feedback is already carrying the old room frame-to-frame.
        # Relocate without a clean reset, then hold the corruption high while the
        # destination begins painting itself through the inherited history.
        self.player.teleport(Point3(7.1, 6.0, 0.0), 90.0)
        self.dreamer.set_position(-8.0, 11.0, 180.0)
        self.world.advance_dream_cycle()
        self._apply_cycle_environment()
        self.vision.force_debug_mosh(event=0.94)
        return task.done

    def _prepare_qa_release_mosh(self, task):
        # Render the coherent Dreamer into temporal history, remove the live
        # entity, then hold the mosh near peak.  The resulting screenshot proves
        # that the old silhouette survives as image data after the entity is gone.
        self.graphicsEngine.renderFrame()
        self.dreamer.release()
        self.vision.force_debug_mosh(event=0.94)
        return task.done

    def _capture_qa(self, task):
        path = Path(self.args.qa_shot)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.graphicsEngine.renderFrame()
        self.graphicsEngine.renderFrame()
        ok = self.win.saveScreenshot(Filename.fromOsSpecific(str(path)))
        print(f"QA_SCREENSHOT={path} OK={bool(ok)}")
        self.taskMgr.doMethodLater(0.05, lambda t: self.userExit(), "qa-exit")
        return task.done

    def _finish_smoke(self, task):
        print(f"SMOKE_PASS window=1 world=1 controller=1 dreamer=1 vision={int(self.vision.available)} pause=1")
        self.userExit()
        return task.done

    def _set_view(self, pos, heading, pitch=0.0):
        self.player.root.setPos(*pos)
        self.player.heading = heading
        self.player.pitch = pitch
        self.player.root.setH(heading)
        self.camera.setP(pitch)

    def _start_self_test(self):
        self.player.manual_mode = True
        self.dreamer.manual_mode = True
        results = []

        # Pass 14 audio remains frozen authority. The self-test uses Panda's null audio
        # backend, so this verifies packaged discovery without requiring a speaker.
        results.append(("pass14_ambient_loop_count", self.audio.track_count == 6, self.audio.track_count))
        results.append(("pass16_sfx_count", len(self.audio._sfx_paths) == 11, len(self.audio._sfx_paths)))

        results.append(("nightmare_vision_available", self.vision.available, int(self.vision.available)))
        results.append(("temporal_feedback_enabled", self.vision.temporal_feedback, int(self.vision.temporal_feedback)))
        results.append(("temporal_feedback_targets", len(self.vision.feedback_buffer) == 2 and len(self.vision.feedback_tex) == 2, len(self.vision.feedback_buffer)))

        # Exercise both ping-pong targets through the real Panda render engine.
        feedback_before = self.vision.feedback_frames
        self.vision._activate_feedback_target(0.0)
        self.graphicsEngine.renderFrame()
        self.vision._activate_feedback_target(1.0 / 60.0)
        self.graphicsEngine.renderFrame()
        feedback_advanced = self.vision.feedback_frames - feedback_before
        textures_sized = all(tex.getXSize() > 64 and tex.getYSize() > 64 for tex in self.vision.feedback_tex)
        results.append(("temporal_pingpong_advances", feedback_advanced == 2, feedback_advanced))
        results.append(("temporal_targets_rendered", textures_sized, int(textures_sized)))

        cycle0_sig = self.world.cycle_signature
        self.world.apply_dream_cycle(1, force=True)
        cycle1_sig = self.world.cycle_signature
        results.append(("dream_cycle_advances", self.world.dream_cycle == 1, self.world.dream_cycle))
        results.append(("dream_cycle_visual_signature_changes", cycle1_sig != cycle0_sig, int(cycle1_sig != cycle0_sig)))
        variant_count = sum(1 for part in cycle1_sig.split("|") if part.endswith(":1") or part.endswith(":2"))
        results.append(("dream_cycle_uses_texture_variants", variant_count >= 2, variant_count))
        # Return deterministic self-test state to cycle zero before testing gameplay.
        self.world.apply_dream_cycle(0, force=True)
        self._apply_cycle_environment()

        # Pass 09 Uneven Dreamspace contract.
        results.append(("distance_depth_texture", self.vision.depth_tex.getXSize() > 64 and self.vision.depth_tex.getYSize() > 64, self.vision.depth_tex.getXSize()))
        results.append(("falsehall_connected", self.world.path_exists((16, 6), (40, 5)), int(self.world.path_exists((16, 6), (40, 5)))))
        fov_entry = self.world.dream_lens_fov_offset(19.4, 6.0)
        fov_mid = self.world.dream_lens_fov_offset(31.0, 6.0)
        fov_exit = self.world.dream_lens_fov_offset(37.0, 6.0)
        results.append(("falsehall_entry_telephoto", fov_entry < -15.0, fov_entry))
        results.append(("falsehall_widens_during_approach", fov_mid > 6.0, fov_mid))
        results.append(("falsehall_releases_at_threshold", abs(fov_exit) < 1.0, fov_exit))
        dark_dead = self.world.darkness_at(-16.0, 12.0)
        light_stable = self.world.darkness_at(8.0, 23.0)
        results.append(("uneven_room_darkness", dark_dead > 0.50 and light_stable < 0.10, dark_dead - light_stable))
        self.player.teleport(Point3(self.world.glasses_pos.x - 0.5, self.world.glasses_pos.y, 0.0), 90.0)
        glasses_near = self.world.glasses_near(self.player.root.getX(), self.player.root.getY())
        results.append(("hidden_glasses_found", glasses_near, int(glasses_near)))
        # Do not enter the one-way Null Layer yet; the remainder of the regression
        # still needs the ordinary dream presentation.
        results.append(("glasses_anchor_is_walkable", self.world.can_stand(self.world.glasses_pos.x, self.world.glasses_pos.y, radius=0.20), self.world.glasses_anchor_index))

        # Pass 15 recovery: the live Sleeper visual is one loaded continuous mesh
        # plus only two restrained whole-body registration echoes.
        results.append(("pass15_sleeper_continuous_mesh", self.dreamer._core_mesh is not None and not self.dreamer._core_mesh.isEmpty(), int(self.dreamer._core_mesh is not None and not self.dreamer._core_mesh.isEmpty())))
        results.append(("pass15_sleeper_whole_body_echo_count", len(self.dreamer._ghosts) == 2, len(self.dreamer._ghosts)))

        # Pass 17 Ceiling Loop: a close watched Sleeper temporarily owns its XY
        # position, wraps the continuous body through real floor/ceiling geometry,
        # and becomes safe to pass beneath only after full clearance is visible.
        self.dreamer.set_position(0.0, 10.05, 180.0)
        self.player.teleport(Point3(0.0, 8.20, 0.0), 0.0)
        for _ in range(45):
            self.dreamer.simulate_step(1.0 / 60.0, force_observed=True, allow_encounter=False)
        triggered = self.dreamer.ceiling_loop_state in ("sinking", "holding")
        for _ in range(180):
            self.dreamer.simulate_step(1.0 / 60.0, force_observed=True, allow_encounter=False)
        open_state = self.dreamer.ceiling_passage_open
        ceiling_z = self.dreamer._ceiling_holder.getZ() if self.dreamer._ceiling_holder is not None else -99.0
        ground_z = self.dreamer._ground_holder.getZ() if self.dreamer._ground_holder is not None else 99.0
        results.append(("pass17_ceiling_loop_triggers_from_close_gaze", triggered, int(triggered)))
        results.append(("pass17_ceiling_loop_separate_from_resonance_band", self.dreamer._ceiling_trigger_max < 2.45, self.dreamer._ceiling_trigger_max))
        results.append(("pass17_ceiling_loop_opens_floor_route", open_state and ceiling_z >= 1.85 and ground_z <= -2.45, ceiling_z))
        results.append(("pass17_ceiling_copy_uses_same_continuous_visual", self.dreamer._ceiling_instance is not None and not self.dreamer._ceiling_instance.isEmpty(), int(self.dreamer._ceiling_instance is not None)))
        # Prove floor-level contact is suppressed while the visual has actually
        # cleared, then restored after the Sleeper reforms.
        hits = []
        old_cb = self.dreamer.on_encounter
        self.dreamer.on_encounter = lambda d: hits.append(1)
        self.player.teleport(Point3(0.0, 10.05, 0.0), 0.0)
        self.dreamer.encounter_cooldown = 0.0
        self.dreamer.simulate_step(1.0 / 60.0, force_observed=True, allow_encounter=True)
        safe_under = not hits

        # Use the actual first-person movement integrator to sprint from one side
        # of the Sleeper to the other while the ceiling opening is held.
        self.dreamer.force_ceiling_loop(1.0, "holding")
        self.player.teleport(Point3(0.0, 8.05, 0.0), 0.0)
        self.player.keys["forward"] = True
        self.player.keys["sprint"] = True
        self.dreamer.encounter_cooldown = 0.0
        start_y = self.player.root.getY()
        for _ in range(52):
            self.player.simulate_step(1.0 / 60.0)
            self.dreamer.simulate_step(1.0 / 60.0, force_observed=True, allow_encounter=True)
        self.player.clear_inputs()
        run_y = self.player.root.getY()
        sprint_crossed = run_y > 11.25 and not hits
        results.append(("pass17_actual_sprint_crosses_beneath", sprint_crossed, run_y - start_y))

        self.dreamer._reset_ceiling_loop()
        self.player.teleport(Point3(0.0, 10.05, 0.0), 0.0)
        self.dreamer.encounter_cooldown = 0.0
        self.dreamer.simulate_step(1.0 / 60.0, force_observed=True, allow_encounter=True)
        dangerous_again = bool(hits)
        self.dreamer.on_encounter = old_cb
        results.append(("pass17_floor_contact_safe_only_when_tucked", safe_under and dangerous_again, int(safe_under and dangerous_again)))
        self.dreamer.set_position(0.0, 12.45, 180.0)

        # Pass 10 Dream Anomalies contract.  All new odd spaces remain honest
        # walkable geometry while their wrongness stays visual/lighting based.
        anomaly_targets = {
            "unlit": (6, -11),
            "echo": (-7, 20),
            "witness": (-8, -8),
        }
        for name, cell in anomaly_targets.items():
            results.append((f"anomaly_{name}_walkable", cell in self.world.walkable, int(cell in self.world.walkable)))
            results.append((f"anomaly_{name}_connected", self.world.path_exists((0, -18), cell), int(self.world.path_exists((0, -18), cell))))
        results.append(("lightless_room_is_darkest", self.world.darkness_at(6.0, -11.0) > 0.82, self.world.darkness_at(6.0, -11.0)))
        results.append(("witness_room_dark", self.world.darkness_at(-8.0, -8.0) > 0.70, self.world.darkness_at(-8.0, -8.0)))
        results.append(("echo_room_moderate", 0.35 < self.world.darkness_at(-7.0, 20.0) < 0.60, self.world.darkness_at(-7.0, 20.0)))
        # Delayed fixtures must visibly differ before/after the player passes them.
        self.world.update_anomalies(7.9, -11.5, 2.0)
        dim_scale = self.world._unlit_afterglow[1][0].getColorScale().x
        self.world.update_anomalies(4.0, -11.5, 2.0)
        bright_scale = self.world._unlit_afterglow[1][0].getColorScale().x
        results.append(("lightless_afterglow_lags_player", bright_scale > dim_scale + 0.25, bright_scale - dim_scale))
        # Borrowed Echo Room memory should be stronger at range and fade up close.
        self.world.update_anomalies(-2.6, 20.5, 2.0)
        far_alpha = self.world._echo_bleed_nodes[0].getColorScale().w
        self.world.update_anomalies(-7.0, 20.5, 2.0)
        near_alpha = self.world._echo_bleed_nodes[0].getColorScale().w
        results.append(("echo_memory_resolves_on_approach", far_alpha > near_alpha + 0.25, far_alpha - near_alpha))
        witness0 = self.world._witness_root.getPos(self.render) if self.world._witness_root else Point3(0)
        sig0 = self.world.anomaly_signature
        self.world.apply_dream_cycle(2, force=True)
        witness2 = self.world._witness_root.getPos(self.render) if self.world._witness_root else Point3(0)
        shift = (witness2 - witness0).length()
        results.append(("witness_shifts_between_cycles", sig0 != self.world.anomaly_signature and 0.01 < shift < 0.30, shift))
        self.world.apply_dream_cycle(0, force=True)
        self._apply_cycle_environment()

        # Pass 11 Continuity Errors: a new optional Return Room remains physically
        # ordinary while its false exit and unseen wall-memory shift undermine
        # visual continuity.  No collision or required progression depends on it.
        return_cell = (-9, 4)
        recess_cell = (-17, 4)
        results.append(("return_room_walkable", return_cell in self.world.walkable, int(return_cell in self.world.walkable)))
        results.append(("return_room_connected", self.world.path_exists((0, -18), return_cell), int(self.world.path_exists((0, -18), return_cell))))
        return_dark = self.world.darkness_at(-9.0, 4.5)
        results.append(("return_room_moderately_dark", 0.50 < return_dark < 0.72, return_dark))
        results.append(("false_exit_recess_walkable", recess_cell in self.world.walkable, int(recess_cell in self.world.walkable)))
        results.append(("false_exit_has_real_back_wall", (-18, 4) not in self.world.walkable, int((-18, 4) not in self.world.walkable)))
        self.world.apply_dream_cycle(0, force=True)
        bracket_before = Point3(self.world._return_memory_root.getPos(self.render)) if self.world._return_memory_root else Point3(0)
        self.world.update_anomalies(-9.0, 4.5, 2.0, -90.0)
        results.append(("return_memory_does_not_move_while_seen", not self.world.return_memory_shifted, int(self.world.return_memory_shifted)))
        self.world.update_anomalies(-9.0, 4.5, 2.0, 90.0)
        bracket_after = Point3(self.world._return_memory_root.getPos(self.render)) if self.world._return_memory_root else Point3(0)
        bracket_shift = (bracket_after - bracket_before).length()
        results.append(("return_memory_moves_only_unseen", self.world.return_memory_shifted and 0.25 < bracket_shift < 0.45, bracket_shift))
        self.world.apply_dream_cycle(0, force=True)
        results.append(("return_memory_resets_on_dream_cycle", not self.world.return_memory_shifted, int(self.world.return_memory_shifted)))

        # Walk the visible thresholds with the actual first-person controller.
        self.player.teleport(Point3(0.25, -11.5, 0.0), -90.0)
        self.player.keys["forward"] = True
        for _ in range(115):
            self.player.simulate_step(1.0 / 60.0)
        self.player.keys["forward"] = False
        results.append(("unlit_threshold_traversable", self.world.zone_at(self.player.root.getX(), self.player.root.getY()) == "unlit" and self.player.root.getX() > 3.0, self.player.root.getX()))

        self.player.teleport(Point3(-1.6, 20.5, 0.0), 90.0)
        self.player.keys["forward"] = True
        for _ in range(105):
            self.player.simulate_step(1.0 / 60.0)
        self.player.keys["forward"] = False
        results.append(("echo_threshold_traversable", self.world.zone_at(self.player.root.getX(), self.player.root.getY()) == "echo" and self.player.root.getX() < -4.4, self.player.root.getX()))

        self.player.teleport(Point3(-7.5, -2.5, 0.0), 180.0)
        self.player.keys["forward"] = True
        for _ in range(110):
            self.player.simulate_step(1.0 / 60.0)
        self.player.keys["forward"] = False
        results.append(("witness_threshold_traversable", self.world.zone_at(self.player.root.getX(), self.player.root.getY()) == "witness" and self.player.root.getY() < -5.2, self.player.root.getY()))

        self.player.teleport(Point3(-9.5, 8.7, 0.0), 180.0)
        self.player.keys["forward"] = True
        for _ in range(105):
            self.player.simulate_step(1.0 / 60.0)
        self.player.keys["forward"] = False
        results.append(("return_threshold_traversable", self.world.zone_at(self.player.root.getX(), self.player.root.getY()) == "return" and self.player.root.getY() < 7.0, self.player.root.getY()))

        self.player.teleport(Point3(-12.4, 5.0, 0.0), 90.0)
        self.player.keys["forward"] = True
        for _ in range(180):
            self.player.simulate_step(1.0 / 60.0)
        self.player.keys["forward"] = False
        recess_stop = self.player.root.getX()
        results.append(("false_exit_physically_dead_ends", -16.8 < recess_stop < -16.2 and self.world.zone_at(recess_stop, self.player.root.getY()) == "return", recess_stop))

        # Physical traversal of the entire false-near hall must agree with the
        # visible opening.  This is not a teleport/non-Euclidean collision trick.
        self.player.teleport(Point3(18.3, 6.0, 0.0), -90.0)
        self.player.keys["forward"] = True
        for _ in range(480):
            self.player.simulate_step(1.0 / 60.0)
        self.player.keys["forward"] = False
        falsehall_x = self.player.root.getX()
        results.append(("falsehall_physical_traversal", falsehall_x > 37.2 and self.world.zone_at(self.player.root.getX(), self.player.root.getY()) == "focus", falsehall_x))

        # Pass 04 topology: each old chamber must now reach a distinct side room
        # through real walkable cells.
        branch_targets = {
            "archive": (-8, 0),
            "feedback": (16, 6),
            "dead": (-16, 12),
        }
        spawn_cell = (0, -18)
        for name, cell in branch_targets.items():
            results.append((f"branch_{name}_walkable", cell in self.world.walkable, int(cell in self.world.walkable)))
            results.append((f"branch_{name}_connected", self.world.path_exists(spawn_cell, cell), int(self.world.path_exists(spawn_cell, cell))))

        # Pass 13 shifting route: the topology is frozen, but each run seed chooses
        # one of six authored permutations through Archive/Feedback/Dead before
        # Deep Buffer.  The chosen order must stay fixed across dream cycles.
        route = self.world.route_sequence
        results.append(("route_profile_curated_length", len(route) == 4, len(route)))
        results.append(("route_profile_uses_all_core_rooms", set(route[:-1]) == {"archive", "feedback", "dead"} and route[-1] == "buffer", len(set(route[:-1]))))
        results.append(("route_node_order_matches_profile", len(self.world.route_node_order) == 4 and self.world.route_node_order[0] == "relay-node", len(self.world.route_node_order)))
        seen_profiles = {random.Random((seed * 1000003) ^ 23).randrange(6) for seed in range(1, 120)}
        results.append(("all_six_route_profiles_seedable", seen_profiles == set(range(6)), len(seen_profiles)))

        relay_node = self.world.stability_nodes["relay-node"]
        first_target = route[0]
        results.append(("relay_initially_unlocked", relay_node.unlocked and not relay_node.active, int(relay_node.unlocked)))
        results.append(("first_route_target_matches_relay", relay_node.target_zone == first_target, int(relay_node.target_zone == first_target)))

        target_positions = {
            "archive": (-8.0, 0.0),
            "feedback": (16.0, 6.0),
            "dead": (-16.0, 12.0),
            "buffer": (0.0, 22.0),
        }
        previous_count = self.world.stabilized_count
        first_activation_revealed_seam = False
        for step, node_id in enumerate(self.world.route_node_order):
            node = self.world.stability_nodes[node_id]
            if step > 0:
                results.append((f"route_step_{step}_relay_unlocked", node.unlocked and not node.active, int(node.unlocked)))
            before = self.world.stability_at(*target_positions[node.target_zone])
            activated = self.world.stabilize_nearest(node.pos.x, node.pos.y, max_distance=0.7)
            after = self.world.stability_at(*target_positions[node.target_zone])
            results.append((f"route_step_{step}_activation", activated is node and self.world.stabilized_count == previous_count + 1, self.world.stabilized_count))
            results.append((f"route_step_{step}_remote_room_gain", after >= 0.75 and after > before, after - before))
            previous_count = self.world.stabilized_count
            if step == 0:
                first_activation_revealed_seam = self.world.memory_seam_revealed
            event = self.world.register_zone_visit(node.target_zone)
            if node.target_zone == "buffer":
                results.append(("buffer_visit_completes_route", self.world.route_complete and bool(event and event[0] == "complete"), int(self.world.route_complete)))
            else:
                next_node = self.world.stability_nodes[self.world.route_node_order[step + 1]]
                results.append((f"route_step_{step}_visit_unlocks_next", bool(event and event[0] == "relay" and next_node.unlocked), int(next_node.unlocked)))
        results.append(("first_recovery_reveals_memory_seam", first_activation_revealed_seam, int(first_activation_revealed_seam)))
        last_node = self.world.stability_nodes[self.world.route_node_order[-1]]
        results.append(("stabilizer_repeat_safe", self.world.stabilize_nearest(last_node.pos.x, last_node.pos.y, max_distance=0.7) is None, self.world.stabilized_count))
        results.append(("false_sleepers_decay_with_progress", len(self.world._false_sleeper_visible_indices) == 0, len(self.world._false_sleeper_visible_indices)))

        # A later dream cycle must not visually undo remotely repaired rooms.
        archive_sample = next(np for np in self.world._zone_visual_nodes["archive"] if np.hasTag("dream-zone"))
        before_scale = archive_sample.getColorScale()
        cycle_before_stable_check = self.world.dream_cycle
        self.world.apply_dream_cycle(cycle_before_stable_check + 1, force=True)
        self._apply_cycle_environment()
        after_scale = archive_sample.getColorScale()
        stable_color_kept = after_scale.z > after_scale.x and after_scale.z >= 1.05
        results.append(("remote_stability_survives_dream_cycle", stable_color_kept, float(after_scale.z)))
        spindle_color = self.world.relay_spindle_parts[0].getColor() if self.world.relay_spindle_parts else None
        relay_visual_kept = bool(spindle_color and spindle_color.z > 0.90 and spindle_color.x < 0.25)
        results.append(("active_relay_visual_survives_dream_cycle", relay_visual_kept, float(spindle_color.z) if spindle_color else 0.0))

        # Actual first-person traversal must cross the relay wall opening into the
        # Archive Cell; this catches a visible-opening / collision mismatch.
        self.player.teleport(Point3(-2.4, -0.2, 0.0), 90.0)
        self.player.keys["forward"] = True
        for _ in range(100):
            self.player.simulate_step(1.0 / 60.0)
        self.player.keys["forward"] = False
        branch_x = self.player.root.getX()
        results.append(("archive_threshold_traversable", branch_x < -5.5 and self.world.zone_at(self.player.root.getX(), self.player.root.getY()) == "archive", branch_x))

        # App-level interaction remains the only player-facing activation path.
        # Reset only the relay node and its current first target for this narrow check.
        relay_node.active = False
        relay_node.unlocked = True
        self.world.stabilized_zones.discard(first_target)
        self.world.visited_stabilized_zones.discard(first_target)
        self.world._refresh_stabilizer_visual(relay_node)
        self.player.teleport(Point3(-1.05, -2.0, 0.0), 0.0)
        self._try_stabilize()
        results.append(("interaction_remotely_stabilizes_first_target", relay_node.active and first_target in self.world.stabilized_zones, int(relay_node.active)))

        spawn_pos, spawn_h = self.world.spawn
        self.player.teleport(spawn_pos, spawn_h)
        start = self.player.root.getPos()
        self.player.keys["forward"] = True
        for _ in range(40):
            self.player.simulate_step(1.0 / 60.0)
        self.player.keys["forward"] = False
        moved = (self.player.root.getPos() - start).length()
        results.append(("walk_forward", moved > 1.0, moved))

        self.player.root.setPos(0.38, -12.0, 0.0)
        self.player.keys["right"] = True
        for _ in range(90):
            self.player.simulate_step(1.0 / 60.0)
        self.player.keys["right"] = False
        x = self.player.root.getX()
        results.append(("wall_collision", x < 0.69, x))

        self.player.root.setPos(0, -12, 0)
        self.player.grounded = True
        self.player.vertical_velocity = 0.0
        self.player.jump()
        peak = 0.0
        for _ in range(150):
            self.player.simulate_step(1.0 / 60.0)
            peak = max(peak, self.player.root.getZ())
        results.append(("jump_peak", peak > 0.45, peak))
        results.append(("jump_land", abs(self.player.root.getZ()) < 0.03 and self.player.grounded, self.player.root.getZ()))

        self.player.keys["forward"] = True
        self.player.set_paused(True)
        self.dreamer.set_paused(True)
        results.append(("pause_input_clear", not any(self.player.keys.values()), int(any(self.player.keys.values()))))
        self.player.set_paused(False)
        self.dreamer.set_paused(False)

        # Dreamer contract from Pass 02 must survive before final-route recovery.
        # Earlier route tests deliberately mutate world state, so normalize the
        # Dreamer itself here rather than allowing that setup to invalidate the
        # legacy observation/movement regression.
        self.dreamer.release_ready = False
        self.dreamer.released = False
        self.dreamer.root.show()
        self.dreamer.encounter_cooldown = 0.0
        self.dreamer.set_recovery_progress(0.0)
        self._set_view((0.0, 6.8, 0.0), 0.0, 0.0)
        self.dreamer.set_position(0.0, 11.2, 180.0)
        observed = self.dreamer.is_observed_by_player()
        y0 = self.dreamer.root.getY()
        for _ in range(60):
            self.dreamer.simulate_step(1.0 / 60.0, allow_encounter=False)
        freeze_delta = abs(self.dreamer.root.getY() - y0)
        results.append(("dreamer_observed", observed, int(observed)))
        results.append(("dreamer_freezes_when_seen", freeze_delta < 0.001, freeze_delta))

        self._set_view((0.0, 6.8, 0.0), 180.0, 0.0)
        y1 = self.dreamer.root.getY()
        for _ in range(60):
            self.dreamer.simulate_step(1.0 / 60.0, allow_encounter=False)
        unseen_advance = y1 - self.dreamer.root.getY()
        results.append(("dreamer_moves_when_unseen", unseen_advance > 0.70, unseen_advance))
        results.append(("dreamer_stays_walkable", self.world.can_stand(self.dreamer.root.getX(), self.dreamer.root.getY(), radius=0.20), self.dreamer.root.getY()))

        self._set_view((0.0, 6.8, 0.0), 0.0, 0.0)
        seen_again = self.dreamer.is_observed_by_player()
        y2 = self.dreamer.root.getY()
        for _ in range(30):
            self.dreamer.simulate_step(1.0 / 60.0, allow_encounter=False)
        refreeze = abs(self.dreamer.root.getY() - y2)
        results.append(("dreamer_reacquired", seen_again, int(seen_again)))
        results.append(("dreamer_refreezes", refreeze < 0.001, refreeze))

        los_blocked = not self.world.has_clear_line(5.5, 8.0, 0.0, 8.0)
        results.append(("dreamer_wall_occlusion", los_blocked, int(los_blocked)))

        # Relocation is authored, walkable, distant, and moves the Dreamer away.
        self.player.teleport(Point3(0.0, 8.5, 0.0), 0.0)
        before = self.player.root.getPos(self.render)
        cycle_before_relocation = self.world.dream_cycle
        self._perform_datamosh_relocation()
        after = self.player.root.getPos(self.render)
        results.append(("respawn_advances_dream_cycle", self.world.dream_cycle == cycle_before_relocation + 1, self.world.dream_cycle - cycle_before_relocation))
        relocation_distance = (after - before).length()
        dpos = self.dreamer.root.getPos(self.render)
        dreamer_distance = math.hypot(dpos.x - after.x, dpos.y - after.y)
        results.append(("mosh_relocation_distance", relocation_distance >= 5.0, relocation_distance))
        results.append(("mosh_relocation_walkable", self.world.can_stand(after.x, after.y), int(self.world.can_stand(after.x, after.y))))
        results.append(("mosh_dreamer_repositioned", dreamer_distance >= 5.0, dreamer_distance))

        # Full encounter lifecycle: input locks, midpoint relocation fires, effect
        # completes, and both controllers are released again.
        self.player.teleport(Point3(0.0, 8.6, 0.0), 0.0)
        self.dreamer.set_position(0.0, 9.3, 180.0)
        self.player.set_control_locked(True)
        self.dreamer.set_control_locked(True)
        lifecycle_start = self.player.root.getPos(self.render)
        started = self.vision.trigger_datamosh(self._perform_datamosh_relocation, self._finish_datamosh)
        for _ in range(int(self.vision.event_duration * 60.0) + 12):
            self.vision._update_event(1.0 / 60.0)
        lifecycle_end = self.player.root.getPos(self.render)
        lifecycle_distance = (lifecycle_end - lifecycle_start).length()
        results.append(("mosh_event_started", started, int(started)))
        results.append(("mosh_event_completed", not self.vision.active, int(not self.vision.active)))
        results.append(("mosh_event_relocated", lifecycle_distance >= 5.0, lifecycle_distance))
        results.append(("mosh_controls_released", not self.player.control_locked and not self.dreamer.control_locked, int(not self.player.control_locked and not self.dreamer.control_locked)))

        # Pass 13: completing every authored linked recovery destabilizes the intercepted
        # instance.  The Sleeper vanishes through the same temporal-mosh system;
        # no close-range release interaction is required anymore.
        self._sync_dreamer_recovery()
        results.append(("route_reconstructs_sleeper", self.dreamer.release_ready and abs(self.dreamer.recovery_progress - 1.0) < 1e-6, self.dreamer.recovery_progress))
        self.dreamer.release_ready = False
        self._instance_collapse_in_progress = False
        self.world.instance_complete = False
        self.player.set_control_locked(False)
        self.dreamer.set_control_locked(False)
        self._start_instance_collapse()
        collapse_started = self._instance_collapse_in_progress and self.vision.active
        for _ in range(int(self.vision.event_duration * 60.0) + 12):
            self.vision._update_event(1.0 / 60.0)
        results.append(("instance_collapse_event_started", collapse_started, int(collapse_started)))
        results.append(("instance_collapse_hides_sleeper", self.dreamer.released and self.dreamer.root.isHidden(), int(self.dreamer.released)))
        results.append(("instance_collapse_marks_complete", self.world.instance_complete, int(self.world.instance_complete)))
        results.append(("instance_collapse_restores_controls", not self.player.control_locked and not self._instance_collapse_in_progress, int(not self.player.control_locked)))

        # Seeded sub-instance variation: same seed/cycle is deterministic, next
        # cycle changes at least one authored secret-placement signature while
        # preserving a fully connected hand-authored topology.
        self.world.apply_dream_cycle(0, force=True)
        sig_a = self.world.instance_signature
        glasses_a = self.world.glasses_anchor_index
        self.world.apply_dream_cycle(1, force=True)
        sig_b = self.world.instance_signature
        glasses_b = self.world.glasses_anchor_index
        results.append(("instance_variant_deterministic_signature", bool(sig_a and sig_b and sig_a != sig_b), int(sig_a != sig_b)))
        results.append(("instance_glasses_anchor_changes_or_profile_changes", glasses_a != glasses_b or sig_a != sig_b, int(glasses_a != glasses_b)))
        results.append(("false_sleepers_seeded_profile", 2 <= len(self.world._false_sleeper_profile_indices) <= 3, len(self.world._false_sleeper_profile_indices)))
        results.append(("false_sleepers_progress_response", len(self.world._false_sleeper_visible_indices) <= len(self.world._false_sleeper_profile_indices), len(self.world._false_sleeper_visible_indices)))
        results.append(("false_sleepers_are_non_authoritative", all(root.getNumChildren() >= 6 for root in self.world._false_sleeper_roots), len(self.world._false_sleeper_roots)))
        route_before_cycle = self.world.route_signature
        self.world.apply_dream_cycle(2, force=True)
        results.append(("route_frozen_across_dream_cycles", self.world.route_signature == route_before_cycle, int(self.world.route_signature == route_before_cycle)))

        # First recovery exposes a backward-facing seam but the shortcut itself is
        # real before and after the reveal.  No invisible blocker is involved.
        results.append(("memory_seam_revealed_by_recovery", self.world.memory_seam_revealed, int(self.world.memory_seam_revealed)))
        results.append(("memory_seam_shortcut_connected", self.world.path_exists((2, -2), (5, -8)), int(self.world.path_exists((2, -2), (5, -8)))))

        # Force one trace for a deterministic look-away test.  It may be absent in
        # normal seeded play; when present, it vanishes only after Andrew has seen it
        # and then breaks observation.
        if self.world._gleebs_trace_root is not None:
            self.world._gleebs_trace_enabled = True
            self.world._gleebs_trace_seen = False
            self.world._gleebs_trace_vanished = False
            self.world._gleebs_trace_root.setPos(-9.50, 6.82, 0.15)
            self.world._gleebs_trace_root.setH(0.0)
            self.world._gleebs_trace_root.show()
            self.world.update_anomalies(-9.50, 4.35, 2.0, 0.0)
            seen_trace = self.world._gleebs_trace_seen and not self.world._gleebs_trace_vanished
            self.world.update_anomalies(-9.50, 4.35, 2.0, 180.0)
            gone_trace = self.world._gleebs_trace_vanished and self.world._gleebs_trace_root.isHidden()
        else:
            seen_trace = gone_trace = False
        results.append(("gleebs_trace_can_be_seen", seen_trace, int(seen_trace)))
        results.append(("gleebs_trace_vanishes_after_lookaway", gone_trace, int(gone_trace)))

        # Pass 16 Visitor Resonance: deliberate observation is now a useful risk.
        # The mechanic must not move walls or alter collision; it only clarifies
        # perception and world clues for a short authored window.
        self.world.set_resonance_view(False)
        resonance_target = self.world.current_route_target()
        visible_before = self.world.false_sleeper_count
        active_target = self.world.set_resonance_view(True)
        hidden_during = all(root.isHidden() for root in self.world._false_sleeper_roots)
        target_emphasized = False
        if active_target in self.world._target_beacons:
            target_emphasized = any(np.hasColorScale() for np in self.world._target_beacons[active_target])
        self.world.set_resonance_view(False)
        restored_after = self.world.false_sleeper_count == visible_before
        results.append(("pass16_resonance_has_route_target", resonance_target is None or active_target == resonance_target, int(active_target == resonance_target if resonance_target else True)))
        results.append(("pass16_resonance_hides_false_sleepers", hidden_during, int(hidden_during)))
        results.append(("pass16_resonance_emphasizes_world_target", resonance_target is None or target_emphasized, int(target_emphasized)))
        results.append(("pass16_resonance_restores_false_sleepers", restored_after, int(restored_after)))
        self.dreamer.set_resonance_strength(0.75)
        results.append(("pass16_resonance_keeps_continuous_sleeper", self.dreamer._core_mesh is not None and len(self.dreamer._ghosts) == 2, len(self.dreamer._ghosts)))
        self.dreamer.set_resonance_strength(0.0)

        # Glasses are a difficult optional alternate route.  They strip presentation
        # and threat systems from the same geometry and reveal a neutral raw exit.
        # Run this one-way transition last.
        self.world.glasses_collected = False
        if self.world.glasses_root:
            self.world.glasses_root.show()
        entered_null = self.world.enter_null_layer()
        self.vision.set_null_layer(True)
        self.dreamer.enter_null_layer()
        self._apply_cycle_environment()
        sample_surface = self.world._surface_records[0][0]
        results.append(("null_layer_enters", entered_null and self.world.null_layer, int(self.world.null_layer)))
        results.append(("null_layer_bypasses_vision", self.vision.null_layer and self.vision.focus_assist >= 0.99, self.vision.focus_assist))
        results.append(("null_layer_hides_sleeper", self.dreamer.null_layer_hidden and self.dreamer.root.isHidden(), int(self.dreamer.null_layer_hidden)))
        results.append(("null_layer_hides_stabilizers", all(node.root is None or node.root.isHidden() for node in self.world.stability_nodes.values()), int(all(node.root is None or node.root.isHidden() for node in self.world.stability_nodes.values()))))
        results.append(("null_layer_strips_textures", not sample_surface.hasTexture(), int(sample_surface.hasTexture())))
        results.append(("null_exit_visible", self.world._null_exit_root is not None and not self.world._null_exit_root.isHidden(), int(self.world._null_exit_root is not None and not self.world._null_exit_root.isHidden())))
        results.append(("null_exit_reachable", self.world.path_exists((0, 18), (0, 26)), int(self.world.path_exists((0, 18), (0, 26)))))
        self.player.teleport(Point3(0.0, 25.2, 0.0), 0.0)
        near_exit = self.world.null_exit_near(self.player.root.getX(), self.player.root.getY())
        completed_exit = self.world.complete_null_exit()
        results.append(("null_exit_interaction_valid", near_exit and completed_exit and self.world.null_exit_complete, int(completed_exit)))

        payload = {name: {"pass": bool(ok), "value": value} for name, ok, value in results}
        all_ok = all(ok for _, ok, _ in results)
        print("SELF_TEST_JSON=" + json.dumps(payload, sort_keys=True))
        print("SELF_TEST_PASS=" + str(all_ok))
        self.taskMgr.doMethodLater(0.05, lambda t: self.userExit(), "self-test-exit")

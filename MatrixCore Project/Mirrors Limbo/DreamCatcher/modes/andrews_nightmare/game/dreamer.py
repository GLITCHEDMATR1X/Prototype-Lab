from __future__ import annotations

from collections import deque
import math
from pathlib import Path

from panda3d.core import Filename, ClockObject, Point2, Point3, TransparencyAttrib, Vec3


class DreamerController:
    """A distorted humanoid that advances only while genuinely unobserved."""

    def __init__(self, base, world, player, on_encounter=None):
        self.base = base
        self.world = world
        self.player = player
        self.on_encounter = on_encounter
        self.root = base.render.attachNewNode("dreamer-root")
        self.root.setPos(0.0, 12.45, 0.0)
        self.root.setH(180.0)
        self.paused = False
        self.manual_mode = False
        self.control_locked = False
        self.speed = 1.12
        self.contact_distance = 1.02
        self.stop_distance = 0.82
        self.encounter_cooldown = 0.0
        self.repath_interval = 0.22
        self._repath_timer = 0.0
        self._path: list[tuple[int, int]] = []
        self._last_player_cell = None
        self._stride = 0.0
        self._moving = False
        self._observed = False
        self._visual_root = None
        self._ground_holder = None
        self._ceiling_holder = None
        self._ceiling_instance = None
        self._core_mesh = None
        self._ghosts = []
        self._ghost_base_pos = []
        self._ghost_base_color = []
        self.recovery_progress = 0.0
        self.resonance_strength = 0.0
        self.release_ready = False
        self.released = False
        self.null_layer_hidden = False
        self._base_speed = 1.12

        # Pass 17: a close, observed Sleeper can vertically wrap through the
        # room instead of permanently body-blocking a narrow route.  The state
        # is gameplay-authoritative: while the Sleeper is tucked into the
        # ceiling there is no contact hazard at floor level.
        self.ceiling_loop_state = "idle"
        self.ceiling_loop_progress = 0.0
        self._ceiling_trigger_charge = 0.0
        self._ceiling_hold_time = 0.0
        self._ceiling_sink_duration = 2.65
        self._ceiling_return_duration = 2.20
        self._ceiling_trigger_time = 0.62
        self._ceiling_trigger_min = 1.10
        self._ceiling_trigger_max = 2.32
        self._ceiling_release_distance = 3.00
        self._ceiling_clearance_z = 1.90
        self._body_height = 2.505
        self._ceiling_height = float(getattr(self.world, "ceiling_height", 2.58))
        self._build_visual()
        self.base.taskMgr.add(self._update, "dreamer-controller", sort=22)

    @property
    def observed(self) -> bool:
        return self._observed

    def set_paused(self, paused: bool):
        self.paused = paused

    def set_control_locked(self, locked: bool):
        self.control_locked = bool(locked)
        self._moving = False

    def set_encounter_cooldown(self, seconds: float):
        self.encounter_cooldown = max(self.encounter_cooldown, float(seconds))

    def set_recovery_progress(self, progress: float):
        """Calm the Sleeper as linked rooms are recovered without changing its silhouette.

        Pass 15 deliberately keeps the body as one continuous mesh. Recovery is
        communicated with restrained color/registration changes rather than
        swapping or exposing primitive body parts.
        """
        p = max(0.0, min(1.0, float(progress)))
        self.recovery_progress = p
        self.speed = self._base_speed * (1.0 - 0.44 * p)

        if self._core_mesh is not None:
            self._core_mesh.setColor(
                0.018 + 0.12 * p,
                0.016 + 0.23 * p,
                0.024 + 0.28 * p,
                1.0,
            )

        for idx, ghost in enumerate(self._ghosts):
            base_pos = self._ghost_base_pos[idx]
            pull = 1.0 - 0.82 * p
            ghost.setPos(base_pos.x * pull, base_pos.y * pull, base_pos.z * pull)
            r, g, b, a = self._ghost_base_color[idx]
            target = (0.11, 0.55, 0.68)
            ghost.setColor(
                r * (1.0 - p) + target[0] * p,
                g * (1.0 - p) + target[1] * p,
                b * (1.0 - p) + target[2] * p,
                a * (1.0 - 0.88 * p),
            )

    def set_resonance_strength(self, strength: float):
        """Visually show Andrew locking onto the real Sleeper signal.

        The body remains one coherent mesh.  Resonance only changes whole-body
        registration/color so the Pass 15 snowman/primitive regression cannot
        return through this mechanic.
        """
        s = max(0.0, min(1.0, float(strength)))
        self.resonance_strength = s
        if self._visual_root is not None:
            self._visual_root.setColorScale(1.0 - 0.08 * s, 1.0 + 0.34 * s, 1.0 + 0.48 * s, 1.0)
        for ghost in self._ghosts:
            ghost.setColorScale(1.0 - 0.10 * s, 1.0 + 0.70 * s, 1.0 + 0.92 * s, 1.0 + 1.65 * s)

    def set_release_ready(self, ready: bool = True):
        self.release_ready = bool(ready) and not self.released
        if self.release_ready:
            self.set_recovery_progress(1.0)
            self.speed = 0.0
            self.encounter_cooldown = 9999.0
            self._moving = False

    def distance_to_player(self) -> float:
        p = self.player.root.getPos(self.base.render)
        d = self.root.getPos(self.base.render)
        return math.hypot(p.x - d.x, p.y - d.y)

    def can_release(self, max_distance: float = 1.75) -> bool:
        return bool(
            self.release_ready
            and not self.released
            and self.distance_to_player() <= float(max_distance)
            and self.is_observed_by_player()
        )

    def release(self):
        """Remove the reconstructed Dreamer from the live simulation.

        The app calls this at the midpoint of a temporal datamosh event.  Because
        the feedback buffers still contain the previous rendered frames, the
        silhouette persists and smears after the actual entity has disappeared.
        """
        if self.released or self.null_layer_hidden:
            return
        self.released = True
        self.release_ready = False
        self._moving = False
        self.root.hide()

    def enter_null_layer(self):
        self.null_layer_hidden = True
        self._moving = False
        self.root.hide()

    def set_position(self, x: float, y: float, heading: float | None = None):
        self.root.setPos(x, y, 0.0)
        self._reset_ceiling_loop()
        if heading is not None:
            self.root.setH(heading)
        self._path = []
        self._last_player_cell = None
        self._repath_timer = 0.0

    def _load_body_template(self):
        model_path = Path(__file__).resolve().parents[1] / "assets" / "models" / "sleeper_continuous.bam"
        model = self.base.loader.loadModel(Filename.fromOsSpecific(str(model_path)))
        if model.isEmpty():
            raise RuntimeError(f"Sleeper mesh missing or unreadable: {model_path}")
        model.setName("sleeper-continuous-template")
        return model

    def _make_body_node(self, parent, template, name, color, offset=(0.0, 0.0, 0.0), scale=1.0, transparent=False):
        node = template.copyTo(parent)
        node.setName(name)
        node.setPos(*offset)
        node.setScale(scale)
        node.setLightOff(1)
        node.setTwoSided(True)
        node.setColor(*color)
        if transparent:
            node.setTransparency(TransparencyAttrib.MAlpha)
            node.setDepthWrite(False)
            node.setBin("transparent", 29)
        return node

    def _build_visual(self):
        # Two holders show the *same* continuous body graph.  The ground holder
        # sinks below z=0 while an instanced copy is positioned above the real
        # ceiling and descends only where the authored wrap calls for it.
        # Floor/ceiling geometry provides the actual occlusion; there is no
        # billboard, fake portal plane, or replacement primitive.
        self._ground_holder = self.root.attachNewNode("sleeper-ground-holder")
        self._ceiling_holder = self.root.attachNewNode("sleeper-ceiling-holder")
        self._visual_root = self._ground_holder.attachNewNode("sleeper-visual")
        template = self._load_body_template()

        # A single seamless implicit-surface humanoid.  The mesh is generated
        # offline and shipped as Panda3D BAM, so runtime needs no modelling libs.
        # Close or side views cannot expose stacked boxes, spheres, or joint caps.
        self._core_mesh = self._make_body_node(
            self._visual_root, template, "sleeper-continuous-core",
            (0.016, 0.014, 0.022, 1.0),
        )

        # Two restrained whole-body registration echoes preserve the damaged
        # DreamCatcher signal language without duplicating individual body parts.
        shell_specs = [
            ((-0.020, 0.008, 0.003), 1.006, (0.38, 0.055, 0.34, 0.045)),
            ((0.018, -0.006, -0.002), 1.010, (0.035, 0.34, 0.43, 0.036)),
        ]
        for idx, (offset, scale, color) in enumerate(shell_specs):
            ghost = self._make_body_node(
                self._visual_root, template, f"sleeper-registration-{idx}", color,
                offset=offset, scale=scale, transparent=True,
            )
            self._ghosts.append(ghost)
            self._ghost_base_pos.append(Point3(*offset))
            self._ghost_base_color.append(color)
        template.removeNode()

        # Instance the complete visual graph so recovery/resonance coloration and
        # microscopic registration drift remain identical on both sides of the
        # wrap without maintaining a second model implementation.
        self._ceiling_instance = self._visual_root.instanceTo(self._ceiling_holder)
        self._ceiling_holder.hide()
        self._apply_ceiling_loop_visual()

    @property
    def ceiling_passage_open(self) -> bool:
        return bool(self.ceiling_loop_progress >= 0.985 and self.ceiling_loop_state in ("holding", "returning"))

    def _reset_ceiling_loop(self):
        self.ceiling_loop_state = "idle"
        self.ceiling_loop_progress = 0.0
        self._ceiling_trigger_charge = 0.0
        self._ceiling_hold_time = 0.0
        if self._ground_holder is not None:
            self._ground_holder.setZ(0.0)
            self._ground_holder.show()
        if self._ceiling_holder is not None:
            self._ceiling_holder.hide()
            self._ceiling_holder.setZ(self._ceiling_height)

    def _apply_ceiling_loop_visual(self):
        if self._ground_holder is None or self._ceiling_holder is None:
            return
        p = max(0.0, min(1.0, float(self.ceiling_loop_progress)))
        # Smoothstep removes the mechanical constant-speed look.  Most of the
        # travel behaves like a vertical wrap; near completion the ceiling copy
        # retracts upward so its lowest visible point sits above Andrew's head.
        e = p * p * (3.0 - 2.0 * p)
        sink = self._body_height * e
        self._ground_holder.setZ(-sink)

        # Exact wrap position would be ceiling_height - sink.  Blend the final
        # third toward a tucked ceiling position to create honest visual
        # clearance rather than leaving a nearly full-height body in the route.
        wrap_z = self._ceiling_height - sink
        tuck_start = 0.64
        if e <= tuck_start:
            ceiling_z = wrap_z
        else:
            t = (e - tuck_start) / (1.0 - tuck_start)
            t = t * t * (3.0 - 2.0 * t)
            tucked_z = self._ceiling_clearance_z
            ceiling_z = wrap_z * (1.0 - t) + tucked_z * t
        self._ceiling_holder.setZ(ceiling_z)
        if p > 0.015:
            self._ceiling_holder.show()
        else:
            self._ceiling_holder.hide()

    def force_ceiling_loop(self, progress: float, state: str = "holding"):
        """Deterministic QA hook for the authored vertical-wrap state."""
        self.ceiling_loop_progress = max(0.0, min(1.0, float(progress)))
        self.ceiling_loop_state = state if state in ("idle", "sinking", "holding", "returning") else "holding"
        self._ceiling_trigger_charge = 0.0
        self._ceiling_hold_time = 0.0
        self._apply_ceiling_loop_visual()

    def _update_ceiling_loop(self, dt: float, observed: bool, distance: float) -> bool:
        """Advance the floor/ceiling wrap.  Returns True while it owns movement."""
        if self.released or self.release_ready or self.null_layer_hidden:
            self._reset_ceiling_loop()
            return False

        state = self.ceiling_loop_state
        if state == "idle":
            valid = observed and self._ceiling_trigger_min <= distance <= self._ceiling_trigger_max
            if valid:
                self._ceiling_trigger_charge = min(self._ceiling_trigger_time, self._ceiling_trigger_charge + dt)
            else:
                self._ceiling_trigger_charge = max(0.0, self._ceiling_trigger_charge - dt * 1.8)
            if self._ceiling_trigger_charge >= self._ceiling_trigger_time:
                self.ceiling_loop_state = "sinking"
                self._ceiling_trigger_charge = 0.0
                self._ceiling_hold_time = 0.0
                state = "sinking"
            else:
                return False

        if state == "sinking":
            self.ceiling_loop_progress = min(1.0, self.ceiling_loop_progress + dt / self._ceiling_sink_duration)
            if self.ceiling_loop_progress >= 0.9999:
                self.ceiling_loop_progress = 1.0
                self.ceiling_loop_state = "holding"
                self._ceiling_hold_time = 0.0
            self._apply_ceiling_loop_visual()
            return True

        if state == "holding":
            self.ceiling_loop_progress = 1.0
            self._ceiling_hold_time += dt
            self._apply_ceiling_loop_visual()
            # Do not descend onto Andrew.  The Sleeper only reforms after Andrew
            # has cleared the immediate route and the opening has existed long
            # enough to be useful.
            if self._ceiling_hold_time >= 0.85 and distance >= self._ceiling_release_distance:
                self.ceiling_loop_state = "returning"
            return True

        if state == "returning":
            # If Andrew comes back underneath, stay tucked rather than creating an
            # unavoidable contact hazard during the return.
            if distance < 2.38:
                self.ceiling_loop_state = "holding"
                self.ceiling_loop_progress = 1.0
                self._ceiling_hold_time = 0.85
            else:
                self.ceiling_loop_progress = max(0.0, self.ceiling_loop_progress - dt / self._ceiling_return_duration)
                if self.ceiling_loop_progress <= 0.0001:
                    self._reset_ceiling_loop()
                    return False
            self._apply_ceiling_loop_visual()
            return True

        return False

    def _body_sample_points(self):
        x, y, _ = self.root.getPos(self.base.render)
        return [
            Point3(x, y, 2.48),
            Point3(x, y, 2.20),
            Point3(x - 0.30, y, 1.78),
            Point3(x + 0.30, y, 1.78),
            Point3(x, y, 1.50),
            Point3(x - 0.18, y, 0.95),
            Point3(x + 0.18, y, 0.95),
            Point3(x - 0.12, y, 0.25),
            Point3(x + 0.12, y, 0.25),
        ]

    def is_observed_by_player(self) -> bool:
        player_pos = self.player.root.getPos(self.base.render)
        for world_point in self._body_sample_points():
            if not self.world.has_clear_line(player_pos.x, player_pos.y, world_point.x, world_point.y):
                continue
            cam_point = self.base.camera.getRelativePoint(self.base.render, world_point)
            screen = Point2()
            if self.base.camLens.project(cam_point, screen):
                # Lens.project can report points near the clip boundaries; require
                # the sample to be actually inside the visible normalized frame.
                if abs(screen.x) <= 1.02 and abs(screen.y) <= 1.02 and cam_point.y > 0.0:
                    return True
        return False

    def _cell(self, x: float, y: float) -> tuple[int, int]:
        return math.floor(x), math.floor(y)

    def _find_path(self, start: tuple[int, int], goal: tuple[int, int]):
        if start == goal:
            return [start]
        if start not in self.world.walkable or goal not in self.world.walkable:
            return []
        q = deque([start])
        came = {start: None}
        for_current = ((1, 0), (-1, 0), (0, 1), (0, -1))
        while q:
            cur = q.popleft()
            if cur == goal:
                break
            for dx, dy in for_current:
                nxt = (cur[0] + dx, cur[1] + dy)
                if nxt in self.world.walkable and nxt not in came:
                    came[nxt] = cur
                    q.append(nxt)
        if goal not in came:
            return []
        rev = []
        cur = goal
        while cur is not None:
            rev.append(cur)
            cur = came[cur]
        rev.reverse()
        return rev

    def _update_path(self, dt: float):
        self._repath_timer -= dt
        ppos = self.player.root.getPos(self.base.render)
        dpos = self.root.getPos(self.base.render)
        player_cell = self._cell(ppos.x, ppos.y)
        dreamer_cell = self._cell(dpos.x, dpos.y)
        if self._repath_timer <= 0.0 or player_cell != self._last_player_cell or not self._path:
            self._path = self._find_path(dreamer_cell, player_cell)
            self._last_player_cell = player_cell
            self._repath_timer = self.repath_interval

    def _target_point(self):
        dpos = self.root.getPos(self.base.render)
        if len(self._path) >= 2:
            cx, cy = self._path[1]
            return Point3(cx + 0.5, cy + 0.5, 0.0)
        ppos = self.player.root.getPos(self.base.render)
        return Point3(ppos.x, ppos.y, 0.0)

    def _pose_stride(self, moving: bool, dt: float):
        # The Sleeper does not articulate like a mannequin. Its whole silhouette
        # drifts with a restrained gait, which avoids exposing synthetic joints.
        if self._visual_root is None:
            return
        if moving:
            self._stride += dt * 4.4
            phase = math.sin(self._stride)
            self._visual_root.setR(phase * 0.75)
            self._visual_root.setZ(abs(math.sin(self._stride * 0.5)) * 0.010)
        else:
            self._visual_root.setR(self._visual_root.getR() * 0.82)
            self._visual_root.setZ(self._visual_root.getZ() * 0.82)

    def _animate_signal_ghosts(self):
        # Only the two complete-body registration echoes drift microscopically.
        # The core silhouette itself remains physically coherent.
        qa_fixed = bool(getattr(getattr(self.base, 'args', None), 'qa_shot', None))
        t = 2.4 if qa_fixed else ClockObject.getGlobalClock().getFrameTime()
        if self.released:
            return
        for idx, ghost in enumerate(self._ghosts):
            base = self._ghost_base_pos[idx]
            pull = (1.0 - 0.82 * self.recovery_progress) * (1.0 - 0.48 * self.resonance_strength)
            jitter = math.sin(t * (1.55 + idx * 0.24) + idx * 1.7) * 0.0035 * (1.0 - 0.90 * self.recovery_progress) * (1.0 - 0.82 * self.resonance_strength)
            ghost.setX(base.x * pull + jitter)

    def simulate_step(self, dt: float, force_observed: bool | None = None, allow_encounter: bool = True):
        dt = min(float(dt), 0.05)
        self.encounter_cooldown = max(0.0, self.encounter_cooldown - dt)
        if self.released or self.release_ready or self.null_layer_hidden:
            self._moving = False
            return
        if self.paused or self.control_locked:
            self._moving = False
            return

        ppos = self.player.root.getPos(self.base.render)
        dpos = self.root.getPos(self.base.render)
        delta_to_player = Vec3(ppos.x - dpos.x, ppos.y - dpos.y, 0.0)
        distance = delta_to_player.length()

        observed = self.is_observed_by_player() if force_observed is None else bool(force_observed)
        self._observed = observed

        # A close, deliberate gaze can make the Sleeper wrap through the floor
        # and ceiling.  Once fully tucked, Andrew may cross the same XY position
        # safely; before that point touching the Sleeper remains a disturbance.
        phase_owns_motion = self._update_ceiling_loop(dt, observed, distance)
        if allow_encounter and distance <= self.contact_distance and self.encounter_cooldown <= 0.0 and not self.ceiling_passage_open:
            self._moving = False
            self.encounter_cooldown = 2.0
            if self.on_encounter:
                self.on_encounter(self)
            return
        if phase_owns_motion:
            self._moving = False
            self._pose_stride(False, dt)
            return

        if observed:
            self._moving = False
            return

        if distance <= self.stop_distance:
            self._moving = False
            return

        self._update_path(dt)
        target = self._target_point()
        delta = target - dpos
        delta.z = 0.0
        if delta.lengthSquared() < 0.0001:
            self._moving = False
            return
        delta.normalize()
        step = delta * self.speed * dt
        nx, ny = dpos.x + step.x, dpos.y + step.y
        if self.world.can_stand(nx, ny, radius=0.20):
            self.root.setFluidPos(nx, ny, 0.0)
            self.root.setH(math.degrees(math.atan2(-delta.x, delta.y)))
            self._moving = True
            self._pose_stride(True, dt)
        else:
            self._path = []
            self._moving = False

    def _update(self, task):
        self._animate_signal_ghosts()
        if self.manual_mode:
            return task.cont
        self.simulate_step(ClockObject.getGlobalClock().getDt())
        return task.cont

from __future__ import annotations

import math

from panda3d.core import (
    Point3,
    Vec3,
    WindowProperties,
    ClockObject,
)

class FirstPersonController:
    def __init__(self, base, world, spawn_pos: Point3, spawn_heading: float, settings: dict, input_enabled=True):
        self.base = base
        self.settings = settings
        self.world = world
        self.input_enabled = input_enabled
        self.root = base.render.attachNewNode("player-root")
        self.root.setPos(spawn_pos)
        self.root.setH(spawn_heading)
        base.camera.reparentTo(self.root)
        base.camera.setPos(0, 0, 1.63)
        base.camera.setHpr(0, 0, 0)
        base.camLens.setFov(settings["fov"])
        base.camLens.setNearFar(0.05, 75.0)

        self.heading = spawn_heading
        self.pitch = 0.0
        self.eye_height = 1.63
        self.target_eye_height = 1.63
        self.vertical_velocity = 0.0
        self.grounded = True
        self.paused = False
        self.control_locked = False
        self.manual_mode = False
        self.keys = {k: False for k in ("forward", "back", "left", "right", "sprint", "crouch")}


        if input_enabled:
            self._bind_inputs()
            self.capture_mouse(True)
        self.base.taskMgr.add(self._update, "fps-controller", sort=15)

    def _bind_inputs(self):
        binds = {
            "w": "forward", "s": "back", "a": "left", "d": "right",
            "shift": "sprint", "control": "crouch",
        }
        for key, action in binds.items():
            self.base.accept(key, self._set_key, [action, True])
            self.base.accept(f"{key}-up", self._set_key, [action, False])
        self.base.accept("space", self.jump)

    def _set_key(self, action, value):
        if not self.paused:
            self.keys[action] = value

    def clear_inputs(self):
        for k in self.keys:
            self.keys[k] = False

    def jump(self):
        if not self.paused and self.grounded and not self.keys["crouch"]:
            self.vertical_velocity = 4.0
            self.grounded = False

    def set_paused(self, paused: bool):
        self.paused = paused
        self.clear_inputs()
        if self.input_enabled:
            self.capture_mouse(not paused)

    def set_control_locked(self, locked: bool):
        self.control_locked = bool(locked)
        if locked:
            self.clear_inputs()

    def teleport(self, pos: Point3, heading: float):
        self.root.setPos(pos)
        self.root.setH(heading)
        self.heading = float(heading)
        self.pitch = 0.0
        self.base.camera.setP(0.0)
        self.vertical_velocity = 0.0
        self.grounded = True

    def capture_mouse(self, capture: bool):
        if not self.base.win:
            return
        props = WindowProperties()
        props.setCursorHidden(capture)
        props.setMouseMode(WindowProperties.MConfined if capture else WindowProperties.MAbsolute)
        self.base.win.requestProperties(props)
        if capture:
            self._recenter_pointer()

    def _recenter_pointer(self):
        if not self.base.win:
            return
        props = self.base.win.getProperties()
        if props.getXSize() > 0 and props.getYSize() > 0:
            self.base.win.movePointer(0, props.getXSize() // 2, props.getYSize() // 2)

    def _mouse_look(self):
        if not self.input_enabled or self.paused or not self.base.win:
            return
        watcher = self.base.mouseWatcherNode
        if not watcher.hasMouse():
            return
        props = self.base.win.getProperties()
        cx, cy = props.getXSize() // 2, props.getYSize() // 2
        pointer = self.base.win.getPointer(0)
        dx = pointer.getX() - cx
        dy = pointer.getY() - cy
        if dx or dy:
            sensitivity = self.settings["mouse_sensitivity"]
            self.heading -= dx * sensitivity
            invert = -1.0 if self.settings.get("invert_y") else 1.0
            self.pitch = max(-84.0, min(84.0, self.pitch - dy * sensitivity * invert))
            self.root.setH(self.heading)
            self.base.camera.setP(self.pitch)
            self.base.win.movePointer(0, cx, cy)

    def simulate_step(self, dt: float, mouse_look: bool = False):
        dt = min(float(dt), 0.05)
        if mouse_look:
            self._mouse_look()
        if self.paused or self.control_locked:
            return

        # Camera crouch is smoothed; collision footprint stays stable.
        crouching = self.keys["crouch"]
        self.target_eye_height = 1.18 if crouching else 1.63
        self.eye_height += (self.target_eye_height - self.eye_height) * min(1.0, dt * 13.0)
        self.base.camera.setZ(self.eye_height)

        local = Vec3(0, 0, 0)
        if self.keys["forward"]: local.y += 1
        if self.keys["back"]: local.y -= 1
        if self.keys["right"]: local.x += 1
        if self.keys["left"]: local.x -= 1
        if local.lengthSquared() > 0:
            local.normalize()
        speed = 1.65 if crouching else (4.65 if self.keys["sprint"] else 2.65)
        h = math.radians(self.heading)
        world = Vec3(local.x * math.cos(h) - local.y * math.sin(h), local.x * math.sin(h) + local.y * math.cos(h), 0)
        delta = world * speed * dt
        pos = self.root.getPos()
        # Axis-separated resolution gives predictable wall sliding. The world grid is the same authority that generated walls.
        nx = pos.x + delta.x
        if self.world.can_stand(nx, pos.y):
            pos.x = nx
        ny = pos.y + delta.y
        if self.world.can_stand(pos.x, ny):
            pos.y = ny
        self.root.setFluidPos(pos)

        # Flat-floor prototype: gravity/jump authority is deterministic and frame-rate independent.
        if not self.grounded or self.vertical_velocity > 0:
            self.vertical_velocity -= 10.8 * dt
            z = self.root.getZ() + self.vertical_velocity * dt
            if z <= 0.0:
                z = 0.0
                self.vertical_velocity = 0.0
                self.grounded = True
            self.root.setZ(z)

    def _update(self, task):
        if self.manual_mode:
            return task.cont
        dt = min(ClockObject.getGlobalClock().getDt(), 0.05)
        self.simulate_step(dt, mouse_look=True)
        return task.cont

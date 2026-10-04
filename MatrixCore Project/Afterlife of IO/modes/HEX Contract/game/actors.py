from __future__ import annotations

import math
import pygame

from .data import HEROES, ENEMY_ARCHETYPES, CIVILIAN_ROLES
from .actor_visuals import CIVILIAN_STYLE

Vec2 = pygame.Vector2


def _pt(v: Vec2 | tuple[float, float]) -> tuple[int, int]:
    return (int(round(v[0])), int(round(v[1])))


def _poly(surface: pygame.Surface, color, points, width: int = 0) -> None:
    pts = [_pt(p) for p in points]
    pygame.draw.polygon(surface, color, pts, width)
    if width == 0 and len(pts) >= 3:
        pygame.draw.aalines(surface, color, True, pts)


def _aaline(surface: pygame.Surface, color, a, b, width: int = 1) -> None:
    if width <= 1:
        pygame.draw.aaline(surface, color, _pt(a), _pt(b))
    else:
        pygame.draw.line(surface, color, _pt(a), _pt(b), width)


def _glow_line(surface: pygame.Surface, color, a, b, width: int = 2) -> None:
    """Readable neon line with a dark structural under-stroke."""
    _aaline(surface, (3, 7, 15), a, b, max(2, width + 4))
    _aaline(surface, color, a, b, width)


def _joint(surface: pygame.Surface, pos, outer, inner=(8, 14, 24), radius: int = 5) -> None:
    pygame.draw.circle(surface, outer, _pt(pos), radius)
    pygame.draw.circle(surface, inner, _pt(pos), max(1, radius - 2))
    pygame.draw.circle(surface, outer, _pt(pos), radius, 1)


def _filled_limb(surface: pygame.Surface, a, b, fill, edge, width: int = 7, edge_width: int = 2) -> None:
    """Draw an armored/cloth limb as a filled capsule instead of a stick line."""
    a2, b2 = Vec2(a), Vec2(b)
    width = max(4, int(width))
    pygame.draw.line(surface, fill, _pt(a2), _pt(b2), width)
    radius = max(2, width // 2)
    pygame.draw.circle(surface, fill, _pt(a2), radius)
    pygame.draw.circle(surface, fill, _pt(b2), radius)
    if edge_width > 0:
        pygame.draw.line(surface, edge, _pt(a2), _pt(b2), min(width, max(1, edge_width)))
        pygame.draw.circle(surface, edge, _pt(a2), radius, max(1, edge_width))
        pygame.draw.circle(surface, edge, _pt(b2), radius, max(1, edge_width))


def _boot(surface: pygame.Surface, foot, right: Vec2, fill, edge, scale: float = 1.0) -> None:
    foot = Vec2(foot)
    r = right * (7 * scale)
    f = Vec2(-right.y, right.x) * (5 * scale)
    _poly(surface, fill, [foot-r-f, foot+r-f, foot+r+f, foot-r*0.7+f])
    _poly(surface, edge, [foot-r-f, foot+r-f, foot+r+f, foot-r*0.7+f], max(1, int(2*scale)))


def _armor_panel(surface: pygame.Surface, center, forward: Vec2, right: Vec2, half_w: float, half_h: float, fill, edge, notch: float = 0.0) -> None:
    c = Vec2(center)
    pts = [
        c-forward*half_h-right*(half_w-notch),
        c-forward*(half_h*0.72)+right*half_w,
        c+forward*half_h+right*(half_w*0.78),
        c+forward*half_h-right*(half_w*0.78),
    ]
    _poly(surface, fill, pts)
    _poly(surface, edge, pts, 2)


class ActorArtist:
    """Procedural actor silhouettes shared by roster, world, and dossier views."""

    def __init__(self):
        self._portrait_cache: dict[tuple[str, int, str], pygame.Surface] = {}

    @staticmethod
    def _basis(facing: Vec2) -> tuple[Vec2, Vec2]:
        forward = Vec2(facing)
        if forward.length_squared() < 0.01:
            forward = Vec2(0, 1)
        forward = forward.normalize()
        right = Vec2(-forward.y, forward.x)
        return forward, right

    def _damage_marks(self, surface, pos: Vec2, color, ratio: float, scale: float, time: float) -> None:
        if ratio >= 0.72:
            return
        amount = 1 if ratio >= 0.42 else 3
        for i in range(amount):
            angle = 0.7 + i * 1.9
            start = pos + Vec2(math.cos(angle), math.sin(angle)) * (8 + i * 3) * scale
            end = start + Vec2(math.cos(angle + 1.1), math.sin(angle + 1.1)) * 9 * scale
            _aaline(surface, (255, 110, 132), start, end, max(1, int(2 * scale)))
        if ratio < 0.32:
            pulse = 2 + int(2 * (0.5 + 0.5 * math.sin(time * 12)))
            pygame.draw.circle(surface, (255, 72, 112), _pt(pos + Vec2(9, -7) * scale), pulse)

    def _kit_overlay(self, surface: pygame.Surface, mission, pos: Vec2, forward: Vec2, right: Vec2, scale: float, time: float) -> None:
        kit = getattr(mission, "equipment_key", "ampoule")
        if kit == "aegis":
            for sign in (-1, 1):
                shoulder = pos - forward * 11 * scale + right * sign * 17 * scale
                plate = [shoulder-forward*7*scale, shoulder+right*sign*7*scale, shoulder+forward*6*scale, shoulder-right*sign*4*scale]
                _poly(surface, (68, 53, 30), plate)
                _poly(surface, (255, 205, 92), plate, max(1, int(2*scale)))
            pygame.draw.arc(surface, (255, 205, 92), pygame.Rect(int(pos.x-34*scale), int(pos.y-34*scale), int(68*scale), int(68*scale)), time % math.tau, (time % math.tau)+1.7, max(1, int(2*scale)))
        elif kit == "surveyor":
            pack = pos - forward * 4 * scale - right * 16 * scale
            pygame.draw.rect(surface, (8, 25, 32), pygame.Rect(int(pack.x-6*scale), int(pack.y-9*scale), int(12*scale), int(18*scale)), border_radius=max(1,int(3*scale)))
            pygame.draw.rect(surface, (94, 238, 255), pygame.Rect(int(pack.x-6*scale), int(pack.y-9*scale), int(12*scale), int(18*scale)), max(1,int(2*scale)), border_radius=max(1,int(3*scale)))
            mast = pack - forward * 16 * scale
            _glow_line(surface, (94, 238, 255), pack, mast, max(1, int(2*scale)))
            pygame.draw.arc(surface, (94, 238, 255), pygame.Rect(int(mast.x-12*scale), int(mast.y-12*scale), int(24*scale), int(24*scale)), -1.2, 1.2, max(1,int(2*scale)))
        elif kit == "beacon":
            relay = pos + right * 17 * scale - forward * 5 * scale
            pygame.draw.circle(surface, (7, 24, 25), _pt(relay), max(4,int(7*scale)))
            pygame.draw.circle(surface, (96, 255, 190), _pt(relay), max(4,int(7*scale)), max(1,int(2*scale)))
            for i in range(3):
                ang = time * 1.8 + i * math.tau / 3
                pip = relay + Vec2(math.cos(ang), math.sin(ang)) * 11 * scale
                pygame.draw.circle(surface, (96, 255, 190), _pt(pip), max(1,int(2*scale)))
        else:
            vial = pos + forward * 7 * scale + right * 13 * scale
            pygame.draw.rect(surface, (28, 12, 42), pygame.Rect(int(vial.x-3*scale), int(vial.y-7*scale), max(3,int(6*scale)), max(7,int(14*scale))), border_radius=max(1,int(2*scale)))
            pygame.draw.rect(surface, (220, 102, 255), pygame.Rect(int(vial.x-3*scale), int(vial.y-7*scale), max(3,int(6*scale)), max(7,int(14*scale))), max(1,int(2*scale)), border_radius=max(1,int(2*scale)))
            pygame.draw.circle(surface, (245, 196, 255), _pt(vial + forward*2*scale), max(1,int(2*scale)))

    def draw_hero_world(self, surface: pygame.Surface, mission, time: float, hero=None) -> None:
        h = hero if hero is not None else mission.hero
        spec = HEROES[h.key]
        pos = Vec2(h.pos)
        forward, right = self._basis(h.facing)
        scale = float(spec.get("actor_scale", 1.0))
        stride = math.sin(h.walk_phase) * (5.5 if h.velocity.length_squared() > 20 else 1.0)
        attack = 1.0 if h.pose in {"SLASH", "FIRE", "PHASE", "WARD", "OVERRIDE", "CHANNEL", "REANIMATE"} else 0.0
        anim = int(getattr(h, "anim_frame", 0))
        frame_wave = (-1.0, -0.25, 0.65, 0.2)[anim % 4]

        # Ground shadow only. Pass 22 removes persistent selection rings/footprints
        # around actors; identity now comes from the actor silhouette and labels.
        shadow = pygame.Rect(0, 0, int(50 * scale), int(25 * scale))
        shadow.center = _pt(pos + Vec2(7, 11))
        pygame.draw.ellipse(surface, (0, 0, 0), shadow)

        hip = pos + forward * 2
        left_foot = hip - right * 8 * scale - forward * stride * scale
        right_foot = hip + right * 8 * scale + forward * stride * scale
        body = pos - forward * (8 + frame_wave * (2.0 if h.pose in {"MOVE", "RUN"} else 0.7)) * scale
        head = pos - forward * 24 * scale + right * frame_wave * (1.4 if h.pose in {"FIRE", "SLASH", "REANIMATE"} else 0.5) * scale

        if h.key == "nyx":
            # Split cloak tails and lean synthetic limbs.
            tail_l = hip - forward * 18 * scale - right * (7 + stride * 0.3) * scale
            tail_r = hip - forward * 18 * scale + right * (7 - stride * 0.3) * scale
            _poly(surface, (27, 14, 45), [body-right*11*scale, body+right*11*scale, tail_r, hip, tail_l])
            _aaline(surface, spec["accent"], hip, tail_l, max(2, int(3*scale)))
            _aaline(surface, spec["color"], hip, tail_r, max(2, int(3*scale)))
            _filled_limb(surface, hip-right*5, left_foot, (45, 54, 76), spec["color"], max(6, int(8*scale)), max(1, int(2*scale)))
            _filled_limb(surface, hip+right*5, right_foot, (45, 54, 76), spec["accent"], max(6, int(8*scale)), max(1, int(2*scale)))
            _poly(surface, (18, 25, 43), [body-forward*13*scale, body-right*13*scale, hip+right*10*scale, hip+forward*5*scale, hip-right*10*scale])
            _poly(surface, spec["color"], [body-forward*12*scale, body-right*13*scale, hip-right*8*scale], 2)
            slash_angles = (-8, -34, -68, -28)
            weapon_dir = forward.rotate(slash_angles[anim] if h.pose == "SLASH" else -12)
            hand = body + right * 13 * scale + forward * 2
            blade_end = hand + weapon_dir * (33 + attack * 15) * scale
            _aaline(surface, (234, 242, 255), hand, blade_end, max(2, int(4*scale)))
            _aaline(surface, spec["accent"], hand, blade_end, max(1, int(2*scale)))
            # Off-hand curse pistol.
            pistol_hand = body - right * 12 * scale
            _aaline(surface, (120, 132, 164), body, pistol_hand, max(2, int(5*scale)))
            _aaline(surface, spec["color"], pistol_hand, pistol_hand + forward * 12 * scale, max(2, int(4*scale)))
            # Hood and visor.
            pygame.draw.circle(surface, (12, 13, 27), _pt(head), int(12*scale))
            _poly(surface, (29, 18, 48), [head-forward*14*scale, head+right*13*scale, head+forward*10*scale, head-right*13*scale])
            _aaline(surface, spec["color"], head-right*7*scale, head+right*7*scale, max(1, int(3*scale)))
            pygame.draw.circle(surface, (245, 255, 255), _pt(head + right*4*scale), max(1, int(2*scale)))
            _glow_line(surface, spec["accent"], body-forward*7*scale, hip+forward*1*scale, max(1, int(2*scale)))
            _aaline(surface, (110, 86, 142), body-right*8*scale, hip+right*8*scale, max(1,int(2*scale)))
            pygame.draw.circle(surface, spec["accent"], _pt(body-right*9*scale), max(2,int(4*scale)), 1)
            _joint(surface, body+right*13*scale, spec["color"], radius=max(3,int(5*scale)))
            _joint(surface, body-right*12*scale, spec["accent"], radius=max(3,int(5*scale)))
            if h.pose == "SLASH":
                trail_end = blade_end + right * 9 * scale
                _aaline(surface, (170, 90, 255), hand-forward*5*scale, trail_end, max(1,int(2*scale)))

        elif h.key == "circuit":
            # Heavy armored legs, broad torso, hammer and prayer drone.
            _filled_limb(surface, hip-right*8, left_foot, (69, 67, 65), spec["color"], max(9, int(11*scale)), max(1, int(2*scale)))
            _filled_limb(surface, hip+right*8, right_foot, (69, 67, 65), spec["color"], max(9, int(11*scale)), max(1, int(2*scale)))
            torso = [body-forward*15*scale, body-right*19*scale, hip+right*15*scale, hip+forward*6*scale, hip-right*15*scale]
            _poly(surface, (74, 61, 38), torso)
            _poly(surface, spec["color"], torso, max(2, int(3*scale)))
            # Shoulder reliquaries.
            for sign in (-1, 1):
                shoulder = body + right * sign * 20 * scale
                pygame.draw.circle(surface, (24, 34, 48), _pt(shoulder), int(8*scale))
                pygame.draw.circle(surface, spec["accent"], _pt(shoulder), int(8*scale), 2)
            # Arc hammer across the body.
            hammer_angles = (12, -18, -54, -12)
            swing = hammer_angles[anim] if h.pose in {"STRIKE", "WARD"} else 8
            hammer_dir = forward.rotate(swing)
            hand = body + right * 8 * scale
            haft_end = hand + hammer_dir * (37 + attack * 8) * scale
            _aaline(surface, (173, 160, 124), hand, haft_end, max(3, int(5*scale)))
            hammer_right = Vec2(-hammer_dir.y, hammer_dir.x)
            _aaline(surface, spec["color"], haft_end-hammer_right*10*scale, haft_end+hammer_right*10*scale, max(5, int(9*scale)))
            # Head/halo.
            pygame.draw.circle(surface, (40, 40, 46), _pt(head), int(11*scale))
            pygame.draw.arc(surface, spec["accent"], pygame.Rect(int(head.x-18*scale), int(head.y-18*scale), int(36*scale), int(36*scale)), math.pi, math.tau, 3)
            pygame.draw.circle(surface, spec["color"], _pt(head), int(11*scale), 2)
            pygame.draw.circle(surface, spec["accent"], _pt(head-forward*2*scale), max(1,int(3*scale)))
            _glow_line(surface, spec["accent"], body-forward*10*scale, hip+forward*2*scale, max(1,int(2*scale)))
            _aaline(surface, spec["color"], body-right*10*scale, body+right*10*scale, max(1,int(2*scale)))
            _aaline(surface, spec["color"], body-forward*3*scale, hip+forward*3*scale, max(1,int(2*scale)))
            _joint(surface, body+right*20*scale, spec["accent"], radius=max(4,int(6*scale)))
            _joint(surface, body-right*20*scale, spec["accent"], radius=max(4,int(6*scale)))
            # Orbiting prayer drone.
            orbit = pos + Vec2(math.cos(time*2.2), math.sin(time*2.2)) * 35 * scale
            pygame.draw.circle(surface, (8, 17, 25), _pt(orbit), int(7*scale))
            pygame.draw.circle(surface, spec["accent"], _pt(orbit), int(7*scale), 2)
            _aaline(surface, spec["accent"], orbit-Vec2(5,0)*scale, orbit+Vec2(5,0)*scale, 2)

        elif h.key == "morrow":
            # Funerary synth: split robe, exposed conduit ribs, gravecaster staff.
            _filled_limb(surface, hip-right*7, left_foot, (67, 50, 73), spec["color"], max(7, int(9*scale)), max(1, int(2*scale)))
            _filled_limb(surface, hip+right*7, right_foot, (67, 50, 73), spec["accent"], max(7, int(9*scale)), max(1, int(2*scale)))
            robe = [body-forward*15*scale, body+right*16*scale, hip+right*12*scale,
                    hip+forward*17*scale, hip-right*12*scale, body-right*16*scale]
            _poly(surface, (43, 19, 42), robe)
            _poly(surface, spec["color"], robe, 2)
            for rib in (-8, 0, 8):
                _aaline(surface, spec["accent"], body-right*10*scale+forward*rib*0.35,
                        body+right*10*scale+forward*rib*0.35, max(1, int(2*scale)))
            # Death mask and suspended reliquary rings.
            pygame.draw.circle(surface, (24, 16, 29), _pt(head), int(12*scale))
            _poly(surface, (80, 42, 69), [head-forward*12*scale, head+right*10*scale,
                                         head+forward*11*scale, head-right*10*scale])
            _aaline(surface, spec["color"], head-right*7*scale, head+right*7*scale, max(1, int(3*scale)))
            pygame.draw.circle(surface, (248,255,248), _pt(head-right*3*scale), max(1,int(2*scale)))
            for radius in (15, 21):
                pygame.draw.arc(surface, spec["accent"], pygame.Rect(int(body.x-radius*scale), int(body.y-radius*scale), int(radius*2*scale), int(radius*2*scale)), time*1.2+radius, time*1.2+radius+1.55, 2)
            # Hooked gravecaster staff with four-frame casting motion.
            staff_angle = (-18, -34, -52, -27)[anim] if h.pose == "REANIMATE" else -12
            staff_dir = forward.rotate(staff_angle)
            hand = body + right*13*scale
            staff_end = hand + staff_dir*(38+attack*7)*scale
            _aaline(surface, (157, 122, 151), hand, staff_end, max(3,int(5*scale)))
            hook_right = Vec2(-staff_dir.y, staff_dir.x)
            _aaline(surface, spec["color"], staff_end, staff_end-forward*8*scale+hook_right*11*scale, max(2,int(4*scale)))
            pygame.draw.circle(surface, spec["accent"], _pt(staff_end), max(3,int(6*scale)), 2)
            # Shard sickle at the hip.
            sickle = hip-right*13*scale
            _glow_line(surface, spec["accent"], sickle, sickle+forward*15*scale, max(1,int(2*scale)))
            if h.pose == "REANIMATE":
                pulse = 31 + int(5*math.sin(time*14))
                pygame.draw.circle(surface, spec["accent"], _pt(pos), int(pulse*scale), 2)
                for k in range(4):
                    ang = time*2.5 + k*math.tau/4
                    mote = pos + Vec2(math.cos(ang), math.sin(ang))*pulse*scale
                    pygame.draw.circle(surface, spec["color"], _pt(mote), max(2,int(3*scale)))

        else:  # Vesper
            # Long mantle, slim limbs, recurved smartbow.
            _filled_limb(surface, hip-right*5, left_foot, (35, 57, 58), spec["color"], max(6, int(8*scale)), max(1, int(2*scale)))
            _filled_limb(surface, hip+right*5, right_foot, (35, 57, 58), spec["accent"], max(6, int(8*scale)), max(1, int(2*scale)))
            mantle = [body-forward*13*scale, body+right*12*scale, hip+right*8*scale, hip-forward*20*scale, hip-right*8*scale, body-right*12*scale]
            _poly(surface, (18, 39, 39), mantle)
            _poly(surface, spec["accent"], mantle, 2)
            # Bow held across facing direction.
            hand = body + forward * 2 * scale
            bow_axis = right.rotate((8, 14, 22, 12)[anim] if h.pose == "FIRE" else 0)
            a = hand - bow_axis * 25 * scale
            b = hand + bow_axis * 25 * scale
            _aaline(surface, spec["color"], a, b, max(2, int(3*scale)))
            curve = forward * 10 * scale
            _aaline(surface, spec["accent"], a, hand+curve, 1)
            _aaline(surface, spec["accent"], b, hand+curve, 1)
            if h.pose in {"FIRE", "OVERRIDE"}:
                _aaline(surface, (240, 255, 245), hand-curve, hand+forward*32*scale, 2)
            pygame.draw.circle(surface, (10, 23, 25), _pt(head), int(10*scale))
            _aaline(surface, spec["color"], head-right*7*scale, head+right*7*scale, max(1, int(3*scale)))
            # Sensor braid.
            braid = [head-forward*8*scale-right*8*scale, body-right*16*scale, hip-right*18*scale]
            pygame.draw.aalines(surface, spec["accent"], False, [_pt(p) for p in braid])
            # Quiver, data dagger, layered mantle clasp, and optic detail.
            quiver = body - right*12*scale + forward*3*scale
            _aaline(surface, (68, 122, 104), quiver-forward*9*scale, quiver+forward*12*scale, max(2,int(4*scale)))
            for k in (-4, 0, 4):
                _aaline(surface, spec["color"], quiver-right*k*scale-forward*11*scale, quiver-right*k*scale-forward*17*scale, 1)
            dagger_a = hip + right*8*scale
            _glow_line(surface, spec["accent"], dagger_a, dagger_a+forward*13*scale, max(1,int(2*scale)))
            pygame.draw.circle(surface, spec["accent"], _pt(body), max(2,int(4*scale)), 1)
            pygame.draw.circle(surface, (245,255,245), _pt(head+right*3*scale), max(1,int(2*scale)))
            _joint(surface, body+right*11*scale, spec["color"], radius=max(3,int(4*scale)))

        self._kit_overlay(surface, mission, pos, forward, right, scale, time)

        # Feet and shared status treatment.
        _boot(surface, left_foot, right, (24, 33, 47), spec["color"], scale)
        _boot(surface, right_foot, right, (24, 33, 47), spec["accent"], scale)
        for foot in (left_foot, right_foot):
            pygame.draw.circle(surface, (130, 145, 168), _pt(foot-forward*2*scale), max(1, int(2*scale)))
        ratio = h.hp / max(1.0, h.max_hp)
        self._damage_marks(surface, pos, spec["color"], ratio, scale, time)
        if h.shield_timer > 0:
            radius = int((34 + 2*math.sin(time*8)) * scale)
            pygame.draw.circle(surface, spec["accent"], _pt(pos), radius, 3)
        if h.hit_flash > 0:
            pygame.draw.circle(surface, (255, 255, 255), _pt(pos), int(30*scale), 2)

    def draw_enemy_world(self, surface: pygame.Surface, enemy, time: float, variant: dict | None = None) -> None:
        if enemy.dead:
            return
        pos = Vec2(enemy.pos)
        forward, right = self._basis(enemy.facing)
        variant = variant or {}
        color = variant.get("color", enemy.color)
        accent = variant.get("accent", color)
        is_boss = bool(getattr(enemy, "is_boss", False))
        boss_scale = 1.24 if is_boss else 1.0
        stride = math.sin(enemy.walk_phase) * 4 * boss_scale
        shadow = pygame.Rect(0, 0, int(enemy.radius*2.45*boss_scale), int(enemy.radius*1.2*boss_scale))
        shadow.center = _pt(pos + Vec2(6, 10))
        pygame.draw.ellipse(surface, (0, 0, 0), shadow)

        if enemy.kind == "revenant":
            hip = pos + forward*5
            lfoot = hip-right*7-forward*stride
            rfoot = hip+right*7+forward*stride
            _filled_limb(surface, hip-right*5, lfoot, (58, 34, 48), color, int(8*boss_scale), 2)
            _filled_limb(surface, hip+right*5, rfoot, (58, 34, 48), color, int(8*boss_scale), 2)
            _boot(surface, lfoot, right, (30, 20, 28), color, 0.85*boss_scale)
            _boot(surface, rfoot, right, (30, 20, 28), color, 0.85*boss_scale)
            torso = [pos-forward*18*boss_scale, pos-right*14*boss_scale,
                     hip+right*11*boss_scale, hip+forward*7*boss_scale, hip-right*11*boss_scale]
            _poly(surface, (42, 17, 30), torso)
            _poly(surface, color, torso, max(2, int(2*boss_scale)))
            # Ragged vestment panels give the corpse a readable body volume.
            for sign in (-1, 1):
                panel = [pos+right*sign*4-forward*8,
                         pos+right*sign*13-forward*2,
                         hip+right*sign*10+forward*9,
                         hip+right*sign*2+forward*12]
                _poly(surface, (63, 26, 43), panel)
                _poly(surface, accent, panel, 1)
            head = pos-forward*27*boss_scale
            pygame.draw.circle(surface, (25, 8, 18), _pt(head), int(10*boss_scale))
            # Broken face plate / visible signal eye.
            face = [head-forward*8*boss_scale, head+right*8*boss_scale,
                    head+forward*7*boss_scale, head-right*8*boss_scale]
            _poly(surface, (58, 26, 39), face)
            _poly(surface, color, face, 2)
            pygame.draw.circle(surface, (255, 205, 218), _pt(head+right*3), max(2, int(2*boss_scale)))
            for rib in (-7, 0, 7):
                _aaline(surface, (139, 55, 83), pos-right*8+forward*rib*0.25,
                        pos+right*8+forward*rib*0.25, 2)
            # Both arms are filled; the weapon arm carries a broad cleaver.
            off_hand = pos-right*15+forward*3
            hand = pos+right*16-forward*2
            _filled_limb(surface, pos-right*9, off_hand, (73, 37, 53), color, int(8*boss_scale), 2)
            _filled_limb(surface, pos+right*9, hand, (73, 37, 53), color, int(9*boss_scale), 2)
            weapon_dir = forward.rotate(-35 if enemy.pose == "STRIKE" else 8)
            weapon = hand + weapon_dir*(27*boss_scale)
            _aaline(surface, (123, 72, 86), hand, weapon, max(3, int(5*boss_scale)))
            blade_right = Vec2(-weapon_dir.y, weapon_dir.x)
            blade = [weapon-blade_right*5, weapon+blade_right*10-forward*4,
                     weapon+blade_right*8+forward*11, weapon-blade_right*7+forward*7]
            _poly(surface, (111, 43, 59), blade)
            _poly(surface, color, blade, 2)

        elif enemy.kind == "construct":
            # Reverse-jointed plated legs and a wider machine chassis.
            for sign in (-1, 1):
                upper = pos + right*sign*13 + forward*8
                knee = upper + right*sign*5 + forward*10
                foot = knee + right*sign*5 + forward*(12+stride*sign)
                _filled_limb(surface, upper, knee, (92, 80, 55), color, int(9*boss_scale), 2)
                _filled_limb(surface, knee, foot, (62, 58, 49), accent, int(8*boss_scale), 2)
                _boot(surface, foot, right*sign, (39, 38, 34), color, 0.9*boss_scale)
            core = [pos-forward*20*boss_scale, pos+right*20*boss_scale,
                    pos+forward*16*boss_scale, pos-right*20*boss_scale]
            _poly(surface, (43, 37, 27), core)
            _poly(surface, color, core, max(2, int(3*boss_scale)))
            # Layered shoulder plates stop the construct reading as a diamond icon.
            for sign in (-1, 1):
                shoulder = pos + right*sign*19 - forward*4
                _armor_panel(surface, shoulder, forward, right*sign, 10*boss_scale, 8*boss_scale,
                             (65, 56, 40), accent, 2)
            chest = pos-forward*4
            pygame.draw.circle(surface, (255, 235, 150), _pt(chest), int(7*boss_scale))
            pygame.draw.circle(surface, (255,255,225), _pt(chest), max(2,int(3*boss_scale)))
            # Cannon arm and stabilizer arm.
            cannon_root = pos+right*17-forward*2
            cannon_end = cannon_root + forward*(31 if enemy.pose == "FIRE" else 25)*boss_scale
            _filled_limb(surface, pos+right*10, cannon_root, (72, 65, 48), color, int(9*boss_scale), 2)
            pygame.draw.line(surface, (63, 58, 47), _pt(cannon_root), _pt(cannon_end), max(8,int(10*boss_scale)))
            pygame.draw.line(surface, color, _pt(cannon_root), _pt(cannon_end), 2)
            support_hand = pos-right*23+forward*5
            _filled_limb(surface, pos-right*10, support_hand, (72, 65, 48), accent, int(8*boss_scale), 2)
            pygame.draw.circle(surface, accent, _pt(support_hand), max(4,int(5*boss_scale)), 2)
            # Low armored head with a horizontal sensor slit.
            head = pos-forward*23*boss_scale
            _armor_panel(surface, head, forward, right, 12*boss_scale, 7*boss_scale, (27, 28, 29), color, 3)
            _aaline(surface, accent, head-right*7*boss_scale, head+right*7*boss_scale, max(2,int(3*boss_scale)))

        else:  # cantor
            hover = math.sin(time*3 + enemy.pulse) * 3
            p = pos + Vec2(0, hover)
            robe = [p-forward*23*boss_scale, p+right*19*boss_scale,
                    p+forward*24*boss_scale, p-right*19*boss_scale]
            _poly(surface, (35, 15, 50), robe)
            _poly(surface, color, robe, max(2,int(3*boss_scale)))
            # Split vestment panels and filled sleeves establish a complete figure.
            for sign in (-1, 1):
                panel = [p+right*sign*3-forward*4, p+right*sign*16+forward*4,
                         p+right*sign*10+forward*24, p+right*sign*2+forward*19]
                _poly(surface, (52, 24, 68), panel)
                _poly(surface, accent, panel, 1)
            core = p-forward*6*boss_scale
            pygame.draw.circle(surface, (18, 9, 25), _pt(core), int(12*boss_scale))
            pygame.draw.circle(surface, color, _pt(core), int(12*boss_scale), max(2,int(3*boss_scale)))
            pygame.draw.circle(surface, (245, 220, 255), _pt(core), max(2,int(3*boss_scale)))
            head = p-forward*25*boss_scale
            _poly(surface, (23, 10, 34), [head-forward*9, head+right*10, head+forward*8, head-right*10])
            _poly(surface, color, [head-forward*9, head+right*10, head+forward*8, head-right*10], 2)
            # Floating sleeves, visible hands, and the resonance staff.
            staff_hand = p+right*20-forward*2
            off_hand = p-right*20+forward*1
            _filled_limb(surface, p+right*10, staff_hand, (50, 24, 67), color, int(8*boss_scale), 2)
            _filled_limb(surface, p-right*10, off_hand, (50, 24, 67), accent, int(8*boss_scale), 2)
            staff_end = staff_hand-forward*(33*boss_scale)
            _aaline(surface, (165, 126, 192), staff_hand, staff_end, max(3,int(5*boss_scale)))
            pygame.draw.circle(surface, color, _pt(staff_end), max(6,int(8*boss_scale)), 2)
            pygame.draw.circle(surface, accent, _pt(off_hand), max(3,int(4*boss_scale)), 2)
            for ring in (18, 25):
                pygame.draw.arc(surface, accent, pygame.Rect(int(core.x-ring), int(core.y-ring), ring*2, ring*2), time*0.8, time*0.8+1.4, 2)
            if enemy.pose == "CHANNEL":
                pygame.draw.circle(surface, color, _pt(p), int(33*boss_scale+3*math.sin(time*12)), 2)

        # Contract livery is body-mounted rather than a floating label.
        mark = variant.get("mark", "")
        if mark == "EMBER CROWN":
            crown = pos-forward*32
            for a in (-1, 0, 1):
                _poly(surface, accent, [crown+right*a*8-forward*8, crown+right*(a*8+5), crown+right*(a*8-5)])
        elif mark == "HYMN SHIELDS":
            for sign in (-1, 1):
                shield = pos + right*sign*28
                _poly(surface, (54, 43, 31), [shield-forward*11, shield+right*sign*8, shield+forward*11, shield-right*sign*5])
                _poly(surface, accent, [shield-forward*11, shield+right*sign*8, shield+forward*11, shield-right*sign*5], 2)
        elif mark == "FLAME HALO":
            pygame.draw.arc(surface, accent, pygame.Rect(int(pos.x-25), int(pos.y-48), 50, 34), math.pi, math.tau, 4)
        elif mark == "SHARD MASK":
            for sign in (-1, 1):
                _poly(surface, (35, 22, 49), [pos-forward*30, pos-forward*19+right*sign*14, pos-forward*8+right*sign*5])
                _poly(surface, accent, [pos-forward*30, pos-forward*19+right*sign*14, pos-forward*8+right*sign*5], 2)
        elif mark == "INDEX FINS":
            for sign in (-1, 1):
                pts = [pos+right*sign*19-forward*13, pos+right*sign*31, pos+right*sign*18+forward*13]
                _poly(surface, (32, 26, 50), pts)
                _poly(surface, accent, pts, 2)
        elif mark == "MEMORY RINGS":
            for radius in (20, 29):
                pygame.draw.arc(surface, accent, pygame.Rect(int(pos.x-radius), int(pos.y-radius-10), radius*2, radius*2), time*1.8+radius, time*1.8+radius+1.7, 2)
        elif mark == "CHAIN COLLAR":
            pygame.draw.arc(surface, accent, pygame.Rect(int(pos.x-17), int(pos.y-32), 34, 25), 0.1, 3.05, 4)
            _filled_limb(surface, pos+right*12-forward*14, pos+right*21+forward*9, (64,47,44), accent, 5, 1)
        elif mark == "WARNING CAGE":
            for sign in (-1, 1):
                side = [pos+right*sign*20-forward*17, pos+right*sign*27-forward*11,
                        pos+right*sign*27+forward*16, pos+right*sign*20+forward*19]
                _poly(surface, (62, 50, 31), side)
                _poly(surface, accent, side, 2)
        elif mark == "PANIC TENDRILS":
            for k in range(3):
                ang = time*1.7 + k*2.1
                mid = pos + Vec2(math.cos(ang), math.sin(ang))*18
                end = pos + Vec2(math.cos(ang+0.3), math.sin(ang+0.3))*32
                _filled_limb(surface, pos, mid, (53,25,67), accent, 5, 1)
                _filled_limb(surface, mid, end, (53,25,67), accent, 4, 1)

        if is_boss:
            boss_id = getattr(enemy, "boss_id", "")
            # Each sovereign now owns additional body geometry instead of only an aura.
            if boss_id == "ash_saint":
                # Processional shoulder reliquaries and split execution mantle.
                for sign in (-1, 1):
                    plate = pos + right*sign*26-forward*3
                    _armor_panel(surface, plate, forward, right*sign, 11, 15, (56, 30, 31), accent, 3)
                cape = [pos-right*22-forward*8, pos+right*22-forward*8,
                        pos+right*17+forward*34, pos+forward*25, pos-right*17+forward*34]
                _poly(surface, (48, 18, 24), cape)
                _poly(surface, color, cape, 2)
                pygame.draw.arc(surface, accent, pygame.Rect(int(pos.x-43), int(pos.y-65), 86, 55), math.pi, math.tau, 5)
            elif boss_id == "mirror_abbot":
                # Filled obsidian mirror wings act as a stable visual body, not thin line fins.
                for sign in (-1, 1):
                    wing = pos + right*sign*24
                    pts = [wing-forward*28, wing+right*sign*24-forward*8,
                           wing+right*sign*18+forward*24, wing+forward*13]
                    _poly(surface, (23, 21, 39), pts)
                    _poly(surface, accent, pts, 3)
                    _aaline(surface, color, wing-forward*20, wing+right*sign*14+forward*15, 2)
                pygame.draw.circle(surface, (15,22,31), _pt(pos-forward*4), 18)
                pygame.draw.circle(surface, accent, _pt(pos-forward*4), 18, 3)
                pygame.draw.circle(surface, (230,252,255), _pt(pos-forward*4), 5)
            elif boss_id == "last_conductor":
                # Long transit coat, shoulder route boards, and a solid signal crown.
                coat = [pos-forward*23, pos+right*23, pos+right*16+forward*34,
                        pos+forward*27, pos-right*16+forward*34, pos-right*23]
                _poly(surface, (24,45,45), coat)
                _poly(surface, color, coat, 3)
                for sign in (-1,1):
                    board = pos+right*sign*28-forward*5
                    pygame.draw.rect(surface, (42,45,37), pygame.Rect(int(board.x-7), int(board.y-13), 14, 26), border_radius=3)
                    pygame.draw.rect(surface, accent, pygame.Rect(int(board.x-7), int(board.y-13), 14, 26), 2, border_radius=3)
                crown = pos-forward*39
                _poly(surface, (45,42,28), [crown-right*21, crown-right*12-forward*13,
                                             crown, crown+right*12-forward*13, crown+right*21, crown+forward*6])
                _poly(surface, accent, [crown-right*21, crown-right*12-forward*13,
                                        crown, crown+right*12-forward*13, crown+right*21, crown+forward*6], 3)

            # No persistent boss aura rings. Small seal motes remain attached to
            # the sovereign design without encircling the whole actor.
            for k in range(4):
                ang = time * (0.55 if enemy.boss_phase == 1 else 1.1) + k * math.tau / 4
                seal = pos + Vec2(math.cos(ang), math.sin(ang)) * (enemy.radius + 18)
                pygame.draw.rect(surface, accent, pygame.Rect(int(seal.x-2), int(seal.y-2), 5, 5), 1)

        ratio = max(0.0, enemy.hp / max(1.0, enemy.max_hp))
        self._damage_marks(surface, pos, color, ratio, 1.0 if is_boss else 0.8, time)
        if enemy.overridden > 0:
            # Angular override ticks replace the old full actor ring.
            r = int(enemy.radius + 10)
            for dx, dy in ((-r,-r),(r,-r),(-r,r),(r,r)):
                pygame.draw.rect(surface, (104, 255, 180), pygame.Rect(int(pos.x+dx-2), int(pos.y+dy-2), 5, 5), 1)
        if enemy.hit_flash > 0:
            r = int(enemy.radius + 8)
            pygame.draw.line(surface, (255,255,255), (int(pos.x-r),int(pos.y-r)), (int(pos.x-r+8),int(pos.y-r)), 2)
            pygame.draw.line(surface, (255,255,255), (int(pos.x+r-8),int(pos.y-r)), (int(pos.x+r),int(pos.y-r)), 2)

    def draw_civilian_world(self, surface: pygame.Surface, civ, time: float) -> None:
        if civ.extracted:
            return
        spec = CIVILIAN_ROLES[civ.role_index % len(CIVILIAN_ROLES)]
        style = CIVILIAN_STYLE[civ.role_index % len(CIVILIAN_STYLE)]
        pos = Vec2(civ.pos)
        forward, right = self._basis(civ.facing)
        rescued_color = (96, 255, 212)
        accent = rescued_color if civ.rescued else style["accent"]
        stride = math.sin(civ.walk_phase) * 3.0
        shadow = pygame.Rect(0, 0, 34, 16)
        shadow.center = _pt(pos + Vec2(4, 8))
        pygame.draw.ellipse(surface, (0, 0, 0), shadow)

        hip = pos + forward * 4
        left_foot = hip - right * 5 + forward * (11 + stride)
        right_foot = hip + right * 5 + forward * (11 - stride)
        _filled_limb(surface, hip-right*4, left_foot, (52, 58, 66), accent, 6, 1)
        _filled_limb(surface, hip+right*4, right_foot, (52, 58, 66), accent, 6, 1)
        _boot(surface, left_foot, right, (31, 37, 43), accent, 0.72)
        _boot(surface, right_foot, right, (31, 37, 43), accent, 0.72)

        body = pos - forward * 5
        head = pos - forward * 20
        coat = style["coat"]
        cloth = style["cloth"]

        if civ.role_index % 3 == 0:  # Archive pilgrim
            mantle = [body-forward*10, body-right*10, hip+right*9, hip+forward*9, hip-right*9]
            _poly(surface, coat, mantle)
            _poly(surface, accent, mantle, 2)
            # Pale archive mantle and hood give a readable pilgrim identity.
            _poly(surface, cloth, [body-forward*11, body-right*8, body+forward*1, body-right*8])
            pygame.draw.circle(surface, (153, 151, 148), _pt(head), 7)
            _poly(surface, coat, [head-forward*9, head+right*9, head+forward*7, head-right*9])
            _aaline(surface, accent, head-right*5, head+right*5, 2)
            # Sealed testimony case worn on the outside of the body.
            case = body + right*12 + forward*3
            pygame.draw.rect(surface, (34, 69, 88), pygame.Rect(int(case.x-6), int(case.y-8), 12, 16), border_radius=2)
            pygame.draw.rect(surface, accent, pygame.Rect(int(case.x-6), int(case.y-8), 12, 16), 2, border_radius=2)
            _aaline(surface, accent, case-Vec2(3,0), case+Vec2(3,0), 1)

        elif civ.role_index % 3 == 1:  # Choir defector
            robe = [body-forward*10, body+right*10, hip+right*8, hip+forward*12, hip-right*8, body-right*10]
            _poly(surface, coat, robe)
            _poly(surface, accent, robe, 2)
            # Broken choir sash is intentionally asymmetric.
            sash_a = body-right*7-forward*5
            sash_b = hip+right*7+forward*5
            _filled_limb(surface, sash_a, sash_b, cloth, accent, 5, 1)
            pygame.draw.circle(surface, (150, 141, 132), _pt(head), 7)
            _poly(surface, coat, [head-forward*8, head+right*8, head+forward*7, head-right*8])
            insignia = body + right*10 - forward*1
            pygame.draw.circle(surface, accent, _pt(insignia), 5, 2)
            _aaline(surface, (30, 20, 24), insignia-Vec2(4,4), insignia+Vec2(4,4), 2)

        else:  # Relic medic
            coat_poly = [body-forward*10, body+right*10, hip+right*9, hip+forward*10, hip-right*9, body-right*10]
            _poly(surface, cloth, coat_poly)
            _poly(surface, accent, coat_poly, 2)
            inner = [body-forward*6, body+right*6, hip+right*5, hip-right*5, body-right*6]
            _poly(surface, coat, inner)
            pygame.draw.circle(surface, (167, 155, 145), _pt(head), 7)
            # Medical cap and cross create a role read even at world scale.
            _poly(surface, cloth, [head-forward*8-right*7, head-forward*9+right*6, head-right*7])
            cross = body - forward*1
            _aaline(surface, accent, cross-right*4, cross+right*4, 2)
            _aaline(surface, accent, cross-forward*4, cross+forward*4, 2)
            satchel = body + right*13 + forward*4
            pygame.draw.rect(surface, (31, 67, 53), pygame.Rect(int(satchel.x-6), int(satchel.y-6), 12, 12), border_radius=3)
            pygame.draw.rect(surface, accent, pygame.Rect(int(satchel.x-6), int(satchel.y-6), 12, 12), 2, border_radius=3)

        # Filled arms keep civilians from reading as symbols while preserving the same simulation footprint.
        left_hand = body-right*12+forward*3
        right_hand = body+right*12+forward*3
        _filled_limb(surface, body-right*7, left_hand, coat, accent, 6, 1)
        _filled_limb(surface, body+right*7, right_hand, coat, accent, 6, 1)
        pygame.draw.circle(surface, (172, 160, 150), _pt(left_hand), 3)
        pygame.draw.circle(surface, (172, 160, 150), _pt(right_hand), 3)

        if civ.rescued:
            # Rescued civilians use a compact chevron instead of a surrounding ring.
            y = int(pos.y - 34)
            x = int(pos.x)
            pygame.draw.lines(surface, rescued_color, False, [(x-7,y+5),(x,y),(x+7,y+5)], 2)
        elif civ.panic > 0.55:
            pygame.draw.arc(surface, (255, 116, 130), pygame.Rect(int(pos.x-22), int(pos.y-31), 44, 44), math.pi*1.12, math.pi*1.88, 2)
            # A small raised-arm panic pose is readable but does not change collision.
            _filled_limb(surface, body+right*7, head+right*13, coat, (255,116,130), 5, 1)

    def portrait(self, hero_key: str, size: int = 180, equipment_key: str = "ampoule") -> pygame.Surface:
        """Cached front-facing dossier portrait with readable costume and kit detail."""
        key = (hero_key, size, equipment_key)
        cached = self._portrait_cache.get(key)
        if cached is not None:
            return cached
        native = 220
        surf = pygame.Surface((native, native), pygame.SRCALPHA)
        spec = HEROES[hero_key]
        color, accent = spec["color"], spec["accent"]
        cx = native // 2
        # Shared ground glow and torso anchor.
        pygame.draw.ellipse(surf, (0, 0, 0, 130), pygame.Rect(28, 178, 164, 28))
        pygame.draw.ellipse(surf, (*color, 80), pygame.Rect(40, 184, 140, 18), 2)

        if hero_key == "nyx":
            # Split cloak and lean phase chassis.
            _poly(surf, (28, 14, 47), [(47, 188), (64, 93), (110, 71), (156, 93), (175, 188), (126, 172), (110, 203), (94, 172)])
            _poly(surf, color, [(64, 95), (110, 72), (156, 95), (150, 165), (70, 165)], 3)
            _poly(surf, (13, 16, 31), [(76, 111), (110, 93), (144, 111), (135, 161), (85, 161)])
            # Hood and mask.
            _poly(surf, (31, 18, 52), [(71, 92), (78, 39), (110, 22), (142, 39), (149, 92), (126, 111), (94, 111)])
            pygame.draw.ellipse(surf, (9, 13, 25), pygame.Rect(82, 48, 56, 52))
            _glow_line(surf, color, (88, 74), (132, 74), 4)
            pygame.draw.circle(surf, (245, 255, 255), (126, 74), 3)
            # Chest phase spine and shoulder nodes.
            _glow_line(surf, accent, (110, 107), (110, 161), 3)
            for x, c in ((77, color), (143, accent)):
                _joint(surf, (x, 111), c, radius=8)
            pygame.draw.rect(surf, (80, 61, 104), pygame.Rect(83, 145, 54, 12), border_radius=4)
            # Sword and curse pistol silhouette.
            _glow_line(surf, (238, 245, 255), (154, 168), (188, 45), 6)
            _glow_line(surf, accent, (154, 168), (188, 45), 2)
            pygame.draw.rect(surf, (28, 42, 59), pygame.Rect(33, 126, 42, 16), border_radius=4)
            pygame.draw.rect(surf, color, pygame.Rect(33, 126, 42, 16), 2, border_radius=4)
            _aaline(surf, accent, (65, 166), (42, 198), 3)
            _aaline(surf, color, (155, 166), (178, 198), 3)

        elif hero_key == "circuit":
            # Monumental reliquary plate and hammer.
            _poly(surf, (70, 57, 36), [(31, 193), (42, 98), (73, 73), (110, 64), (147, 73), (178, 98), (189, 193)])
            _poly(surf, color, [(42, 100), (74, 75), (110, 66), (146, 75), (178, 100), (166, 181), (54, 181)], 4)
            for x in (48, 172):
                pygame.draw.circle(surf, (20, 32, 46), (x, 105), 24)
                pygame.draw.circle(surf, accent, (x, 105), 24, 4)
                pygame.draw.circle(surf, color, (x, 105), 12, 2)
            # Helmet, face lamp, and halo.
            pygame.draw.circle(surf, (37, 38, 45), (110, 52), 34)
            pygame.draw.circle(surf, color, (110, 52), 34, 4)
            pygame.draw.arc(surf, accent, pygame.Rect(64, 6, 92, 92), math.pi, math.tau, 5)
            pygame.draw.rect(surf, (16, 23, 30), pygame.Rect(84, 45, 52, 25), border_radius=8)
            pygame.draw.circle(surf, (226, 255, 255), (110, 57), 6)
            # Chest reliquary.
            _poly(surf, (18, 28, 36), [(82, 111), (110, 88), (138, 111), (126, 161), (94, 161)])
            _poly(surf, accent, [(82, 111), (110, 88), (138, 111), (126, 161), (94, 161)], 3)
            _glow_line(surf, color, (110, 102), (110, 154), 4)
            _glow_line(surf, color, (91, 130), (129, 130), 4)
            # Hammer behind shoulder.
            _glow_line(surf, (174, 162, 126), (165, 184), (187, 44), 7)
            pygame.draw.rect(surf, color, pygame.Rect(160, 28, 51, 23), border_radius=4)
            pygame.draw.rect(surf, (255, 241, 178), pygame.Rect(160, 28, 51, 23), 2, border_radius=4)
            # Prayer drone.
            pygame.draw.circle(surf, (8, 17, 25), (42, 55), 14)
            pygame.draw.circle(surf, accent, (42, 55), 14, 3)
            _aaline(surf, accent, (34, 55), (50, 55), 2)

        elif hero_key == "morrow":
            # Tall mourning plate with a visible echo reliquary and hooked staff.
            _poly(surf, (42, 18, 41), [(42, 194), (58, 92), (110, 67), (162, 92), (178, 194), (132, 176), (110, 207), (88, 176)])
            _poly(surf, color, [(58, 94), (110, 68), (162, 94), (151, 177), (69, 177)], 3)
            _poly(surf, (18, 22, 31), [(78, 111), (110, 88), (142, 111), (132, 166), (88, 166)])
            for y in (112, 128, 144):
                _glow_line(surf, accent, (88, y), (132, y), 2)
            # Rose death mask.
            _poly(surf, (68, 35, 60), [(77, 91), (82, 41), (110, 21), (138, 41), (143, 91), (125, 108), (95, 108)])
            pygame.draw.ellipse(surf, (12, 14, 21), pygame.Rect(84, 49, 52, 47))
            _glow_line(surf, color, (89, 72), (131, 72), 4)
            pygame.draw.circle(surf, (245, 255, 250), (99, 72), 3)
            # Suspended reliquary rings.
            for r in (31, 43):
                pygame.draw.arc(surf, accent, pygame.Rect(110-r, 101-r, r*2, r*2), -0.7, 1.6, 3)
            pygame.draw.circle(surf, color, (110, 130), 7, 2)
            # Gravecaster staff and hooked blade.
            _glow_line(surf, (159, 124, 153), (166, 190), (190, 46), 7)
            _aaline(surf, color, (190, 46), (204, 63), 5)
            _aaline(surf, color, (204, 63), (188, 74), 5)
            pygame.draw.circle(surf, accent, (190, 46), 8, 3)
            # Shard sickle and shoulder conduits.
            _glow_line(surf, accent, (55, 164), (35, 199), 3)
            for x in (65, 155):
                _joint(surf, (x, 111), accent, radius=7)

        else:
            # Layered infiltrator mantle, smartbow and sensor braid.
            _poly(surf, (16, 38, 38), [(48, 192), (62, 91), (110, 69), (158, 91), (172, 192), (130, 173), (110, 204), (90, 173)])
            _poly(surf, accent, [(62, 92), (110, 70), (158, 92), (148, 171), (72, 171)], 3)
            _poly(surf, (9, 24, 27), [(79, 111), (110, 90), (141, 111), (132, 161), (88, 161)])
            # Hood and optic.
            _poly(surf, (14, 32, 34), [(76, 91), (82, 41), (110, 24), (138, 41), (144, 91), (125, 105), (95, 105)])
            pygame.draw.ellipse(surf, (6, 18, 21), pygame.Rect(85, 50, 50, 44))
            _glow_line(surf, color, (89, 73), (131, 73), 4)
            pygame.draw.circle(surf, (245, 255, 245), (123, 73), 3)
            # Bow across the chest.
            pygame.draw.arc(surf, color, pygame.Rect(34, 91, 152, 110), -1.25, 1.25, 5)
            _aaline(surf, accent, (56, 112), (164, 176), 2)
            _aaline(surf, accent, (164, 112), (56, 176), 2)
            _glow_line(surf, (232, 255, 240), (110, 137), (179, 137), 3)
            # Quiver and braid.
            pygame.draw.rect(surf, (28, 65, 58), pygame.Rect(45, 117, 17, 65), border_radius=5)
            pygame.draw.rect(surf, color, pygame.Rect(45, 117, 17, 65), 2, border_radius=5)
            for x in (48, 53, 58):
                _aaline(surf, color, (x, 122), (x-5, 96), 1)
            pygame.draw.aalines(surf, accent, False, [(89, 86), (72, 125), (66, 179), (80, 201)])
            pygame.draw.circle(surf, accent, (110, 118), 6, 2)

        # Equipment-specific portrait attachment.
        if equipment_key == "aegis":
            for x in (66, 154):
                _poly(surf, (70, 54, 30), [(x-16, 105), (x, 91), (x+16, 105), (x+9, 128), (x-9, 128)])
                _poly(surf, (255, 205, 92), [(x-16, 105), (x, 91), (x+16, 105), (x+9, 128), (x-9, 128)], 3)
            pygame.draw.arc(surf, (255, 205, 92), pygame.Rect(37, 35, 146, 146), -0.2, 1.45, 3)
        elif equipment_key == "surveyor":
            pygame.draw.rect(surf, (8, 25, 32), pygame.Rect(31, 72, 24, 50), border_radius=5)
            pygame.draw.rect(surf, (94, 238, 255), pygame.Rect(31, 72, 24, 50), 3, border_radius=5)
            _glow_line(surf, (94, 238, 255), (43, 72), (43, 35), 3)
            pygame.draw.arc(surf, (94, 238, 255), pygame.Rect(23, 16, 40, 40), -1.3, 1.3, 3)
        elif equipment_key == "beacon":
            pygame.draw.circle(surf, (7, 24, 25), (177, 121), 16)
            pygame.draw.circle(surf, (96, 255, 190), (177, 121), 16, 3)
            for ang in (0, 2.1, 4.2):
                pygame.draw.circle(surf, (96, 255, 190), (int(177+24*math.cos(ang)), int(121+24*math.sin(ang))), 4)
        else:
            pygame.draw.rect(surf, (32, 12, 44), pygame.Rect(151, 154, 13, 35), border_radius=4)
            pygame.draw.rect(surf, (220, 102, 255), pygame.Rect(151, 154, 13, 35), 3, border_radius=4)
            pygame.draw.circle(surf, (245, 196, 255), (157, 177), 3)

        portrait = pygame.transform.smoothscale(surf, (size, size)) if size != native else surf
        self._portrait_cache[key] = portrait
        return portrait

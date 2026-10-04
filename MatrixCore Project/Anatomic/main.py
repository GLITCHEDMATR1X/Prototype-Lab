from __future__ import annotations
import argparse, json, math, random, sys, traceback, os, time, tempfile, faulthandler
from pathlib import Path

# Historical regression compatibility is preserved beneath Pass 45.
# Pass 45 builds on Pass 44 while preserving Motion Dynamics, Body Solver, Motion Forge and Combo Composer authority.
ROOT = Path(__file__).resolve().parent
HOLOVERSE_EMBEDDED = str(os.environ.get('ANATOMIC_HOLOVERSE_EMBEDDED', '')).strip().lower() in {'1','true','yes','on'}


def _runtime_log_dir():
    try:
        if os.name == 'nt':
            base = Path(os.environ.get('LOCALAPPDATA') or (Path.home() / 'AppData' / 'Local'))
            path = base / 'GLITCHED MATRIX' / 'ASCII Matter Lab' / 'logs'
        else:
            path = Path.home() / '.glitched_matrix' / 'ascii_matter_lab' / 'logs'
        path.mkdir(parents=True, exist_ok=True)
        return path
    except Exception:
        path = Path(tempfile.gettempdir()) / 'glitched_matrix_ascii_matter_logs'
        path.mkdir(parents=True, exist_ok=True)
        return path


RUNTIME_LOG_DIR = _runtime_log_dir()
CHECKPOINT_PATH = RUNTIME_LOG_DIR / 'startup_state.json'
CRASH_LOG_PATH = RUNTIME_LOG_DIR / 'crash.log'
NATIVE_FAULT_PATH = RUNTIME_LOG_DIR / 'native_fault.log'
_FAULT_HANDLE = None
# faulthandler is process-global. Standalone Anatomic may own it, but an embedded
# dimension must not replace HoloVerse's crash/fault reporting destination.
if not HOLOVERSE_EMBEDDED:
    try:
        _FAULT_HANDLE = NATIVE_FAULT_PATH.open('a', encoding='utf-8')
        faulthandler.enable(file=_FAULT_HANDLE, all_threads=True)
    except Exception:
        _FAULT_HANDLE = None


def _checkpoint(stage, detail=''):
    try:
        CHECKPOINT_PATH.write_text(json.dumps({
            'schema': 'ascii_matter.startup.v1',
            'time': time.time(),
            'pid': os.getpid(),
            'stage': str(stage),
            'detail': str(detail),
        }, indent=2), encoding='utf-8')
    except Exception:
        pass


def _write_crash_report(exc, stage='runtime'):
    try:
        CRASH_LOG_PATH.write_text(
            'Anatomic Pass 47 crash report\n'
            + f'stage={stage}\n'
            + f'{type(exc).__name__}: {exc}\n\n'
            + traceback.format_exc(),
            encoding='utf-8'
        )
        print(f'ASCII_MATTER_CRASH_LOG={CRASH_LOG_PATH}', file=sys.stderr)
    except Exception:
        pass


def parse_args():
    p = argparse.ArgumentParser(description='Anatomic Pass 47 - in-place HoloVerse same-window authority with preserved Pass 45 gait authority')
    p.add_argument('--smoke-test', action='store_true')
    p.add_argument('--combat-smoke', action='store_true', help='Engine smoke: exercise all rifle modes, impacts, fragments, and rewind')
    p.add_argument('--impact-smoke', action='store_true', help='Engine smoke: verify weapon-scaled body/head impact springs')
    p.add_argument('--perf-smoke', action='store_true', help='Engine smoke: report hotpath counters and render LOD state')
    p.add_argument('--reverse-perf-smoke', action='store_true', help='Engine smoke: damage, rewind, damage again, and verify pooled fragments/color-only rewind')
    p.add_argument('--rig-smoke', action='store_true', help='Engine smoke: articulate rig joints, verify bound body movement, then restore rest pose')
    p.add_argument('--head-track-smoke', action='store_true', help='Engine smoke: drive the player around the NPC and verify bounded neck swivel parenting')
    p.add_argument('--arm-smoke', action='store_true', help='Engine smoke: bend each elbow independently and verify torso/opposite arm isolation plus finger inheritance')
    p.add_argument('--shoulder-smoke', action='store_true', help='Engine smoke: articulate each shoulder above the elbow chain and verify torso/opposite-arm isolation plus descendant inheritance')
    p.add_argument('--walk-smoke', action='store_true', help='Engine smoke: drive the NPC through a deterministic walking cycle, turn, and verify leg/body parenting')
    p.add_argument('--fps-control-smoke', action='store_true', help='Engine smoke: verify Panda3D camera-relative WASD across cardinal headings, yaw/pitch stability, spawn facing, acceleration/deceleration, crouch, buffered jump, and NPC collision')
    p.add_argument('--test-shot', type=str, default='')
    p.add_argument('--proof', choices=('intact', 'damaged', 'rewind'), default='intact')
    p.add_argument('--width', type=int, default=1920)
    p.add_argument('--height', type=int, default=1080)
    p.add_argument('--fullscreen', action='store_true')
    p.add_argument('--windowed', action='store_true', help='Force a normal window; accepted by Prototype Lab/GPTOOL launch contracts')
    p.add_argument('--no-audio', action='store_true', help='Disable all audio; accepted by GPTOOL/smoke-test launch contracts')
    p.add_argument('--audio-diagnostic', action='store_true', help='Play overlapping weapon cues, print the selected backend, then exit')
    p.add_argument('--melee-smoke', action='store_true', help='Engine smoke: verify holo arms, direct/gesture punches, melee damage, stagger and defense')
    p.add_argument('--melee-proof', action='store_true', help='Render proof with holo fists raised and a charged left-hand trajectory')
    p.add_argument('--melee-impact-proof', action='store_true', help='Render proof of a charged melee impact, wound, stagger and defensive brace')
    p.add_argument('--sword-smoke', action='store_true', help='Engine smoke: verify spaced arms, right-hand laser sword reach, FX, bone cut and reversible dismemberment')
    p.add_argument('--sword-proof', action='store_true', help='Render 1080p proof with naturally spaced arms and the right-hand laser sword raised')
    p.add_argument('--dismember-proof', action='store_true', help='Render 1080p proof of a sword-cut limb with connected ASCII matter detached')
    p.add_argument('--pass34-smoke', action='store_true', help='Engine smoke: verify wider FOV, held reach extension, enemy-assisted forward commit and held sword wrist cant')
    p.add_argument('--pass34-proof', action='store_true', help='Render 1080p proof of the wider FOV and charged extended sword pose')
    p.add_argument('--pass37-smoke', action='store_true', help='Engine smoke: verify inherited wider FOV, vector steering, air momentum, jump timing, landing recovery and locomotion sway')
    p.add_argument('--pass37-proof', action='store_true', help='Render proof of Pass 37 wider framing and locomotion-ready melee pose')
    p.add_argument('--pass38-smoke', action='store_true', help='Engine smoke: verify melee release begins at the live held pose and sword flurry animates before forward commit')
    p.add_argument('--pass38-proof', action='store_true', help='Render proof of the release-origin laser-sword wrist flurry in motion')
    p.add_argument('--pass39-smoke', action='store_true', help='Engine smoke: verify 88-degree FOV, full held-path memory, stronger melee contact/impact and wound ASCII spill')
    p.add_argument('--pass39-proof', action='store_true', help='Render proof of a dramatic melee wound with red ASCII spill and wider framing')
    p.add_argument('--pass40-smoke', action='store_true', help='Engine smoke: verify full local-transform replay at 1.5x, numbered sword slots, doubled sword impact and velocity distortion')
    p.add_argument('--pass40-proof', action='store_true', help='Render proof of a saved sword recording replay with distortion ribbons')
    p.add_argument('--pass41-smoke', action='store_true', help='Engine smoke: verify Body Solver shoulder/torso/hip support preserves recorded hand path and returns cleanly to rest')
    p.add_argument('--pass41-proof', action='store_true', help='Render proof of a recorded sword swing with procedural whole-body support')
    p.add_argument('--pass42-smoke', action='store_true', help='Engine smoke: verify blade-speed, edge-alignment and leverage-driven sword impact dynamics')
    p.add_argument('--pass42-proof', action='store_true', help='Render proof of a high-energy clean-edge recorded sword impact')
    p.add_argument('--pass43-smoke', action='store_true', help='Engine smoke: verify Motion Forge trim, mirror, speed, rename, persistence and non-destructive reset')
    p.add_argument('--pass43-proof', action='store_true', help='Render proof of the temporary Motion Forge editor with an authored sword slot selected')
    p.add_argument('--pass44-smoke', action='store_true', help='Engine smoke: verify Combo Composer persistence, velocity-aware bridges, non-damaging transitions and multi-move playback')
    p.add_argument('--pass44-proof', action='store_true', help='Render proof of the temporary Combo Composer with a three-move authored chain')
    p.add_argument('--pass45-smoke', action='store_true', help='Engine smoke: verify joint-map knee direction, swing-only flex, ankle droop, terminal foot leveling and grounded stance contact')
    p.add_argument('--pass45-proof', action='store_true', help='Render side-view proof of corrected forward knee flex and grounded ankle/foot behavior')
    p.add_argument('--no-body-solver', action='store_true', help='Developer comparison: disable Pass 41 procedural body support while preserving recorded hand playback')
    p.add_argument('--safe-mode', action='store_true', help='Diagnostic launch: no weapon audio, neural layer, or solid skeleton; body/organs/FPS remain available')
    p.add_argument('--no-neural', action='store_true', help='Disable only the neural-memory layer for crash isolation')
    p.add_argument('--no-skeleton', action='store_true', help='Disable only the internal solid skeleton for crash isolation')
    p.add_argument('--no-head-track', action='store_true', help='Disable automatic NPC neck/head tracking while leaving the skeleton active')
    p.add_argument('--no-arm-flex', action='store_true', help='Disable autonomous independent elbow flex while leaving the rig active')
    p.add_argument('--no-shoulder-sway', action='store_true', help='Disable autonomous shoulder swing while keeping elbow articulation and the rig active')
    p.add_argument('--no-npc-walk', action='store_true', help='Disable autonomous NPC locomotion while preserving the full rig and local joint animation')
    p.add_argument('--preflight', action='store_true', help='Validate launch arguments/assets without importing Panda3D')
    args, unknown = p.parse_known_args()
    args.ignored_args = tuple(unknown)
    if args.windowed:
        args.fullscreen = False
    if unknown:
        print('ASCII_MATTER_IGNORED_ARGS=' + ' '.join(unknown), file=sys.stderr)
    return args


_checkpoint('python_start')
ARGS = parse_args()
if ARGS.preflight:
    required = [
        ROOT / 'assets/cache/generic_male_ascii.json',
        ROOT / 'assets/source/Pistol-Lazer.obj',
        ROOT / 'assets/source/10688_GenericMale_v2.obj',
        ROOT / 'assets/cache/internal_skeleton.json',
    ]
    missing = [str(x.relative_to(ROOT)) for x in required if not x.exists()]
    if missing:
        print('ASCII_MATTER_PREFLIGHT=FAIL missing=' + ','.join(missing))
        raise SystemExit(3)
    print(f'ASCII_MATTER_PREFLIGHT=PASS weapon=holographic_rifle windowed={ARGS.windowed} fullscreen={ARGS.fullscreen} no_audio={ARGS.no_audio or ARGS.safe_mode} no_neural={ARGS.no_neural or ARGS.safe_mode} no_skeleton={ARGS.no_skeleton or ARGS.safe_mode} ignored={len(ARGS.ignored_args)}')
    raise SystemExit(0)

_checkpoint('panda_config')
try:
    from panda3d.core import loadPrcFileData
except BaseException as exc:
    _write_crash_report(exc, 'panda_import')
    raise

# Engine-smoke paths stay silent and deterministic. Normal gameplay selects Panda3D's
# OpenAL plug-in *before* ShowBase creates its audio managers. Pass 35 tried to switch
# away from the null manager after ShowBase startup; on systems where that manager had
# already been created, the result could remain a valid-but-silent/null audio path.
ENGINE_SMOKE = any((ARGS.smoke_test, ARGS.test_shot, ARGS.combat_smoke, ARGS.impact_smoke, ARGS.perf_smoke, ARGS.reverse_perf_smoke, ARGS.rig_smoke, ARGS.head_track_smoke, ARGS.arm_smoke, ARGS.shoulder_smoke, ARGS.walk_smoke, ARGS.fps_control_smoke, ARGS.melee_smoke, ARGS.melee_proof, ARGS.melee_impact_proof, ARGS.sword_smoke, ARGS.sword_proof, ARGS.dismember_proof, ARGS.pass34_smoke, ARGS.pass34_proof, ARGS.pass37_smoke, ARGS.pass37_proof, ARGS.pass38_smoke, ARGS.pass38_proof, ARGS.pass39_smoke, ARGS.pass39_proof, ARGS.pass40_smoke, ARGS.pass40_proof, ARGS.pass41_smoke, ARGS.pass41_proof, ARGS.pass42_smoke, ARGS.pass42_proof, ARGS.pass43_smoke, ARGS.pass43_proof, ARGS.pass44_smoke, ARGS.pass44_proof, ARGS.pass45_smoke, ARGS.pass45_proof))
if not HOLOVERSE_EMBEDDED:
    if ENGINE_SMOKE:
        loadPrcFileData('', f'window-type offscreen\nload-display p3tinydisplay\nwin-size {ARGS.width} {ARGS.height}\naudio-library-name null\nsync-video 0\n')
    else:
        # Standalone Anatomic owns its own render/audio configuration.  When imported
        # by HoloVerse, the already-running host owns these settings and this block is
        # deliberately skipped.
        linux_display = 'load-display p3tinydisplay\n' if os.name != 'nt' else ''
        loadPrcFileData('', f'{linux_display}win-size {ARGS.width} {ARGS.height}\nwindow-title Anatomic - HoloVerse Compatible\nthreading-model Cull/Draw\nsync-video 1\nshow-frame-rate-meter 0\nfullscreen {1 if ARGS.fullscreen else 0}\naudio-library-name p3openal_audio\n')

_checkpoint('panda_import')
from direct.showbase.ShowBase import ShowBase
from direct.gui.DirectGui import DirectFrame, DirectLabel, DirectButton, DirectEntry
from panda3d.core import (
    AmbientLight, AudioManager, AudioSound, CardMaker, DirectionalLight, Filename, Geom, GeomNode, GeomLines, GeomTriangles, GeomVertexData, GeomVertexFormat,
    GeomVertexWriter, LPoint3, LineSegs, NodePath, TextNode, Vec3, Vec4, WindowProperties,
    TransparencyAttrib
)

def _v3(value):
    """Compatibility-safe vector copy for Panda3D 1.10.16 bindings."""
    if hasattr(value, 'x'):
        return Vec3(float(value.x), float(value.y), float(value.z))
    return Vec3(float(value[0]), float(value[1]), float(value[2]))

GLYPH_CACHE = ROOT / 'assets/cache/generic_male_ascii.json'
SKELETON_CACHE = ROOT / 'assets/cache/internal_skeleton.json'

# Pass 29 preserves the Pass 28 dense-body renderer while improving internal skeletal presentation. The logical shell carries substantially more samples,
# while visible glyphs are rebuilt into one flattened batch per animated rig branch.
# This trades thousands of tiny draw submissions for a few dozen articulated batches.
BODY_GLYPH_SCALE = 0.0235
LOD_FULL_DISTANCE = 2.65
LOD_BAL_DISTANCE = 6.75
LOD_KEEP_THRESHOLDS = (256, 148, 92)  # 100%, ~58%, ~36% of live logical glyphs.
GLYPH_CLUSTER_CELL = 0.12  # retained for compatibility with earlier Pass 28 prototypes.
# Compact vector-stroke approximations of the actual ASCII shell characters.
# Coordinates are glyph-local in a [-.5,.5] square; each pair is one line segment.
ASCII_STROKES = {
    '#': [(-.34,-.48,-.18,.48),(.18,-.48,.34,.48),(-.48,-.18,.48,-.18),(-.48,.18,.48,.18)],
    '+': [(0,-.46,0,.46),(-.46,0,.46,0)],
    '=': [(-.44,-.16,.44,-.16),(-.44,.16,.44,.16)],
    '*': [(-.44,0,.44,0),(0,-.44,0,.44),(-.33,-.33,.33,.33),(-.33,.33,.33,-.33)],
    ':': [(-.06,-.26,.06,-.26),(-.06,.26,.06,.26)],
    '.': [(-.07,-.38,.07,-.38)],
    '%': [(-.34,.30,-.20,.44),(-.20,.44,-.06,.30),(-.06,.30,-.20,.16),(-.20,.16,-.34,.30),
          (-.38,-.44,.38,.44),(.06,-.30,.20,-.16),(.20,-.16,.34,-.30),(.34,-.30,.20,-.44),(.20,-.44,.06,-.30)],
    '@': [(-.34,-.28,-.46,0),(-.46,0,-.34,.30),(-.34,.30,0,.44),(0,.44,.34,.30),(.34,.30,.46,0),
          (.46,0,.34,-.30),(.34,-.30,0,-.44),(0,-.44,-.34,-.28),(-.10,.10,.08,.20),(.08,.20,.22,.06),
          (.22,.06,.18,-.14),(.18,-.14,0,-.12),(0,-.12,-.08,0),(-.08,0,-.02,.12),(.18,-.14,.34,-.08)],
}

# Pass 15 neck swivel limits preserved under Pass 16 elbow articulation.  The NPC's authored forward direction is -Y, so
# H=0/P=0 is the visual rest pose; tracking angles are local to spine_high.
HEAD_TRACK_YAW_LIMIT = 58.0
HEAD_TRACK_PITCH_UP_LIMIT = 28.0
HEAD_TRACK_PITCH_DOWN_LIMIT = 22.0
HEAD_TRACK_SPEED_DPS = 120.0
HEAD_TRACK_DEADZONE_DEG = 0.35
# Pass 16 independent elbow articulation. Only elbow descendants are rotated;
# shoulders/torso remain the parent frame.  The two arms use different phases so
# they do not mirror one another mechanically.
ELBOW_FLEX_MIN_DEG = 3.0
ELBOW_FLEX_MAX_DEG = 34.0
ELBOW_FLEX_SPEED_HZ = 0.18
ELBOW_FLEX_RESPONSE_DPS = 80.0
# Pass 19 shoulder articulation.  The shoulder is the parent of the elbow chain,
# so these small local rotations carry the humerus, forearm, wrist, hand and
# fingers without moving the chest or opposite arm.  Pitch creates a gentle
# forward/back arm swing; mirrored roll adds a small natural lateral lift.
SHOULDER_SWING_DEG = 7.5
SHOULDER_LIFT_DEG = 4.0
SHOULDER_SWAY_SPEED_HZ = 0.13
SHOULDER_RESPONSE_DPS = 48.0
# Pass 20 procedural walking.  The authored model faces local -Y, so H=0
# means the NPC walks toward world -Y.  The route stays near the lab center and
# the rig provides the gait while body_root supplies world translation/turning.
NPC_WALK_SPEED = 0.72
NPC_TURN_SPEED_DPS = 105.0
NPC_GAIT_HZ = 0.92
NPC_HIP_SWING_DEG = 18.0
# Pass 45 JointMap authority: knees hinge opposite the elbows and only flex in the
# forward-swinging leg.  The ankle owns foot leveling; it may briefly relax into a
# small droop after toe-off, but must return the foot to a flat world pitch before plant.
NPC_KNEE_FLEX_DEG = 40.0
NPC_KNEE_PEAK_SWING = 0.35
NPC_ANKLE_DROOP_DEG = 8.0
NPC_ANKLE_LEVEL_BEGIN = 0.62
NPC_ANKLE_LEVEL_END = 0.84
NPC_PELVIS_ROLL_DEG = 1.8
NPC_ROOT_CONTACT_RESPONSE_MPS = 0.30
JOINT_MAP_AUTHORITY = {
    'neck': {'parent':'spine_high','axes':'yaw_pitch','note':'head/neck swivel and tilt; no body translation'},
    'left_shoulder': {'parent':'spine_high','independent':True,'sweep_deg':270},
    'right_shoulder': {'parent':'spine_high','independent':True,'sweep_deg':270},
    'left_elbow': {'parent':'left_shoulder','hinge':'arm_forward','side_motion':False},
    'right_elbow': {'parent':'right_shoulder','hinge':'arm_forward','side_motion':False},
    'left_wrist': {'parent':'left_elbow','swivel_deg':360,'collision_safe':True},
    'right_wrist': {'parent':'right_elbow','swivel_deg':360,'collision_safe':True},
    'waist': {'joint':'spine_low','swivel_deg':180,'parents_upper_body':True},
    'left_hip': {'parent':'pelvis','sweep_deg':270,'outward':True},
    'right_hip': {'parent':'pelvis','sweep_deg':270,'outward':True},
    'left_knee': {'parent':'left_hip','hinge':'opposite_elbow','side_motion':False},
    'right_knee': {'parent':'right_hip','hinge':'opposite_elbow','side_motion':False},
    'left_ankle': {'parent':'left_knee','role':'ground_flattening'},
    'right_ankle': {'parent':'right_knee','role':'ground_flattening'},
}
NPC_WALK_BLEND_SPEED = 4.5
NPC_WAYPOINT_RADIUS = 0.075
NPC_WALK_START_DELAY = 1.20
NPC_WALK_ROUTE = (
    (0.0, -1.25),
    (1.15, -1.25),
    (1.15, 0.20),
    (-1.15, 0.20),
    (-1.15, -1.25),
    (0.0, -1.25),
    (0.0, 0.0),
)
# Pass 17 first-person control polish. Acceleration/friction remove the abrupt
# start-stop feel while jump buffering/coyote time make Space more forgiving.
WALK_SPEED = 4.0
SPRINT_SPEED = 6.5
CROUCH_SPEED = 2.3
# Pass 37 movement authority: responsive planar steering with bounded momentum.
GROUND_ACCEL = 28.0
GROUND_DECEL = 38.0
GROUND_REVERSE_ACCEL = 50.0
AIR_ACCEL = 8.5
AIR_REVERSE_ACCEL = 11.0
COYOTE_TIME = 0.12
JUMP_BUFFER_TIME = 0.14
JUMP_SPEED = 5.70
GRAVITY = 15.0
EYE_TRANSITION_SPEED = 5.0
LANDING_DIP_MAX = 0.038
LANDING_DIP_SCALE = 0.0055
LANDING_RECOVER_SPEED = 0.30
LOCOMOTION_BOB_SCALE = 0.0055
LOCOMOTION_SWAY_SCALE = 0.0065
LOCOMOTION_PHASE_RATE = 1.72
MOUSE_SENS_X = 0.100
MOUSE_SENS_Y = 0.095
MAX_MOUSE_PIXEL_DELTA = 120
CAMERA_PITCH_LIMIT = 86.0
SPAWN_LOOK_TARGET_Z = 1.38
PISTOL_OBJ = ROOT / 'assets/source/Pistol-Lazer.obj'
WEAPON_SFX_DIR = ROOT / 'assets/audio/weapons'
WORLD_HALF = 24.0
PLAYER_RADIUS = 0.30
STAND_EYE = 1.68
CROUCH_EYE = 1.08
BODY_COLLISION_RADIUS = 0.58
WOUND_RADIUS = 0.26
WOUND_CORE_RADIUS = 0.050
BREAK_RADIUS = 0.100
WOUND_BLOOM_TIME = 0.16
REWIND_SPEED = 2.20
MEMORY_SAMPLE_DT = 1.0 / 30.0
WOUND_VISUAL_UPDATE_DT = 1.0 / 30.0
WEAPON_AUDIO_POOL_FIRE = 12
WEAPON_AUDIO_POOL_IMPACT = 10
MELEE_AUDIO_POOL_ARM = 10
MELEE_AUDIO_POOL_SWORD = 12
AUDIO_CACHE_LIMIT = 96
ARM_MOTION_SOUND_DISTANCE = 0.055
ARM_MOTION_SOUND_COOLDOWN = 0.115
SWORD_MOTION_SOUND_DISTANCE = 0.038
SWORD_MOTION_SOUND_COOLDOWN = 0.085


# Pass 33 Laser Sword Structural Dismemberment and Pass 34 Assisted Reach remain inherited authority.
# Historical authority markers retained for regression tooling: Pass 34 Assisted Reach Swings; Pass 36 Restored Polyphonic Melee Audio + Impact.
# Pass 40 makes held melee recording literal: every sampled solved hand target and wrist
# orientation is replayed from the weapon's original starting pose at 1.5x recorded speed.
# Right-hand recordings can be persisted to slots 1-9 and replay anywhere because all data
# stays in camera/melee-local coordinates. Sword physical reaction is doubled and high-speed
# playback generates a swept hardlight distortion ribbon from the real blade geometry.
# Pass 40 preserves wider FOV, stronger contact and generated red wound ASCII spill.
# Historical identity marker: Pass 40 Recorded Sword Slots remains inherited authority.
# Historical Pass40 wound impulse contract marker: impulse_scale=(.62+.70*charge)*SWORD_IMPACT_MULTIPLIER
# Historical identity marker: Anatomic Pass 41 remains the inherited Body Solver authority.
# Pass 42 adds Motion Dynamics: real blade velocity, edge alignment, contact leverage and
# motion type now scale sword wounds, physical reaction, debris impulse, sparks and severing.
# Pass 41 adds a procedural Body Solver around the player-authored local hand path.
# Recorded hand/wrist transforms remain exact authority; torso/hip intent is represented by
# shoulder-line rotation, stance weight shift and elbow-pole anticipation around that target.
# Pass 34 preserves Pass 33 sword/dismemberment and refines first-person framing and
# gesture melee. Held gestures progressively reach outward, release commits through an
# outward/forward strike lane with bounded enemy assist, and the sword wrist is canted
# modestly forward while held. The left hand remains the precision gesture fist.
PLAYER_FOV_DEG = 88.0
MELEE_UPPER_ARM_LEN = 0.40
MELEE_FOREARM_LEN = 0.40
MELEE_NEUTRAL_Y = 0.50
MELEE_MAX_REACH = 0.79
MELEE_MIN_REACH = 0.22
MELEE_GESTURE_X = 0.46
MELEE_GESTURE_Z = 0.38
MELEE_GESTURE_SAMPLE_DIST = 0.018
MELEE_MAX_PATH_POINTS = 4096
MELEE_TAP_TIME = 0.16
MELEE_FULL_CHARGE_TIME = 1.35
MELEE_PUNCH_RADIUS = 0.170
MELEE_DIRECT_DAMAGE = 4
MELEE_CHARGED_DAMAGE = 11
MELEE_OUTER_PURPLE = Vec4(0.62, 0.12, 0.94, 1.0)
MELEE_MID_RED = Vec4(0.94, 0.10, 0.30, 1.0)
MELEE_CORE_RED = Vec4(1.0, 0.018, 0.014, 1.0)
MELEE_LEFT = Vec4(0.22, 0.94, 1.0, 0.92)
MELEE_RIGHT = Vec4(0.72, 0.38, 1.0, 0.92)
MELEE_FILL_ALPHA = 0.16
MELEE_DETAIL_ALPHA = 0.82
MELEE_TRAIL_CORE_ALPHA = 0.98
MELEE_WRIST_TWIST_DEG = 18.0
MELEE_FOLLOW_THROUGH = 0.085
MELEE_HOLD_REACH_GAIN = 0.21
MELEE_HOLD_REACH_BASE = 0.42
MELEE_AUTO_AIM_BLEND = 0.90
MELEE_AUTO_AIM_MAX_DISTANCE = 2.25
MELEE_OUTWARD_ARC_X = 0.31
MELEE_TARGET_SIDE_OFFSET = 0.045
MELEE_RELEASE_ORIENTATION_BLEND = 0.58
MELEE_RELEASE_OUTWARD_STEP = 0.14
SWORD_FLURRY_Z_SWEEP = 0.16
SWORD_FLURRY_TURNS = 1.18
SWORD_FLURRY_HEADING_DEG = 18.0
SWORD_FLURRY_PITCH_DEG = 22.0
SWORD_FLURRY_ROLL_DEG = 245.0
SWORD_FLURRY_PORTION = 0.72
SWORD_HOLD_FORWARD_BIAS = 0.18
SWORD_HOLD_WRIST_PITCH_DEG = -6.5
MELEE_REPLAY_SPEED = 1.50
MELEE_SLOT_COUNT = 9
MELEE_RECORD_SAMPLE_DT = 1.0 / 60.0
# Historical identity marker: Anatomic Pass 43 Motion Forge remains inherited authority.
# Pass 43 Motion Forge: non-destructive metadata layered over immutable captured samples.
MOTION_FORGE_MIN_SPEED = 0.50
MOTION_FORGE_MAX_SPEED = 2.50
MOTION_FORGE_SPEED_STEP = 0.10
MOTION_FORGE_TRIM_STEP = 0.05
MOTION_FORGE_MIN_DURATION = 0.12
MOTION_FORGE_DEFAULT_NAME = 'UNTITLED MOTION'
# Pass 44 Combo Composer. Combos reference immutable Motion Forge slots; connective
# bridges are generated in local hand space and are explicitly non-damaging.
COMBO_SLOT_COUNT = 9
COMBO_MAX_MOVES = 6
COMBO_MIN_MOVES = 2
COMBO_DEFAULT_NAME = 'UNTITLED COMBO'
COMBO_TRANSITION_MIN = 0.060
COMBO_TRANSITION_MAX = 0.220
COMBO_TRANSITION_BASE = 0.045
COMBO_TRANSITION_POS_RATE = 3.8
COMBO_TRANSITION_ANGLE_RATE = 760.0
COMBO_TRANSITION_TANGENT_SCALE = 0.28
COMBO_TRANSITION_MAX_TANGENT_SPEED = 2.6
# Pass 41 Body Solver. These values affect only the supporting virtual body.
BODY_SOLVER_LOOKAHEAD = 0.115
BODY_SOLVER_RESPONSE = 18.0
BODY_SOLVER_RELEASE_RESPONSE = 12.0
BODY_SOLVER_MAX_TORSO_H = 11.5
BODY_SOLVER_MAX_TORSO_P = 5.5
BODY_SOLVER_MAX_TORSO_R = 7.0
BODY_SOLVER_HIP_COUNTER = 0.58
BODY_SOLVER_MAX_STANCE_X = 0.052
BODY_SOLVER_MAX_STANCE_Y = 0.028
BODY_SOLVER_MAX_SHOULDER_Z = 0.032
BODY_SOLVER_MAX_SHOULDER_Y = 0.046
BODY_SOLVER_MAX_ELBOW_LEAD = 0.18
BODY_SOLVER_SPEED_REF = 0.70
BODY_SOLVER_REACH_REF = 0.22
SWORD_IMPACT_MULTIPLIER = 2.0
# Pass 42 Motion Dynamics. Values are tuned around the existing meter-scale viewmodel.
# A normal authored cut remains dangerous, while slow drags and flat-side contacts lose
# cutting authority. Fast, well-aligned tip/outer-blade contacts gain wound and reaction force.
SWORD_DYN_MIN_SPEED = 0.30
SWORD_DYN_REFERENCE_SPEED = 4.60
SWORD_DYN_MAX_SPEED = 10.0
SWORD_DYN_MIN_IMPACT = 0.38
SWORD_DYN_MAX_IMPACT = 1.85
SWORD_DYN_MIN_CUT = 0.24
SWORD_DYN_MAX_CUT = 1.85
SWORD_DYN_LEVER_BASE = 0.70
SWORD_DYN_LEVER_GAIN = 0.48
SWORD_DYN_FLAT_CUT_SCALE = 0.34
SWORD_DYN_THRUST_THRESHOLD = 0.58
SWORD_DYN_CLEAN_EDGE_THRESHOLD = 0.62
SWORD_DYN_SEVER_THRESHOLD = 0.42
SWORD_DYN_DAMAGE_MAX = 46
SWORD_DISTORTION_LIFE = 0.19
SWORD_DISTORTION_POINTS = 20
SWORD_DISTORTION_MIN_SPEED = 0.60
SWORD_DISTORTION_MAX_SPEED = 7.0
SWORD_DISTORTION_OFFSETS = (-0.018, 0.0, 0.018)
SWORD_DISTORTION_ALPHA = 0.34
MELEE_SLOT_PATH = RUNTIME_LOG_DIR.parent / 'melee_slots.json'
NPC_STAGGER_DRAG = 7.5
NPC_STAGGER_MAX_SPEED = 3.25
NPC_DEFENSE_TIME = 0.72
NPC_DEFENSE_SIDE_STEP = 0.72

MELEE_SHOULDER_X = 0.315
MELEE_NEUTRAL_X = 0.205
SWORD_BLADE_LENGTH = 0.82
SWORD_HILT_LENGTH = 0.19
SWORD_CUT_RADIUS = 0.074
SWORD_ASCII_DAMAGE = 18
SWORD_ASCII_DAMAGE_CHARGED = 30
SWORD_MIN_SEVER_CHARGE = 0.28
SWORD_MIN_SEVER_TRAVEL = 0.075
SWORD_TRAIL_POINTS = 14
SWORD_TRAIL_LIFE = 0.13
SWORD_SPARK_LIFE = 0.18
SWORD_GRAVITY = 7.8
SWORD_LIMB_BOUNCE = 0.24
SWORD_LIMB_DRAG = 1.45
SWORD_ANGULAR_DRAG = 2.0
WOUND_ASCII_MAX = 96
WOUND_ASCII_GRAVITY = 6.9
WOUND_ASCII_LIFE = 2.8
WOUND_ASCII_EMIT_TIME = 1.55
WOUND_ASCII_MELEE_RATE = 11.0
WOUND_ASCII_SWORD_RATE = 18.0
WOUND_ASCII_GLYPHS = '@#%*+'
SWORD_CORE = Vec4(0.92, 0.995, 1.0, 1.0)
SWORD_GLOW = Vec4(0.20, 0.82, 1.0, 0.58)
SWORD_EDGE = Vec4(0.72, 0.38, 1.0, 0.82)

# Intact ASCII matter keeps an explicit memory palette.  The generated TextNode
# glyph geometry stays white and these colors modulate it through ColorScale,
# preserving visible cyan/blue identity while allowing wound red to blend back
# toward each glyph's exact pristine color.
MEMORY_PALETTE = {
    'head': Vec4(0.62, 0.96, 1.00, 1.0),
    'chest': Vec4(0.20, 0.92, 1.00, 1.0),
    'torso': Vec4(0.10, 0.82, 1.00, 1.0),
    'pelvis': Vec4(0.18, 0.74, 1.00, 1.0),
    'upper_leg': Vec4(0.08, 0.68, 0.98, 1.0),
    'lower_leg': Vec4(0.06, 0.60, 0.94, 1.0),
    'foot': Vec4(0.14, 0.70, 0.96, 1.0),
}
MEMORY_WOUND_RED = Vec4(1.0, 0.025, 0.018, 1.0)

ORGAN_RECIPES = {
    # +Y is toward the rear of the skull from the default first-person view.
    'brain':        {'center': (0.000, 0.012, 1.690), 'radii': (0.050, 0.042, 0.040), 'count': 24, 'glyphs': '&%@', 'color': Vec4(0.96, 0.48, 1.00, 1.0)},
    'left_lung':    {'center': (-0.073, 0.000, 1.350), 'radii': (0.036, 0.023, 0.095), 'count': 22, 'glyphs': '()%', 'color': Vec4(0.70, 0.78, 1.00, 1.0)},
    'right_lung':   {'center': (0.073, 0.000, 1.350), 'radii': (0.036, 0.023, 0.095), 'count': 22, 'glyphs': '()%', 'color': Vec4(0.70, 0.78, 1.00, 1.0)},
    'heart':        {'center': (0.000, -0.030, 1.310), 'radii': (0.023, 0.014, 0.030), 'count': 12, 'glyphs': '*<>', 'color': Vec4(1.00, 0.22, 0.38, 1.0)},
    'stomach':      {'center': (-0.055, 0.012, 1.105), 'radii': (0.032, 0.020, 0.042), 'count': 12, 'glyphs': '~S%', 'color': Vec4(1.00, 0.68, 0.20, 1.0)},
    'liver':        {'center': (0.055, 0.007, 1.115), 'radii': (0.040, 0.020, 0.030), 'count': 14, 'glyphs': '=L#', 'color': Vec4(0.86, 0.40, 0.16, 1.0)},
    'left_kidney':  {'center': (-0.065, -0.012, 1.005), 'radii': (0.018, 0.014, 0.026), 'count': 6, 'glyphs': '8K', 'color': Vec4(0.76, 0.36, 0.90, 1.0)},
    'right_kidney': {'center': (0.065, -0.012, 1.005), 'radii': (0.018, 0.014, 0.026), 'count': 6, 'glyphs': '8K', 'color': Vec4(0.76, 0.36, 0.90, 1.0)},
}
ORGAN_GLYPH_SCALE = 0.014
NEURAL_GLYPH_SCALE = 0.009
NEURAL_RED = Vec4(0.95, 0.035, 0.055, 1.0)
NEURAL_BODY_CLEARANCE = 0.017
NEURAL_ORGAN_CLEARANCE = 0.015
NEURAL_PATH_SPACING = 0.030

# Sparse central nervous-system memory.  The main trunk stays behind the thoracic
# organs and branches into both arms and legs. Unsafe points are rejected using
# the actual 1,300-point GenericMale surface cache at startup.
NEURAL_PATHS = {
    'spinal_trunk': [(0,.040,1.645),(0,.055,1.560),(0,.060,1.460),(0,.065,1.360),(0,.065,1.250),(0,.060,1.150),(0,.055,1.040),(0,.050,.920)],
    'left_shoulder':[(-.005,.055,1.480),(-.080,.060,1.470),(-.150,.055,1.430),(-.210,.062,1.370)],
    'right_shoulder':[(.005,.055,1.480),(.080,.060,1.470),(.150,.055,1.430),(.210,.056,1.370)],
    'left_arm':[(-.210,.062,1.370),(-.250,.056,1.290),(-.290,.059,1.190),(-.320,.045,1.090),(-.350,.003,.990),(-.380,-.042,.890)],
    'right_arm':[(.210,.056,1.370),(.250,.064,1.290),(.290,.058,1.190),(.320,.033,1.090),(.350,-.005,.990),(.380,-.038,.890)],
    'left_leg':[(-.010,.050,.920),(-.060,.055,.840),(-.090,.055,.740),(-.100,.055,.640),(-.105,.055,.530),(-.105,.060,.420),(-.105,.060,.300),(-.105,.065,.180)],
    'right_leg':[(.010,.050,.920),(.060,.055,.840),(.090,.055,.740),(.100,.055,.640),(.105,.055,.530),(.105,.060,.420),(.105,.060,.300),(.105,.065,.180)],
}


class Fragment:
    __slots__ = ('index', 'glyph', 'node', 'pos', 'vel', 'roll', 'roll_v', 'age', 'samples', 'sample_clock', 'settled')
    def __init__(self, index, glyph, node, pos, vel, roll_v):
        self.index = int(index)
        self.glyph = str(glyph)
        self.node = node
        self.pos = Vec3(*pos)
        self.vel = Vec3(*vel)
        self.roll = 0.0
        self.roll_v = roll_v
        self.age = 0.0
        self.samples = [(0.0, (self.pos.x, self.pos.y, self.pos.z), 0.0)]
        self.sample_clock = 0.0
        self.settled = False


class Wound:
    __slots__ = ('center', 'radius', 'age', 'bloom', 'bind_name', 'outer_color', 'core_color', 'mode', 'spill_accum')
    def __init__(self, center, radius=WOUND_RADIUS, bind_name='body_root', outer_color=None, core_color=None, mode='AUTO'):
        # Center is stored in the local space named by bind_name so animated
        # wounds remain attached to the body branch that was actually struck.
        self.center = _v3(center)
        self.radius = float(radius)
        self.age = 0.0
        self.bloom = WOUND_BLOOM_TIME
        self.bind_name = str(bind_name)
        oc = outer_color if outer_color is not None else MEMORY_WOUND_RED
        cc = core_color if core_color is not None else MEMORY_WOUND_RED
        self.outer_color = Vec4(float(oc.x), float(oc.y), float(oc.z), float(oc.w))
        self.core_color = Vec4(float(cc.x), float(cc.y), float(cc.z), float(cc.w))
        self.mode = str(mode).upper()
        self.spill_accum = 0.0

    @property
    def strength(self):
        if self.age <= 0.0:
            return 0.0
        return min(1.0, self.age / self.bloom)


class WoundASCII:
    __slots__ = ('glyph','node','pos','vel','roll','roll_v','age','life','samples','sample_clock','settled','origin')
    def __init__(self, glyph, node, pos, vel, roll_v, life=WOUND_ASCII_LIFE):
        self.glyph=str(glyph); self.node=node; self.pos=_v3(pos); self.origin=_v3(pos); self.vel=_v3(vel)
        self.roll=0.0; self.roll_v=float(roll_v); self.age=0.0; self.life=float(life)
        self.samples=[(0.0,(self.pos.x,self.pos.y,self.pos.z),0.0)]; self.sample_clock=0.0; self.settled=False



class Shot:
    __slots__ = ('node','pos','vel','life','side','radius','count','mode','hit_index','hit_bind','hit_local','hit_threshold')
    def __init__(self, node, pos, vel, side, radius=WOUND_RADIUS, count=30, life=1.8,
                 mode='AUTO', hit_index=None, hit_bind='body_root', hit_local=None, hit_threshold=.10):
        self.node=node; self.pos=_v3(pos); self.vel=_v3(vel); self.life=float(life); self.side=str(side)
        self.radius=float(radius); self.count=int(count); self.mode=str(mode)
        self.hit_index=hit_index; self.hit_bind=str(hit_bind); self.hit_local=_v3(hit_local) if hit_local is not None else None
        self.hit_threshold=float(hit_threshold)


class DetachedLimb:
    __slots__ = ('root_name','root','parent_name','parent','local_transform','cut_bone','cut_node','velocity','angular_velocity','age','sample_clock','samples','floor_offset','descendants','settled')
    def __init__(self, root_name, root, parent_name, parent, local_transform, cut_bone, cut_node, velocity, angular_velocity, floor_offset, descendants):
        self.root_name=str(root_name); self.root=root; self.parent_name=str(parent_name or '')
        self.parent=parent; self.local_transform=local_transform; self.cut_bone=str(cut_bone); self.cut_node=cut_node
        self.velocity=_v3(velocity); self.angular_velocity=_v3(angular_velocity); self.age=0.0; self.sample_clock=0.0
        self.samples=[]; self.floor_offset=float(floor_offset); self.descendants=set(descendants); self.settled=False


class ASCIIMatterLab(ShowBase):
    def __init__(self, host=None, render_root=None):
        self._holoverse_embedded = host is not None
        self._holoverse_host = host
        self._embedded_dt_override = None
        _checkpoint('holoverse_host_attach' if self._holoverse_embedded else 'showbase_init')
        if self._holoverse_embedded:
            # Reuse HoloVerse's one ShowBase/window/camera/task/audio authority.  This
            # object intentionally does not initialize a second ShowBase.
            self.taskMgr = host.taskMgr
            self.loader = host.loader
            self.win = host.win
            self.graphicsEngine = getattr(host, 'graphicsEngine', None)
            self.render = render_root if render_root is not None else host.render
            self.render2d = getattr(host, 'render2d', None)
            self.aspect2d = getattr(host, 'aspect2d', None)
            self.pixel2d = getattr(host, 'pixel2d', None)
            self.camera = host.camera
            self.camLens = host.camLens
            self.mouseWatcherNode = getattr(host, 'mouseWatcherNode', None)
            self.sfxManagerList = list(getattr(host, 'sfxManagerList', []) or [])
            self.musicManager = getattr(host, 'musicManager', None)
            _checkpoint('holoverse_host_ready')
        else:
            super().__init__()
            _checkpoint('showbase_ready')
            self.disableMouse()
            self.setBackgroundColor(0.0, 0.0, 0.0, 1.0)
        self.camLens.setFov(PLAYER_FOV_DEG)
        self.camLens.setNearFar(0.05, 60.0)

        self.rng = random.Random(7001)
        self.pristine_rng_state = self.rng.getstate()
        self.fragments = []
        self.wounds = []
        self.wound_ascii = []
        self.wound_ascii_pool = {}
        self.rewinding = False
        self.shots = []
        self.weapon_sfx = {}
        self.audio_available = False
        self.weapon_audio_backend = 'disabled'
        self.weapon_audio_manager = None
        self.weapon_audio_cursor = {}
        self.weapon_audio_generation = {}
        self.sword_hum = None
        self.melee_audio_motion_accum = {'left': 0.0, 'right': 0.0}
        self.melee_audio_cooldown = {'left': 0.0, 'right': 0.0}
        self.melee_audio_last_target = {'left': None, 'right': None}
        self.weapon_recoil = 0.0
        self.fire_cooldown = 0.0
        self.fire_button_down = False
        self.fire_latch = False
        self.weapon_root = None
        self.weapon_muzzle = None
        self.weapon_spinner_groups = []
        self.weapon_fill_nodes = []
        self.weapon_wire_nodes = []
        self.weapon_palette_glow = None
        self.weapon_mode_order = ('AUTO', 'SHOTGUN', 'SNIPER')
        self.weapon_modes = {
            'AUTO': {
                'label': 'AUTO', 'display': 'AUTOMATIC RIFLE', 'pellets': 1, 'spread': 0.45, 'speed': 24.0,
                'cooldown': 0.090, 'recoil': 0.70, 'scale': 0.036, 'radius': WOUND_RADIUS * 0.90,
                'count': 18, 'life': 1.35, 'color': (.20, .92, 1.00, 1.0), 'wire': (.62, .98, 1.00, .88),
                'fill': (.10, .78, 1.00, .14), 'glow': (.20, .92, 1.00, .20),
            },
            'SHOTGUN': {
                'label': 'SHOTGUN', 'display': 'SHOTGUN', 'pellets': 7, 'spread': 5.8, 'speed': 18.5,
                'cooldown': 0.420, 'recoil': 1.18, 'scale': 0.041, 'radius': WOUND_RADIUS * 1.20,
                'count': 14, 'life': 0.72, 'color': (1.00, .78, .30, 1.0), 'wire': (1.00, .92, .62, .90),
                'fill': (.98, .62, .18, .16), 'glow': (1.00, .72, .18, .22),
            },
            'SNIPER': {
                'label': 'SNIPER', 'display': 'SNIPER', 'pellets': 1, 'spread': 0.06, 'speed': 38.0,
                'cooldown': 0.900, 'recoil': 1.28, 'scale': 0.029, 'radius': WOUND_RADIUS * 1.35,
                'count': 40, 'life': 2.15, 'color': (.92, .48, 1.00, 1.0), 'wire': (.96, .76, 1.00, .92),
                'fill': (.56, .20, 1.00, .15), 'glow': (.84, .36, 1.00, .22),
            },
        }
        self.current_weapon_mode = 'AUTO'
        self.combat_mode = 'rifle'
        self.melee_root = None
        self.melee_arms = {}
        self.melee_hold = {'left': False, 'right': False}
        self.melee_hold_time = {'left': 0.0, 'right': 0.0}
        self.melee_cursor = {'left': [0.0, 0.0], 'right': [0.0, 0.0]}
        self.melee_paths = {'left': [], 'right': []}
        self.melee_recordings = {'left': [], 'right': []}
        self.melee_motion_recordings = {'left': [], 'right': []}
        self.melee_last_recording = {'left': None, 'right': None}
        self.melee_pending_slot_save = False
        self.melee_slots = {}
        self.motion_forge_visible = False
        self.motion_forge_slot = 1
        self.motion_forge = None
        self.motion_forge_labels = {}
        self.motion_forge_slot_buttons = []
        self.motion_forge_name_entry = None
        self.motion_forge_mouse_was_captured = False
        self.melee_combos = {}
        self.active_combo_slot = 1
        self.combo_composer_visible = False
        self.combo_composer_slot = 1
        self.combo_composer = None
        self.combo_composer_labels = {}
        self.combo_composer_bank_buttons = []
        self.combo_composer_move_buttons = []
        self.combo_composer_name_entry = None
        self.combo_composer_mouse_was_captured = False
        self.melee_playback = {'left': None, 'right': None}
        self.melee_trails = {'left': None, 'right': None}
        self.melee_fist_world_prev = {'left': None, 'right': None}
        self.melee_last_hit_time = {'left': -9.0, 'right': -9.0}
        self.melee_time = 0.0
        self.melee_raise_blend = 0.0
        # Pass 41 virtual full-body support. The solver never owns hand targets.
        self.melee_body_solver = {'torso_h':0.0,'torso_p':0.0,'torso_r':0.0,'hip_h':0.0,'stance_x':0.0,'stance_y':0.0,'shoulder_z':0.0,'shoulder_y':0.0,'elbow_x':0.0,'elbow_z':0.0,'intensity':0.0}
        self.melee_body_solver_goal = dict(self.melee_body_solver)
        self.melee_body_solver_debug = {'source':'idle','velocity':Vec3(0,0,0),'active_side':None}
        self.npc_stagger_velocity = Vec3(0,0,0)
        self.npc_defense_timer = 0.0
        self.npc_defense_side = 1.0
        self.npc_last_damage_mode = 'NONE'
        self.npc_damage_origin = None
        self.melee_test_state = None
        self.melee_head_hits = 0
        self.melee_body_hits = 0
        self.melee_peak_head_reaction = 0.0
        self.sword_root = None
        self.sword_blade_core = None
        self.sword_blade_glow = None
        self.sword_base = None
        self.sword_tip = None
        self.sword_tip_prev = None
        self.sword_base_prev = None
        self.sword_tip_history = []
        self.sword_trail_nodes = []
        self.sword_sparks = []
        self.sword_distortion_history = []
        self.sword_distortion_node = None
        self.sword_last_distortion_tip = None
        self.sword_pulse = 0.0
        self.detached_limbs = []
        self.detached_joint_names = set()
        self.skeleton_bone_nodes = {}
        self.skeleton_bone_specs = {}
        self.rig_parent_names = {}
        self.sword_cut_count = 0
        self.sword_last_cut_bone = 'NONE'
        self.severed_bone_names = set()
        self.sword_test_state = None
        self.sword_last_dynamics = {'type':'IDLE','speed':0.0,'edge':0.0,'thrust':0.0,'flat':0.0,'lever':0.0,'impact':0.0,'cut':0.0}
        self.sword_dynamics_peak = 0.0
        # Pass 25 performance/impact state.
        self.projectile_proto = {}
        self.binding_members = {}
        self.binding_bounds = {}
        self.glyph_batches = {}
        self.glyph_batch_vdatas = {}
        self.glyph_batch_color_rows = {}
        self.wound_color_bindings = set()
        self.wound_visual_clock = 0.0
        self.fragment_pool = {}
        self.glyph_local_positions = []
        self.glyph_local_normals = []
        self.status_cache = None
        self.lod_tier = -1
        self.lod_clock = 0.0
        self.lod_visible_count = 0
        self.internal_detail_visible = True
        self.perf_counters = {'shot_queries':0,'shot_binding_checks':0,'shot_query_checks':0,'shot_query_candidates':0,'damage_checks':0,'damage_binding_checks':0,'lod_changes':0,'glyph_batch_rebuilds':0,'glyph_color_updates':0,'fragment_pool_hits':0,'fragment_pool_misses':0,'projectile_builds':0}
        self.impact_body_p = self.impact_body_r = 0.0
        self.impact_body_vp = self.impact_body_vr = 0.0
        self.impact_head_h = self.impact_head_p = self.impact_head_r = 0.0
        self.impact_head_vh = self.impact_head_vp = self.impact_head_vr = 0.0
        self.glyph_nodes = []
        self.original_colors = []
        self.organ_nodes = []
        self.organ_points = []
        self.organ_original_colors = []
        self.organ_names = []
        self.neural_nodes = []
        self.neural_points = []
        self.neural_names = []
        self.skeleton_root = None
        self.rig_root = None
        self.rig_joints = {}
        self.rig_rest_positions = {}
        self.body_bindings = []
        self.organ_bindings = []
        self.neural_bindings = []
        self.rig_test_state = None
        self.head_track_state = None
        self.head_track_h = 0.0
        self.head_track_p = 0.0
        self.head_track_target_h = 0.0
        self.head_track_target_p = 0.0
        self.arm_anim_time = 0.0
        self.arm_flex_left = 0.0
        self.arm_flex_right = 0.0
        self.arm_test_state = None
        self.shoulder_anim_time = 0.0
        self.shoulder_pitch_left = 0.0
        self.shoulder_pitch_right = 0.0
        self.shoulder_roll_left = 0.0
        self.shoulder_roll_right = 0.0
        self.shoulder_test_state = None
        self.npc_walk_time = 0.0
        self.npc_walk_phase = 0.0
        self.npc_walk_blend = 0.0
        self.npc_walk_route_index = 0
        self.npc_walk_distance = 0.0
        self.npc_walk_moving = False
        self.npc_walk_base_z = 0.15
        self.npc_walk_contact_z = {'left': None, 'right': None}
        self.npc_walk_debug = {}
        self.npc_walk_test_state = None
        self.skeleton_bones = []
        self.skeleton_joints = []
        self.skeleton_skull_parts = []
        self.skeleton_segment_count = 0
        self.skeleton_joint_count = 0
        self.skeleton_skull_count = 0
        self.live = []
        self.keys = set()
        self.frame_count = 0
        self.proof_done = False
        self.last_hit = 'NONE'
        self.mouse_captured = not (ARGS.smoke_test or ARGS.test_shot or ARGS.audio_diagnostic)
        self.help_visible = False
        self.fullscreen = bool(ARGS.fullscreen)

        self.player_pos = Vec3(0.0, -5.0, 0.0)
        self.player_vel = Vec3(0.0, 0.0, 0.0)
        self.player_vel_z = 0.0
        self.yaw = 0.0
        self.pitch = 0.0
        self.on_ground = True
        self.crouching = False
        self.current_eye_height = STAND_EYE
        self.coyote_timer = COYOTE_TIME
        self.jump_buffer_timer = 0.0
        self.mouse_sensitivity = MOUSE_SENS_X
        self.mouse_pitch_sensitivity = MOUSE_SENS_Y
        self.mouse_ignore_frames = 2
        self.spawn_facing_dot = 0.0
        self.fps_control_test_state = None
        self.locomotion_phase = 0.0
        self.landing_camera_offset = 0.0
        self.melee_slots = self._load_melee_slots()

        _checkpoint('world_build')
        self._build_black_world()
        _checkpoint('weapon_geometry')
        self._build_weapon_prototype()
        self._build_viewmodels()
        _checkpoint('audio_manifest')
        self._load_weapon_audio()
        _checkpoint('glyph_prototypes')
        self._build_glyph_prototypes()
        _checkpoint('body_and_anatomy')
        self._load_body()
        _checkpoint('spawn_facing')
        self._set_spawn_camera_facing_npc()
        self._update_render_lod(1.0, force=True)
        _checkpoint('ui')
        self._build_ui()
        _checkpoint('input')
        # Native HoloVerse mode now preserves the source game's own Panda
        # messenger bindings. TAB alone stays reserved by HoloVerse.
        self._bind()
        self._update_camera()
        if self.mouse_captured:
            if self._holoverse_embedded:
                self._set_mouse_capture(True)
            else:
                self.doMethodLater(0.12, lambda task: (self._set_mouse_capture(True), task.done)[1], 'capture-mouse')
        # Standalone Anatomic owns its update task. HoloVerse drives embedded
        # Anatomic through the adapter's update(dt), preventing a second update loop.
        if not self._holoverse_embedded:
            if ARGS.perf_smoke or ARGS.reverse_perf_smoke or ARGS.impact_smoke or ARGS.combat_smoke or ARGS.melee_smoke or ARGS.sword_smoke or ARGS.pass34_smoke or ARGS.pass34_proof or ARGS.pass37_smoke or ARGS.pass38_smoke or ARGS.pass39_smoke or ARGS.pass40_smoke or ARGS.pass44_smoke or ARGS.pass45_smoke:
                self.taskMgr.remove('igLoop')
            self.taskMgr.add(self._update, 'ascii-matter-fps-update')


    # ---------- WORLD ----------
    def _box(self, name, center, size, color):
        sx, sy, sz = size[0] / 2, size[1] / 2, size[2] / 2
        faces = [
            ((-sx,-sy,-sz),( sx,-sy,-sz),( sx,-sy, sz),(-sx,-sy, sz),(0,-1,0)),
            (( sx, sy,-sz),(-sx, sy,-sz),(-sx, sy, sz),( sx, sy, sz),(0,1,0)),
            ((-sx, sy,-sz),(-sx,-sy,-sz),(-sx,-sy, sz),(-sx, sy, sz),(-1,0,0)),
            (( sx,-sy,-sz),( sx, sy,-sz),( sx, sy, sz),( sx,-sy, sz),(1,0,0)),
            ((-sx,-sy, sz),( sx,-sy, sz),( sx, sy, sz),(-sx, sy, sz),(0,0,1)),
            ((-sx, sy,-sz),( sx, sy,-sz),( sx,-sy,-sz),(-sx,-sy,-sz),(0,0,-1)),
        ]
        fmt = GeomVertexFormat.getV3n3()
        vd = GeomVertexData(name, fmt, Geom.UHStatic)
        vw = GeomVertexWriter(vd, 'vertex')
        nw = GeomVertexWriter(vd, 'normal')
        prim = GeomTriangles(Geom.UHStatic)
        idx = 0
        for a,b,c,d,n in faces:
            for v in (a,b,c,d):
                vw.addData3f(*v); nw.addData3f(*n)
            prim.addVertices(idx, idx+1, idx+2)
            prim.addVertices(idx, idx+2, idx+3)
            idx += 4
        g = Geom(vd); g.addPrimitive(prim)
        gn = GeomNode(name); gn.addGeom(g)
        np = self.render.attachNewNode(gn)
        np.setPos(*center); np.setColor(*color); np.setLightOff()
        return np

    def _build_black_world(self):
        # The room is intentionally almost featureless. A near-black floor supplies grounding and collision context
        # without turning the scene itself into ASCII or distracting from the glyph body.
        self.floor = self._box('black_floor', (0,0,-0.06), (WORLD_HALF*2, WORLD_HALF*2, 0.12), (0.006,0.007,0.009,1))
        # Four extremely dark boundary slabs keep FPS movement contained while disappearing into the black world.
        wall = (0.003, 0.004, 0.006, 1)
        self._box('north_wall', (0, WORLD_HALF, 2.2), (WORLD_HALF*2, 0.15, 4.4), wall)
        self._box('south_wall', (0,-WORLD_HALF, 2.2), (WORLD_HALF*2, 0.15, 4.4), wall)
        self._box('west_wall', (-WORLD_HALF,0,2.2), (0.15,WORLD_HALF*2,4.4), wall)
        self._box('east_wall', ( WORLD_HALF,0,2.2), (0.15,WORLD_HALF*2,4.4), wall)

    # ---------- AUDIO ----------
    def _load_weapon_audio(self):
        """Load all replaceable combat WAVs into independent polyphonic voice pools.

        Normal gameplay enters ShowBase with Panda3D OpenAL already selected.  We then use
        ShowBase's own SFX manager and remove the old global concurrency ceiling: concurrency
        is bounded by the individual voice pools instead, so an arm swish, sword whoosh, sword
        hum, gunshot and impact can coexist without unrelated cues stealing one another.  A
        pool only ever reuses one of its own voices when every voice in that *same cue* is busy.
        """
        self.weapon_sfx = {}
        self.audio_available = False
        self.weapon_audio_backend = 'disabled'
        self.weapon_audio_cursor = {}
        self.weapon_audio_generation = {}
        self.sword_hum = None
        self.weapon_audio_specs = {
            'left_fire':  'assets/audio/weapons/left_hologun_fire.wav',
            'right_fire': 'assets/audio/weapons/right_hologun_fire.wav',
            'left_impact':  'assets/audio/weapons/left_hologun_impact.wav',
            'right_impact': 'assets/audio/weapons/right_hologun_impact.wav',
            'left_arm_move': 'assets/audio/melee/left_arm_move.wav',
            'right_arm_move': 'assets/audio/melee/right_arm_move.wav',
            'sword_move': 'assets/audio/melee/sword_move.wav',
            'fist_impact': 'assets/audio/melee/fist_impact.wav',
            'sword_impact': 'assets/audio/melee/sword_impact.wav',
        }
        self.weapon_audio_pool_sizes = {
            'left_fire': WEAPON_AUDIO_POOL_FIRE,
            'right_fire': WEAPON_AUDIO_POOL_FIRE,
            'left_impact': WEAPON_AUDIO_POOL_IMPACT,
            'right_impact': WEAPON_AUDIO_POOL_IMPACT,
            'left_arm_move': MELEE_AUDIO_POOL_ARM,
            'right_arm_move': MELEE_AUDIO_POOL_ARM,
            'sword_move': MELEE_AUDIO_POOL_SWORD,
            'fist_impact': WEAPON_AUDIO_POOL_IMPACT,
            'sword_impact': WEAPON_AUDIO_POOL_IMPACT,
        }
        self.weapon_audio_volumes = {
            'left_fire': .64, 'right_fire': .64,
            'left_impact': .74, 'right_impact': .74,
            'left_arm_move': .30, 'right_arm_move': .30,
            'sword_move': .46,
            'fist_impact': .78, 'sword_impact': .82,
        }
        self._winsound = None
        if ARGS.no_audio or ARGS.safe_mode or ENGINE_SMOKE:
            return

        try:
            # Use ShowBase's SFX manager. It was created from p3openal_audio during normal
            # startup, which is Panda3D's documented configuration path.  This avoids the
            # Pass 35 failure mode where a second manager was requested only after the
            # application had already booted with the null backend.
            mgr = self.sfxManagerList[0] if getattr(self, 'sfxManagerList', None) else None
            if mgr is not None and mgr.isValid():
                mgr.setActive(True)
                if not self._holoverse_embedded:
                    # Standalone Anatomic may configure its audio manager. Embedded mode
                    # shares HoloVerse's manager and must not mutate host-wide policy.
                    mgr.setConcurrentSoundLimit(0)
                    mgr.setCacheLimit(AUDIO_CACHE_LIMIT)
                    mgr.setVolume(0.86)
                for key, rel in self.weapon_audio_specs.items():
                    path = ROOT / rel
                    if not path.exists():
                        continue
                    count = int(self.weapon_audio_pool_sizes[key])
                    voices=[]
                    filename=Filename.fromOsSpecific(str(path))
                    for _ in range(count):
                        snd=mgr.getSound(filename, False, AudioManager.SM_sample)
                        if snd is not None:
                            snd.setVolume(float(self.weapon_audio_volumes[key]))
                            voices.append(snd)
                    if voices:
                        self.weapon_sfx[key]=voices
                        self.weapon_audio_cursor[key]=0
                        self.weapon_audio_generation[key]=[0 for _ in voices]

                hum_path=ROOT/'assets/audio/melee/sword_hum_loop.wav'
                if hum_path.exists():
                    hum=mgr.getSound(Filename.fromOsSpecific(str(hum_path)), False, AudioManager.SM_sample)
                    if hum is not None:
                        hum.setVolume(.16)
                        hum.setLoop(True)
                        self.sword_hum=hum

                if self.weapon_sfx:
                    self.weapon_audio_manager=mgr
                    self.audio_available=True
                    self.weapon_audio_backend='showbase_openal_polyphonic'
                    _checkpoint('audio_backend_ready', self.weapon_audio_backend)
                    print(f'ASCII_MATTER_AUDIO_BACKEND={self.weapon_audio_backend} cues={len(self.weapon_sfx)} global_limit=unlimited valid={int(mgr.isValid())}')
                    self._sync_sword_hum()
                    return
        except Exception as exc:
            print(f'ASCII_MATTER_AUDIO_OPENAL_FAILED={type(exc).__name__}: {exc}', file=sys.stderr)

        # Deliberately do not fall back to winsound.PlaySound here.  Win32 PlaySound is a
        # single asynchronous lane and was the source of cues overriding one another.  A
        # missing OpenAL backend now fails silent instead of pretending to support polyphony.
        print('ASCII_MATTER_AUDIO_DISABLED=polyphonic_backend_unavailable', file=sys.stderr)

    def _update_audio(self):
        mgr=self.weapon_audio_manager
        if mgr is not None:
            try:
                mgr.update()
            except Exception as exc:
                print(f'ASCII_MATTER_AUDIO_UPDATE_FAILED={type(exc).__name__}: {exc}', file=sys.stderr)
                self.weapon_audio_manager=None
                self.audio_available=False

    def _play_weapon_sfx(self, key, volume_scale=1.0, play_rate=1.0):
        if ARGS.no_audio or ARGS.safe_mode or ENGINE_SMOKE:
            return False
        voices=self.weapon_sfx.get(key)
        if not voices:
            return False
        cursor=self.weapon_audio_cursor.get(key,0) % len(voices)
        chosen=None
        # Prefer a finished voice so currently audible copies are never restarted merely
        # because round-robin wrapped.  If every copy is busy, reuse only the oldest voice
        # from this cue; unrelated cue pools remain untouched.
        for step in range(len(voices)):
            idx=(cursor+step)%len(voices)
            try:
                if voices[idx].status()!=AudioSound.PLAYING:
                    chosen=idx
                    break
            except Exception:
                chosen=idx
                break
        if chosen is None:
            gens=self.weapon_audio_generation.get(key,[0 for _ in voices])
            chosen=min(range(len(voices)), key=lambda i: gens[i] if i < len(gens) else 0)
        snd=voices[chosen]
        self.weapon_audio_cursor[key]=(chosen+1)%len(voices)
        gens=self.weapon_audio_generation.setdefault(key,[0 for _ in voices])
        if len(gens)!=len(voices):
            gens[:]=[0 for _ in voices]
        generation=max(gens, default=0)+1
        gens[chosen]=generation
        try:
            snd.stop()
            snd.setTime(0.0)
            snd.setVolume(max(0.0,min(1.0,float(self.weapon_audio_volumes.get(key,.6))*float(volume_scale))))
            snd.setPlayRate(max(.25,min(2.0,float(play_rate))))
            snd.play()
            return True
        except Exception as exc:
            print(f'ASCII_MATTER_SFX_POOL_FAILED={key}:{type(exc).__name__}: {exc}', file=sys.stderr)
            return False

    def _sync_sword_hum(self):
        hum=self.sword_hum
        if hum is None:
            return
        should_play=(self.combat_mode=='melee' and not (ARGS.no_audio or ARGS.safe_mode or ENGINE_SMOKE))
        try:
            if should_play:
                if hum.status()!=AudioSound.PLAYING:
                    hum.play()
            elif hum.status()==AudioSound.PLAYING:
                hum.stop()
        except Exception as exc:
            print(f'ASCII_MATTER_SWORD_HUM_FAILED={type(exc).__name__}: {exc}', file=sys.stderr)

    def _tick_melee_motion_audio(self, side, target, dt, sword=False):
        """Emit restrained movement swishes from actual held-arm travel.

        The arm and sword use separate cue pools.  Right-hand movement can therefore emit an
        arm swish and sword whoosh on the same frame, on top of any gun/impact sounds already
        playing.  Distance accumulation and a short cooldown prevent frame-rate-dependent spam.
        """
        self.melee_audio_cooldown[side]=max(0.0,self.melee_audio_cooldown.get(side,0.0)-max(0.0,float(dt)))
        current=_v3(target)
        prev=self.melee_audio_last_target.get(side)
        self.melee_audio_last_target[side]=Vec3(current)
        if prev is None:
            return
        delta=(current-_v3(prev)).length()
        if delta<=1e-5:
            return
        self.melee_audio_motion_accum[side]=self.melee_audio_motion_accum.get(side,0.0)+delta
        threshold=SWORD_MOTION_SOUND_DISTANCE if sword else ARM_MOTION_SOUND_DISTANCE
        if self.melee_audio_cooldown[side]>0.0 or self.melee_audio_motion_accum[side]<threshold:
            return
        magnitude=min(1.0,self.melee_audio_motion_accum[side]/max(threshold,1e-6))
        self.melee_audio_motion_accum[side]=0.0
        self.melee_audio_cooldown[side]=SWORD_MOTION_SOUND_COOLDOWN if sword else ARM_MOTION_SOUND_COOLDOWN
        rate=.94+.11*min(1.0,delta/max(threshold,1e-6))
        self._play_weapon_sfx(side+'_arm_move', .72+.28*magnitude, rate)
        if sword:
            # Intentionally overlaps the right-arm cue rather than replacing it.
            self._play_weapon_sfx('sword_move', .78+.22*magnitude, 1.0+.06*min(1.0,delta/max(threshold,1e-6)))

    # ---------- HOLOGRAPHIC VIEWMODELS ----------
    def _triangle_prism(self, name, length=.42, width=.055, height=.045):
        half = length * 0.5
        w = width * 0.5
        h = height * 0.5
        front = [Vec3(-w, -half, -h), Vec3(w, -half, -h), Vec3(0.0, -half, h)]
        back = [Vec3(-w, half, -h), Vec3(w, half, -h), Vec3(0.0, half, h)]
        faces = [
            (0, 1, 2), (5, 4, 3),
            (0, 3, 4), (0, 4, 1),
            (1, 4, 5), (1, 5, 2),
            (2, 5, 3), (2, 3, 0),
        ]
        pts = front + back
        fmt = GeomVertexFormat.getV3n3()
        vd = GeomVertexData(name, fmt, Geom.UHStatic)
        vw = GeomVertexWriter(vd, 'vertex')
        nw = GeomVertexWriter(vd, 'normal')
        prim = GeomTriangles(Geom.UHStatic)
        for ia, ib, ic in faces:
            a, b, c = pts[ia], pts[ib], pts[ic]
            n = (b - a).cross(c - a)
            if n.lengthSquared() <= 1e-10:
                continue
            n.normalize()
            base = vw.getWriteRow()
            for v in (a, b, c):
                vw.addData3f(v)
                nw.addData3f(n)
            prim.addVertices(base, base + 1, base + 2)
        geom = Geom(vd)
        geom.addPrimitive(prim)
        gn = GeomNode(name)
        gn.addGeom(geom)
        return NodePath(gn)

    def _weapon_box(self, name, sx=.08, sy=.08, sz=.08):
        x = sx * 0.5
        y = sy * 0.5
        z = sz * 0.5
        pts = [
            Vec3(-x, -y, -z), Vec3(x, -y, -z), Vec3(x, y, -z), Vec3(-x, y, -z),
            Vec3(-x, -y, z), Vec3(x, -y, z), Vec3(x, y, z), Vec3(-x, y, z),
        ]
        faces = [
            (0, 1, 2), (0, 2, 3),
            (4, 7, 6), (4, 6, 5),
            (0, 4, 5), (0, 5, 1),
            (1, 5, 6), (1, 6, 2),
            (2, 6, 7), (2, 7, 3),
            (3, 7, 4), (3, 4, 0),
        ]
        fmt = GeomVertexFormat.getV3n3()
        vd = GeomVertexData(name, fmt, Geom.UHStatic)
        vw = GeomVertexWriter(vd, 'vertex')
        nw = GeomVertexWriter(vd, 'normal')
        prim = GeomTriangles(Geom.UHStatic)
        for ia, ib, ic in faces:
            a, b, c = pts[ia], pts[ib], pts[ic]
            n = (b - a).cross(c - a)
            if n.lengthSquared() <= 1e-10:
                continue
            n.normalize()
            base = vw.getWriteRow()
            for v in (a, b, c):
                vw.addData3f(v)
                nw.addData3f(n)
            prim.addVertices(base, base + 1, base + 2)
        geom = Geom(vd)
        geom.addPrimitive(prim)
        gn = GeomNode(name)
        gn.addGeom(geom)
        return NodePath(gn)

    def _build_weapon_prototype(self):
        self.weapon_body_parts = []
        receiver = self._weapon_box('rifle_receiver', .12, .46, .09)
        receiver.setPos(0.0, 0.02, 0.0)
        self.weapon_body_parts.append(receiver)
        stock = self._triangle_prism('rifle_stock', .26, .10, .10)
        stock.setPos(0.0, -0.24, -0.005); stock.setP(90)
        self.weapon_body_parts.append(stock)
        grip = self._triangle_prism('rifle_grip', .14, .085, .095)
        grip.setPos(0.0, -0.02, -0.085); grip.setP(180)
        self.weapon_body_parts.append(grip)
        fore = self._weapon_box('rifle_fore', .07, .50, .055)
        fore.setPos(0.0, 0.34, 0.0)
        self.weapon_body_parts.append(fore)
        barrel = self._weapon_box('rifle_barrel', .026, .82, .026)
        barrel.setPos(0.0, 0.68, 0.002)
        self.weapon_body_parts.append(barrel)
        rail = self._triangle_prism('rifle_top_rail', .30, .045, .032)
        rail.setPos(0.0, 0.14, 0.072)
        self.weapon_body_parts.append(rail)
        muzzle = self._triangle_prism('rifle_muzzle', .14, .038, .028)
        muzzle.setPos(0.0, 1.06, 0.002)
        self.weapon_body_parts.append(muzzle)
        self.weapon_shard_proto = self._triangle_prism('rifle_shard', .38, .040, .060)
        self.weapon_muzzle_local = Vec3(0.0, 1.18, 0.002)

    def _make_holographic_rifle(self):
        spec = self.weapon_modes[self.current_weapon_mode]
        root = self.camera.attachNewNode('holographic_rifle')
        visual = root.attachNewNode('rifle_visual')
        glow = visual.attachNewNode('rifle_glow')
        glow.setTransparency(TransparencyAttrib.MAlpha)
        glow.setLightOff(); glow.setDepthWrite(False); glow.setDepthTest(False); glow.setBin('fixed', 28)
        glow_card = CardMaker('rifle_glow_card')
        glow_card.setFrame(-.12, .12, -.035, .035)
        glow_np = glow.attachNewNode(glow_card.generate())
        glow_np.setP(90); glow_np.setPos(0.0, .58, .005); glow_np.setColor(*spec['glow'])
        self.weapon_palette_glow = glow_np
        fill_root = visual.attachNewNode('rifle_fill')
        wire_root = visual.attachNewNode('rifle_wire')
        for part in self.weapon_body_parts:
            fill = part.copyTo(fill_root)
            fill.setColor(*spec['fill']); fill.setTransparency(TransparencyAttrib.MAlpha); fill.setTwoSided(True)
            fill.setLightOff(); fill.setDepthWrite(False); fill.setDepthTest(False); fill.setBin('fixed', 30)
            self.weapon_fill_nodes.append(fill)
            wire = part.copyTo(wire_root)
            wire.setColor(*spec['wire']); wire.setTransparency(TransparencyAttrib.MAlpha); wire.setTwoSided(True)
            wire.setLightOff(); wire.setDepthWrite(False); wire.setDepthTest(False); wire.setRenderModeWireframe(); wire.setBin('fixed', 31)
            self.weapon_wire_nodes.append(wire)
        # All receiver pieces move as one viewmodel. Flattening only these static siblings
        # reduces draw submissions without touching the independently spinning shards.
        fill_root.flattenStrong(); wire_root.flattenStrong()
        self.weapon_static_fill = fill_root; self.weapon_static_wire = wire_root
        self.weapon_fill_nodes = [fill_root]
        self.weapon_wire_nodes = [wire_root]
        shard_specs = ((0.00, 8.0, 1.0), (0.10, -10.5, -1.0), (-0.09, 13.0, 1.0))
        for idx, (yoff, tilt, direction) in enumerate(shard_specs):
            spinner = visual.attachNewNode(f'rifle_spinner_{idx}')
            spinner.setPos(0.0, 0.78 + yoff, 0.0); spinner.setR(idx * 120.0)
            self.weapon_spinner_groups.append((spinner, 135.0 + idx * 28.0, direction))
            for ring in (0.0, 120.0, 240.0):
                pivot = spinner.attachNewNode(f'shard_pivot_{idx}_{int(ring)}')
                pivot.setR(ring)
                offset = pivot.attachNewNode(f'shard_offset_{idx}_{int(ring)}')
                offset.setPos(0.083, 0.0, 0.0); offset.setP(tilt)
                fill = offset.attachNewNode(self.weapon_shard_proto.node().makeCopy())
                fill.setColor(*spec['fill']); fill.setTransparency(TransparencyAttrib.MAlpha); fill.setTwoSided(True)
                fill.setLightOff(); fill.setDepthWrite(False); fill.setDepthTest(False); fill.setBin('fixed', 30)
                self.weapon_fill_nodes.append(fill)
                wire = offset.attachNewNode(self.weapon_shard_proto.node().makeCopy())
                wire.setColor(*spec['wire']); wire.setTransparency(TransparencyAttrib.MAlpha); wire.setTwoSided(True)
                wire.setLightOff(); wire.setDepthWrite(False); wire.setDepthTest(False); wire.setRenderModeWireframe(); wire.setBin('fixed', 31)
                self.weapon_wire_nodes.append(wire)
        self.weapon_root = root
        self.weapon_muzzle = root.attachNewNode('rifle_muzzle')
        self.weapon_muzzle.setPos(self.weapon_muzzle_local)
        self.weapon_base = (Vec3(.13, .72, -.30), 1.6, -2.0, 0.0)
        root.setPos(self.weapon_base[0]); root.setHpr(self.weapon_base[1], self.weapon_base[2], self.weapon_base[3])
        self._apply_weapon_palette()

    def _build_viewmodels(self):
        self._make_holographic_rifle()
        self._build_holographic_arms()
        self._set_combat_mode('rifle', announce=False)

    def _holo_piece(self, parent, name, size, color, fill_alpha=None, wire_alpha=None):
        """Create one cheap fill+wire holographic piece under a transform holder."""
        holder = parent.attachNewNode(name)
        proto = self._weapon_box(name+'_proto', *size)
        fill = proto.copyTo(holder)
        fa = MELEE_FILL_ALPHA if fill_alpha is None else float(fill_alpha)
        wa = color.w if wire_alpha is None else float(wire_alpha)
        fill.setColor(color.x, color.y, color.z, fa)
        fill.setTransparency(TransparencyAttrib.MAlpha); fill.setTwoSided(True)
        fill.setLightOff(); fill.setDepthWrite(False); fill.setDepthTest(False); fill.setBin('fixed', 30)
        wire = proto.copyTo(holder)
        wire.setColor(color.x, color.y, color.z, wa)
        wire.setTransparency(TransparencyAttrib.MAlpha); wire.setTwoSided(True)
        wire.setLightOff(); wire.setDepthWrite(False); wire.setDepthTest(False); wire.setRenderModeWireframe(); wire.setBin('fixed', 31)
        return holder

    def _holo_ring(self, parent, name, radius, color, segments=14, thickness=1.8):
        ls=LineSegs(name); ls.setThickness(thickness); ls.setColor(color.x,color.y,color.z,MELEE_DETAIL_ALPHA)
        for i in range(segments+1):
            a=(2.0*math.pi*i)/segments
            p=Vec3(math.cos(a)*radius,0.0,math.sin(a)*radius)
            if i==0: ls.moveTo(p)
            else: ls.drawTo(p)
        np=parent.attachNewNode(ls.create()); np.setLightOff(); np.setTransparency(TransparencyAttrib.MAlpha)
        np.setDepthWrite(False); np.setDepthTest(False); np.setBin('fixed',33)
        return np

    def _decorate_holo_limb(self, holder, side, color, forearm=False):
        """Add low-cost rails and a central energy spine without increasing IK complexity."""
        sign=-1.0 if side=='left' else 1.0
        rail_len=.92
        rails=[]
        for x in (-.052,.052):
            r=self._holo_piece(holder, f'{side}_{"fore" if forearm else "upper"}_rail_{len(rails)}',
                               (.018,rail_len,.018), color, .08, .78)
            r.setPos(x,0.0,.012 if forearm else .0); rails.append(r)
        spine=self._holo_piece(holder, f'{side}_{"fore" if forearm else "upper"}_energy_spine',
                               (.012,.86,.012), color, .22, .92)
        spine.setPos(0.0,0.0,-.035 if forearm else .035)
        fin=self._triangle_prism(f'{side}_arm_fin_proto', .22, .038, .045)
        for i,y in enumerate((-.22,.20)):
            n=holder.attachNewNode(f'{side}_{"fore" if forearm else "upper"}_fin_{i}')
            fin.copyTo(n); n.setPos(.058*sign,y,.0); n.setHpr(0,90,18*sign)
            n.setColor(color.x,color.y,color.z,.72); n.setTransparency(TransparencyAttrib.MAlpha)
            n.setLightOff(); n.setDepthWrite(False); n.setDepthTest(False); n.setRenderModeWireframe(); n.setBin('fixed',33)
        return rails+[spine]

    def _build_holo_fist(self, arm, side, color):
        """Build a clenched but anatomically readable holographic hand from separate palm/finger bones."""
        sign=-1.0 if side=='left' else 1.0
        hand=arm.attachNewNode(side+'_fist')
        palm=self._holo_piece(hand,side+'_palm',(.145,.125,.090),color,.18,.96)
        palm.setPos(0,.006,-.004)
        back=self._holo_piece(hand,side+'_hand_backplate',(.118,.082,.018),color,.10,.88)
        back.setPos(0,-.010,.054)
        heel=self._holo_piece(hand,side+'_palm_heel',(.112,.045,.072),color,.12,.84)
        heel.setPos(0,-.065,-.010)
        fingers=[]; knuckles=[]
        xs=(-.054,-.018,.018,.054)
        lengths=(.052,.058,.058,.049)
        for idx,(x,ln) in enumerate(zip(xs,lengths)):
            root=hand.attachNewNode(f'{side}_finger_{idx}')
            root.setPos(x,.040,.018)
            prox=self._holo_piece(root,f'{side}_finger_{idx}_prox',(.024,ln,.027),color,.14,.90)
            prox.setPos(0,.020,0); prox.setP(-20)
            mid=self._holo_piece(root,f'{side}_finger_{idx}_mid',(.023,.046,.025),color,.12,.86)
            mid.setPos(0,.054,-.020); mid.setP(-58)
            tip=self._holo_piece(root,f'{side}_finger_{idx}_tip',(.022,.032,.023),color,.13,.86)
            tip.setPos(0,.079,-.045); tip.setP(-78)
            cap=self._holo_piece(hand,f'{side}_knuckle_{idx}',(.029,.031,.032),color,.22,1.0)
            cap.setPos(x,.073,.040)
            fingers.append((prox,mid,tip)); knuckles.append(cap)
        thumb=hand.attachNewNode(side+'_thumb')
        thumb.setPos(-sign*.072,.017,-.004); thumb.setHpr(24*sign,-28,-24*sign)
        t0=self._holo_piece(thumb,side+'_thumb_metacarpal',(.034,.064,.034),color,.16,.92)
        t0.setPos(0,.022,0)
        t1=self._holo_piece(thumb,side+'_thumb_distal',(.031,.052,.031),color,.15,.92)
        t1.setPos(sign*.018,.066,-.012); t1.setHpr(20*sign,-32,0)
        cuff=self._holo_piece(hand,side+'_wrist_cuff',(.122,.035,.086),color,.10,.88)
        cuff.setPos(0,-.090,-.004)
        ring=self._holo_ring(hand,side+'_wrist_ring',.061,color,16,1.7); ring.setY(-.108)
        emitter=self._triangle_prism(side+'_fist_emitter_proto',.090,.045,.032)
        en=hand.attachNewNode(side+'_fist_emitter'); emitter.copyTo(en); en.setPos(0,-.018,.075); en.setP(90)
        en.setColor(color.x,color.y,color.z,.80); en.setTransparency(TransparencyAttrib.MAlpha)
        en.setLightOff(); en.setDepthWrite(False); en.setDepthTest(False); en.setRenderModeWireframe(); en.setBin('fixed',33)
        strike_tip=hand.attachNewNode(side+'_strike_tip'); strike_tip.setPos(0,.112,.020)
        return hand, fingers, knuckles, (t0,t1), ring, strike_tip

    def _build_laser_sword(self, hand):
        """Attach a long-reach volumetric hardlight sword to the right fist."""
        root=hand.attachNewNode('right_laser_sword')
        root.setPos(0.0,.035,.010)
        grip=self._holo_piece(root,'sword_grip',(.050,SWORD_HILT_LENGTH,.050),MELEE_RIGHT,.20,.98); grip.setY(.105)
        pommel=self._holo_piece(root,'sword_pommel',(.068,.050,.068),MELEE_RIGHT,.16,.94); pommel.setY(.010)
        guard=self._holo_piece(root,'sword_guard',(.205,.032,.038),MELEE_RIGHT,.18,.98); guard.setY(.205)
        emitter=self._holo_ring(root,'sword_emitter_ring',.074,MELEE_RIGHT,18,2.0); emitter.setY(.225)
        start=.225; end=start+SWORD_BLADE_LENGTH; center=(start+end)*.5
        # Real thin prisms remain readable in TinyDisplay and on hardware renderers;
        # a cyan translucent envelope surrounds an almost-white energetic core.
        glow=self._holo_piece(root,'laser_sword_glow_volume',(.082,SWORD_BLADE_LENGTH,.050),SWORD_GLOW,.13,.42); glow.setY(center)
        edge=self._holo_piece(root,'laser_sword_edge_volume',(.052,SWORD_BLADE_LENGTH,.036),SWORD_EDGE,.23,.82); edge.setY(center)
        core=self._holo_piece(root,'laser_sword_core_volume',(.022,SWORD_BLADE_LENGTH*.99,.022),SWORD_CORE,.78,1.0); core.setY(center)
        base=root.attachNewNode('sword_blade_base'); base.setPos(0,start+.02,0)
        tip=root.attachNewNode('sword_blade_tip'); tip.setPos(0,end,0)
        self.sword_root=root; self.sword_blade_glow=glow; self.sword_blade_core=core; self.sword_blade_edge=edge; self.sword_base=base; self.sword_tip=tip
        return root,base,tip

    def _build_holographic_arms(self):
        root = self.camera.attachNewNode('holographic_melee_arms')
        root.setDepthWrite(False); root.setDepthTest(False); root.setBin('fixed', 32)
        self.melee_root = root
        for side, sign, color in (('left', -1.0, MELEE_LEFT), ('right', 1.0, MELEE_RIGHT)):
            arm = root.attachNewNode(side+'_arm_root')
            shoulder = Vec3(MELEE_SHOULDER_X*sign, 0.18, -0.205)
            upper = self._holo_piece(arm, side+'_upper_arm', (.088, 1.0, .092), color,.15,.92)
            fore = self._holo_piece(arm, side+'_forearm', (.078, 1.0, .082), color,.15,.92)
            self._decorate_holo_limb(upper,side,color,False)
            self._decorate_holo_limb(fore,side,color,True)
            shoulder_cap = self._holo_piece(arm,side+'_shoulder_cap',(.145,.125,.145),color,.13,.90)
            shoulder_ring = self._holo_ring(arm,side+'_shoulder_ring',.078,color,16,1.6)
            elbow = self._holo_piece(arm, side+'_elbow', (.112, .096, .112), color,.16,.98)
            elbow_ring = self._holo_ring(arm,side+'_elbow_ring',.058,color,14,1.6)
            wrist = self._holo_piece(arm, side+'_wrist', (.090, .070, .090), color,.14,.94)
            fist,fingers,knuckles,thumb,wrist_ring,strike_tip = self._build_holo_fist(arm,side,color)
            self.melee_arms[side]={
                'root':arm,'shoulder':shoulder,'base_shoulder':Vec3(shoulder),'upper':upper,'fore':fore,'elbow':elbow,'wrist':wrist,'fist':fist,
                'knuckles':knuckles,'fingers':fingers,'thumb':thumb,'shoulder_cap':shoulder_cap,'shoulder_ring':shoulder_ring,
                'elbow_ring':elbow_ring,'wrist_ring':wrist_ring,'strike_tip':strike_tip,'color':color,'last_target':Vec3(0,MELEE_NEUTRAL_Y,-.18)
            }
            if side=='right':
                sword,blade_base,blade_tip=self._build_laser_sword(fist)
                self.melee_arms[side]['sword']=sword; self.melee_arms[side]['blade_base']=blade_base; self.melee_arms[side]['blade_tip']=blade_tip
        self._update_melee_pose('left', Vec3(-MELEE_NEUTRAL_X, MELEE_NEUTRAL_Y, -.18))
        self._update_melee_pose('right', Vec3(MELEE_NEUTRAL_X, MELEE_NEUTRAL_Y, -.18))
        root.hide()

    @staticmethod
    def _clamp_vec_length(v, low, high):
        out=_v3(v); length=out.length()
        if length < 1e-8: return Vec3(0, high, 0)
        target=max(low,min(high,length)); out *= target/length
        return out

    def _solve_two_bone(self, shoulder, target, side):
        """Analytic two-bone IK in camera-local space with a stable outward/down elbow pole."""
        sign=-1.0 if side=='left' else 1.0
        delta=self._clamp_vec_length(target-shoulder, MELEE_MIN_REACH, min(MELEE_MAX_REACH, MELEE_UPPER_ARM_LEN+MELEE_FOREARM_LEN-.015))
        dist=delta.length(); direction=delta/dist
        support=getattr(self,'melee_body_solver',{})
        pole=Vec3(.75*sign + float(support.get('elbow_x',0.0))*sign, -.05, -.58 + float(support.get('elbow_z',0.0)))
        perp=pole-direction*direction.dot(pole)
        if perp.lengthSquared()<1e-7: perp=Vec3(sign,0,-.4)
        perp.normalize()
        a=MELEE_UPPER_ARM_LEN; b=MELEE_FOREARM_LEN
        along=(a*a - b*b + dist*dist)/(2.0*dist)
        height=math.sqrt(max(0.0,a*a-along*along))
        elbow=shoulder + direction*along + perp*height
        wrist=shoulder+delta
        return elbow,wrist

    def _place_bone_piece(self, node, a, b, width=.070):
        a=_v3(a); b=_v3(b); d=b-a; length=max(.001,d.length())
        mid=(a+b)*.5
        node.setPos(mid); node.lookAt(b); node.setScale(1.0, length, 1.0)

    def _melee_charge_blend(self, side):
        return max(0.0,min(1.0,float(self.melee_hold_time.get(side,0.0))/MELEE_FULL_CHARGE_TIME))

    def _melee_gesture_travel(self, side):
        path=self.melee_paths.get(side,())
        return sum(math.hypot(b[0]-a[0],b[1]-a[1]) for a,b in zip(path[:-1],path[1:]))

    @staticmethod
    def _body_solver_move(current, target, rate, dt):
        a=max(0.0,min(1.0,float(rate)*max(0.0,float(dt))))
        return float(current)+(float(target)-float(current))*a

    def _body_solver_motion_probe(self, side):
        """Return (current_target, future_target, source) without changing playback state."""
        if self.melee_hold.get(side):
            current=_v3(self._melee_target_from_cursor(side))
            prev=_v3(self.melee_arms.get(side,{}).get('last_target',current))
            future=current+(current-prev)*2.25
            return current,future,'recording'
        pb=self.melee_playback.get(side)
        if not pb: return None
        if pb.get('mode')=='recorded':
            source_time=min(pb['duration'],float(pb.get('elapsed',0.0))*float(pb.get('speed',MELEE_REPLAY_SPEED)))
            now=self._sample_recorded_motion(pb.get('samples',()),source_time)
            ahead=self._sample_recorded_motion(pb.get('samples',()),min(pb['duration'],source_time+BODY_SOLVER_LOOKAHEAD))
            if now and ahead: return _v3(now[0]),_v3(ahead[0]),str(pb.get('source','recorded'))
        else:
            targets=pb.get('targets',())
            idx=min(int(pb.get('index',0)),max(0,len(targets)-1))
            if targets:
                return _v3(targets[idx]),_v3(targets[min(idx+1,len(targets)-1)]),'authored'
        return None

    def _update_melee_body_solver(self, dt):
        """Solve torso/hip/shoulder intent around the exact recorded hand path."""
        contributions=[]
        if ARGS.no_body_solver:
            goal={k:0.0 for k in ('torso_h','torso_p','torso_r','hip_h','stance_x','stance_y','shoulder_z','shoulder_y','elbow_x','elbow_z','intensity')}
            self.melee_body_solver_goal=goal
            for key,val in goal.items(): self.melee_body_solver[key]=self._body_solver_move(self.melee_body_solver.get(key,0.0),val,BODY_SOLVER_RELEASE_RESPONSE,dt)
            self.melee_body_solver_debug={'source':'disabled','velocity':Vec3(0,0,0),'active_side':None}
            return
        for side in ('left','right'):
            probe=self._body_solver_motion_probe(side)
            if not probe: continue
            current,future,source=probe
            delta=future-current
            speed=delta.length()/max(1e-6,BODY_SOLVER_LOOKAHEAD)
            motion=min(1.0,speed/BODY_SOLVER_SPEED_REF)
            reach=min(1.0,max(0.0,current.y-MELEE_NEUTRAL_Y)/BODY_SOLVER_REACH_REF)
            intensity=max(.12 if self.melee_hold.get(side) else .0,min(1.0,.72*motion+.28*reach))
            contributions.append((intensity,side,current,delta,source))
        goal={k:0.0 for k in ('torso_h','torso_p','torso_r','hip_h','stance_x','stance_y','shoulder_z','shoulder_y','elbow_x','elbow_z','intensity')}
        active_side=None; velocity=Vec3(0,0,0); source='idle'
        if contributions:
            intensity,active_side,current,delta,source=max(contributions,key=lambda q:q[0])
            velocity=delta/max(1e-6,BODY_SOLVER_LOOKAHEAD)
            vx=max(-1.0,min(1.0,velocity.x/BODY_SOLVER_SPEED_REF))
            vz=max(-1.0,min(1.0,velocity.z/BODY_SOLVER_SPEED_REF))
            vy=max(-1.0,min(1.0,velocity.y/BODY_SOLVER_SPEED_REF))
            sign=-1.0 if active_side=='left' else 1.0
            torso_h=(-vx*BODY_SOLVER_MAX_TORSO_H + sign*vy*2.2)*intensity
            torso_p=(-vz*BODY_SOLVER_MAX_TORSO_P - max(0.0,vy)*2.0)*intensity
            torso_r=(-vx*BODY_SOLVER_MAX_TORSO_R + sign*vz*1.4)*intensity
            goal.update({
                'torso_h':torso_h,'torso_p':torso_p,'torso_r':torso_r,
                'hip_h':-torso_h*BODY_SOLVER_HIP_COUNTER,
                'stance_x':max(-BODY_SOLVER_MAX_STANCE_X,min(BODY_SOLVER_MAX_STANCE_X,-vx*BODY_SOLVER_MAX_STANCE_X*intensity)),
                'stance_y':max(-BODY_SOLVER_MAX_STANCE_Y,min(BODY_SOLVER_MAX_STANCE_Y,vy*BODY_SOLVER_MAX_STANCE_Y*intensity)),
                'shoulder_z':max(-BODY_SOLVER_MAX_SHOULDER_Z,min(BODY_SOLVER_MAX_SHOULDER_Z,vz*BODY_SOLVER_MAX_SHOULDER_Z*intensity)),
                'shoulder_y':max(-BODY_SOLVER_MAX_SHOULDER_Y,min(BODY_SOLVER_MAX_SHOULDER_Y,vy*BODY_SOLVER_MAX_SHOULDER_Y*intensity)),
                'elbow_x':max(-BODY_SOLVER_MAX_ELBOW_LEAD,min(BODY_SOLVER_MAX_ELBOW_LEAD,-vx*BODY_SOLVER_MAX_ELBOW_LEAD*intensity)),
                'elbow_z':max(-BODY_SOLVER_MAX_ELBOW_LEAD*.55,min(BODY_SOLVER_MAX_ELBOW_LEAD*.55,vz*BODY_SOLVER_MAX_ELBOW_LEAD*.55*intensity)),
                'intensity':intensity,
            })
        self.melee_body_solver_goal=goal
        rate=BODY_SOLVER_RESPONSE if contributions else BODY_SOLVER_RELEASE_RESPONSE
        state=self.melee_body_solver
        for key,val in goal.items(): state[key]=self._body_solver_move(state.get(key,0.0),val,rate,dt)
        self.melee_body_solver_debug={'source':source,'velocity':Vec3(velocity),'active_side':active_side}

    def _body_solver_shoulder(self, side):
        arm=self.melee_arms.get(side)
        if not arm: return Vec3(0,0,0)
        base=_v3(arm.get('base_shoulder',arm.get('shoulder',Vec3(0,0,0))))
        st=self.melee_body_solver
        h=math.radians(float(st.get('torso_h',0.0))); r=math.radians(float(st.get('torso_r',0.0)))
        x=base.x; y=base.y-.18; z=base.z+.205
        xh=x*math.cos(h)-y*math.sin(h); yh=x*math.sin(h)+y*math.cos(h)
        xr=xh*math.cos(r)-z*math.sin(r); zr=xh*math.sin(r)+z*math.cos(r)
        out=Vec3(xr+float(st.get('stance_x',0.0)), yh+.18+float(st.get('stance_y',0.0))+float(st.get('shoulder_y',0.0)), zr-.205+float(st.get('shoulder_z',0.0)))
        p=math.radians(float(st.get('torso_p',0.0)))
        yp=out.y-.18; zp=out.z+.205
        out.y=yp*math.cos(p)-zp*math.sin(p)+.18
        out.z=yp*math.sin(p)+zp*math.cos(p)-.205
        return out

    def _update_melee_pose(self, side, target):
        arm=self.melee_arms.get(side)
        if not arm: return
        shoulder=self._body_solver_shoulder(side); target=_v3(target)
        # Hand motion is sacred. If a torso-supported shoulder would make the recorded hand
        # unreachable, adjust only the virtual shoulder toward/away from that exact hand point.
        # This keeps the fist at the stored local transform instead of clamping the animation.
        reach_vec=target-shoulder; reach_len=reach_vec.length(); max_reach=min(MELEE_MAX_REACH,MELEE_UPPER_ARM_LEN+MELEE_FOREARM_LEN-.015)
        if reach_len>1e-8:
            direction=reach_vec/reach_len
            if reach_len>max_reach: shoulder += direction*(reach_len-max_reach+1e-5)
            elif reach_len<MELEE_MIN_REACH: shoulder -= direction*(MELEE_MIN_REACH-reach_len+1e-5)
        elbow,wrist=self._solve_two_bone(shoulder,target,side)
        self._place_bone_piece(arm['upper'], shoulder, elbow)
        self._place_bone_piece(arm['fore'], elbow, wrist)
        arm['shoulder_cap'].setPos(shoulder); arm['shoulder_ring'].setPos(shoulder)
        arm['elbow'].setPos(elbow); arm['elbow_ring'].setPos(elbow)
        arm['wrist'].setPos(wrist)
        hand=arm['fist']; hand.setPos(wrist)
        d=wrist-elbow
        aim=_v3(d)
        if side=='right' and self.melee_hold.get('right',False) and aim.lengthSquared()>1e-8:
            # A held sword should not sit vertically dominant in the view. Blend the wrist
            # direction toward camera-forward, then add only a small local pitch cant.
            aim.normalize()
            charge=self._melee_charge_blend('right')
            forward=Vec3(0,1,0)
            aim=aim*(1.0-SWORD_HOLD_FORWARD_BIAS*charge)+forward*(SWORD_HOLD_FORWARD_BIAS*charge)
            if aim.lengthSquared()>1e-8: aim.normalize()
        hand.lookAt(wrist+aim)
        prev=arm.get('last_target',target); gesture=target-prev
        side_sign=-1.0 if side=='left' else 1.0
        twist=max(-1.0,min(1.0,gesture.x*7.0))*MELEE_WRIST_TWIST_DEG
        hand.setR(hand.getR()+twist*side_sign)
        if side=='right' and self.melee_hold.get('right',False):
            hand.setP(hand.getP()+SWORD_HOLD_WRIST_PITCH_DEG*self._melee_charge_blend('right'))
        arm['last_target']=Vec3(target)
        arm['wrist_ring'].setPos(0,-.108,0)
        return wrist

    def _melee_target_from_cursor(self, side):
        x,z=self.melee_cursor[side]
        sign=-1.0 if side=='left' else 1.0
        charge=self._melee_charge_blend(side)
        travel=self._melee_gesture_travel(side)
        activity=max(abs(x),abs(z),min(1.0,travel/.48))
        reach=MELEE_HOLD_REACH_GAIN*charge*(MELEE_HOLD_REACH_BASE+(1.0-MELEE_HOLD_REACH_BASE)*min(1.0,activity))
        return Vec3(MELEE_NEUTRAL_X*sign + x*MELEE_GESTURE_X, MELEE_NEUTRAL_Y+reach, -.18 - z*MELEE_GESTURE_Z)

    def _melee_enemy_commit_target(self, side, fallback, charge):
        """Return a reachable camera-local strike point biased toward the live NPC.

        Gesture shape remains the wind-up authority; this only corrects the final committed
        segment so a release naturally travels outward/forward through the opponent instead
        of finishing off-line. No collision radius or damage authority is enlarged.
        """
        arm=self.melee_arms.get(side)
        if not arm or getattr(self,'body_root',None) is None:
            out=_v3(fallback); out.y=min(.86,out.y+.26+.10*charge); return out
        # Pick the reachable anatomical lane closest to the released gesture instead of
        # forcing every strike through one chest point.  High gestures naturally favor head,
        # low gestures favor abdomen, and center gestures favor sternum.
        root=self.body_root.getPos(self.render)
        zones=[root+Vec3(0,0,1.62), root+Vec3(0,0,1.27), root+Vec3(0,0,1.02)]
        local_zones=[_v3(self.camera.getRelativePoint(self.render,w)) for w in zones]
        local=min(local_zones,key=lambda q:(_v3(fallback)-q).lengthSquared())
        if local.y<=0.05 or local.length()>MELEE_AUTO_AIM_MAX_DISTANCE:
            out=_v3(fallback); out.y=min(.90,out.y+.29+.11*charge); return out
        sign=-1.0 if side=='left' else 1.0
        local.x += sign*MELEE_TARGET_SIDE_OFFSET
        shoulder=arm['shoulder']
        reachable=shoulder+self._clamp_vec_length(local-shoulder,MELEE_MIN_REACH,MELEE_MAX_REACH)
        assist=min(0.975,MELEE_AUTO_AIM_BLEND+.065*charge)
        out=_v3(fallback)*(1.0-assist)+reachable*assist
        out.y=max(out.y,min(reachable.y,MELEE_NEUTRAL_Y+.34+.06*charge))
        return out

    def _rebuild_melee_trail(self, side, points=None, alpha=0.92):
        old=self.melee_trails.get(side)
        if old is not None and not old.isEmpty(): old.removeNode()
        points=list(points if points is not None else self.melee_paths.get(side,()))
        if len(points)<2: self.melee_trails[side]=None; return
        color=MELEE_LEFT if side=='left' else MELEE_RIGHT
        ls=LineSegs('melee_trajectory_'+side); ls.setThickness(3.2); ls.setColor(color.x,color.y,color.z,min(MELEE_TRAIL_CORE_ALPHA,alpha))
        sign=-1.0 if side=='left' else 1.0
        first=True
        for px,pz in points:
            p=Vec3(MELEE_NEUTRAL_X*sign + px*MELEE_GESTURE_X, MELEE_NEUTRAL_Y+.02, -.18-pz*MELEE_GESTURE_Z)
            if first: ls.moveTo(p); first=False
            else: ls.drawTo(p)
        node=self.melee_root.attachNewNode(ls.create()); node.setLightOff(); node.setTransparency(TransparencyAttrib.MAlpha); node.setDepthWrite(False); node.setDepthTest(False); node.setBin('fixed',34)
        self.melee_trails[side]=node

    def _set_combat_mode(self, mode, announce=True):
        mode='melee' if str(mode).lower()=='melee' else 'rifle'
        self.combat_mode=mode
        if self.weapon_root is not None:
            self.weapon_root.hide() if mode=='melee' else self.weapon_root.show()
        if self.melee_root is not None:
            if mode=='melee':
                self.melee_raise_blend=0.0; self.melee_root.setZ(-.38); self.melee_root.show()
            else: self.melee_root.hide()
        if mode=='rifle':
            for side in ('left','right'):
                self.melee_hold[side]=False; self.melee_playback[side]=None
                self._rebuild_melee_trail(side,[])
            self.sword_tip_history=[]; self.sword_base_prev=None; self.sword_tip_prev=None
            self.sword_distortion_history=[]; self.sword_last_distortion_tip=None
            oldd=getattr(self,'sword_distortion_node',None)
            if oldd is not None and not oldd.isEmpty(): oldd.removeNode()
            self.sword_distortion_node=None
            old=getattr(self,'sword_trail_node',None)
            if old is not None and not old.isEmpty(): old.removeNode()
            self.sword_trail_node=None
        self._sync_sword_hum()
        if announce:
            self.last_hit='HOLO FIST + LASER SWORD RAISED' if mode=='melee' else 'HOLOGRAPHIC RIFLE READY'
            self._status()

    def toggle_combat_mode(self):
        if self.combo_composer_visible:
            return
        if self.motion_forge_visible:
            self._forge_mirror(); return
        self._set_combat_mode('melee' if self.combat_mode=='rifle' else 'rifle')

    @staticmethod
    def _recording_meta_defaults(recording=None):
        r=recording or {}
        return {
            'name':str(r.get('name') or MOTION_FORGE_DEFAULT_NAME)[:32],
            'playback_speed':max(MOTION_FORGE_MIN_SPEED,min(MOTION_FORGE_MAX_SPEED,float(r.get('playback_speed',MELEE_REPLAY_SPEED)))),
            'trim_start':max(0.0,float(r.get('trim_start',0.0))),
            'trim_end':max(0.0,float(r.get('trim_end',0.0))),
            'mirrored':bool(r.get('mirrored',False)),
        }

    def _serialize_melee_recording(self, recording):
        if not recording: return None
        meta=self._recording_meta_defaults(recording)
        return {
            'schema':'anatomic.melee_recording.v2',
            'side':str(recording.get('side','right')),
            'duration':float(recording.get('duration',0.0)),
            'travel':float(recording.get('travel',0.0)),
            **meta,
            'samples':[
                [float(q['t']), [float(v) for v in q['target']], [float(v) for v in q['hpr']]]
                for q in recording.get('samples',())
            ],
        }

    def _deserialize_melee_recording(self, data):
        try:
            if not isinstance(data,dict) or data.get('schema') not in ('anatomic.melee_recording.v1','anatomic.melee_recording.v2'): return None
            side='right' if str(data.get('side'))=='right' else 'left'
            samples=[]
            for row in data.get('samples',()):
                if not isinstance(row,(list,tuple)) or len(row)!=3: continue
                t=float(row[0]); target=Vec3(*[float(x) for x in row[1]]); hpr=Vec3(*[float(x) for x in row[2]])
                samples.append({'t':max(0.0,t),'target':target,'hpr':hpr})
            if len(samples)<2: return None
            samples.sort(key=lambda q:q['t'])
            base=samples[0]['t']
            for q in samples: q['t']-=base
            duration=max(0.001,float(samples[-1]['t']))
            out={'side':side,'duration':duration,'travel':float(data.get('travel',0.0)),'samples':samples}
            out.update(self._recording_meta_defaults(data))
            return out
        except Exception:
            return None

    @staticmethod
    def _combo_meta_defaults(combo=None):
        c=combo or {}
        seq=[]
        for raw in c.get('sequence',()):
            try:
                n=int(raw)
                if 1<=n<=MELEE_SLOT_COUNT and len(seq)<COMBO_MAX_MOVES: seq.append(n)
            except Exception:
                pass
        return {'name':str(c.get('name') or COMBO_DEFAULT_NAME)[:32],'sequence':seq}

    def _serialize_melee_combo(self, combo):
        if not combo: return None
        meta=self._combo_meta_defaults(combo)
        return {'schema':'anatomic.melee_combo.v1','name':meta['name'],'sequence':list(meta['sequence'])}

    def _deserialize_melee_combo(self, data):
        if not isinstance(data,dict): return None
        if data.get('schema') not in (None,'anatomic.melee_combo.v1'): return None
        out=self._combo_meta_defaults(data)
        return out if out['sequence'] else None

    @staticmethod
    def _combo_vec_clamp(v, max_len):
        q=_v3(v); ln=q.length()
        if ln>max_len and ln>1e-8: q*=float(max_len)/ln
        return q

    @staticmethod
    def _combo_angle_distance(a,b):
        aa=_v3(a); bb=_v3(b)
        def d(x,y): return abs(((float(y)-float(x)+180.0)%360.0)-180.0)
        return max(d(aa.x,bb.x),d(aa.y,bb.y),d(aa.z,bb.z))

    def _combo_transition_duration(self, end_sample, start_sample):
        dist=(_v3(start_sample['target'])-_v3(end_sample['target'])).length()
        ang=self._combo_angle_distance(end_sample['hpr'],start_sample['hpr'])
        dur=COMBO_TRANSITION_BASE+dist/COMBO_TRANSITION_POS_RATE+ang/COMBO_TRANSITION_ANGLE_RATE
        return max(COMBO_TRANSITION_MIN,min(COMBO_TRANSITION_MAX,dur))

    @staticmethod
    def _combo_hermite(p0,p1,v0,v1,duration,u):
        u=max(0.0,min(1.0,float(u))); u2=u*u; u3=u2*u
        h00=2*u3-3*u2+1; h10=u3-2*u2+u; h01=-2*u3+3*u2; h11=u3-u2
        return _v3(p0)*h00 + _v3(v0)*(duration*COMBO_TRANSITION_TANGENT_SCALE*h10) + _v3(p1)*h01 + _v3(v1)*(duration*COMBO_TRANSITION_TANGENT_SCALE*h11)

    @staticmethod
    def _combo_sample_velocity(samples, at_end=False):
        if not samples or len(samples)<2: return Vec3(0,0,0)
        a,b=(samples[-2],samples[-1]) if at_end else (samples[0],samples[1])
        dt=max(1e-5,float(b['t'])-float(a['t']))
        return ASCIIMatterLab._combo_vec_clamp((_v3(b['target'])-_v3(a['target']))/dt,COMBO_TRANSITION_MAX_TANGENT_SPEED)

    def _compile_melee_combo(self, combo):
        meta=self._combo_meta_defaults(combo); seq=list(meta['sequence'])
        if len(seq)<COMBO_MIN_MOVES: return None
        compiled=[]; windows=[]; transitions=[]; cursor=0.0; prev_move=None
        component_names=[]
        for order,slot in enumerate(seq):
            raw=self.melee_slots.get(int(slot)); eff=self._effective_melee_recording(raw) if raw else None
            if not eff or len(eff['samples'])<2: return None
            speed=max(MOTION_FORGE_MIN_SPEED,min(MOTION_FORGE_MAX_SPEED,float(eff.get('playback_speed',MELEE_REPLAY_SPEED))))
            move=[{'t':float(q['t'])/speed,'target':_v3(q['target']),'hpr':_v3(q['hpr'])} for q in eff['samples']]
            component_names.append(str(eff.get('name',f'SWORD MOTION {slot:02d}')))
            if prev_move is not None:
                td=self._combo_transition_duration(prev_move[-1],move[0]); steps=max(3,int(math.ceil(td/MELEE_RECORD_SAMPLE_DT)))
                v0=self._combo_sample_velocity(prev_move,True); v1=self._combo_sample_velocity(move,False)
                t0=cursor; p0=_v3(prev_move[-1]['target']); p1=_v3(move[0]['target']); h0=_v3(prev_move[-1]['hpr']); h1=_v3(move[0]['hpr'])
                for j in range(1,steps+1):
                    u=j/steps; e=u*u*(3.0-2.0*u); tt=t0+td*u
                    pos=self._combo_hermite(p0,p1,v0,v1,td,u)
                    hpr=Vec3(self._melee_angle_lerp(h0.x,h1.x,e),self._melee_angle_lerp(h0.y,h1.y,e),self._melee_angle_lerp(h0.z,h1.z,e))
                    compiled.append({'t':tt,'target':pos,'hpr':hpr})
                transitions.append((t0,t0+td)); cursor+=td
            move_start=cursor
            for j,q in enumerate(move):
                if j==0 and compiled and abs(float(compiled[-1]['t'])-cursor)<1e-7: continue
                compiled.append({'t':cursor+float(q['t']),'target':_v3(q['target']),'hpr':_v3(q['hpr'])})
            move_end=cursor+float(move[-1]['t'])
            windows.append({'start':move_start,'end':move_end,'slot':int(slot),'charge':max(0.0,min(1.0,float(eff['duration'])/MELEE_FULL_CHARGE_TIME)),'travel':float(eff.get('travel',0.0))})
            cursor=move_end; prev_move=move
        if len(compiled)<2: return None
        return {'side':'right','duration':max(.001,cursor),'travel':sum(float(w['travel']) for w in windows),'samples':compiled,'name':meta['name'],'playback_speed':1.0,'trim_start':0.0,'trim_end':0.0,'mirrored':False,'combo_windows':windows,'transition_ranges':transitions,'sequence':seq,'component_names':component_names}

    def _combo_window_at(self, pb, source_time, previous_time=None):
        for idx,w in enumerate(pb.get('combo_windows',())):
            if float(w['start'])-1e-6<=source_time<=float(w['end'])+1e-6:
                if previous_time is not None and previous_time<float(w['start'])-1e-6: return None
                return idx,w
        return None

    def _start_combo_playback(self, combo_slot, source='combo'):
        combo=self.melee_combos.get(int(combo_slot)); compiled=self._compile_melee_combo(combo) if combo else None
        if not compiled: return False
        started=self._start_recorded_melee_playback(compiled,source=f'{source}_{combo_slot}')
        if not started: return False
        pb=self.melee_playback.get('right')
        pb['combo_windows']=[dict(w) for w in compiled['combo_windows']]
        pb['transition_ranges']=list(compiled['transition_ranges']); pb['combo_slot']=int(combo_slot); pb['combo_sequence']=list(compiled['sequence'])
        pb['combo_hit_counts']={}; pb['combo_last_hit_times']={}; pb['last_sample_time']=0.0
        pb['name']=str(compiled['name'])
        return True

    def _load_melee_slots(self):
        slots={}
        try:
            if not MELEE_SLOT_PATH.exists(): return slots
            raw=json.loads(MELEE_SLOT_PATH.read_text(encoding='utf-8'))
            for key,val in (raw.get('slots',{}) if isinstance(raw,dict) else {}).items():
                n=int(key)
                if 1<=n<=MELEE_SLOT_COUNT:
                    rec=self._deserialize_melee_recording(val)
                    if rec and rec.get('side')=='right': slots[n]=rec
            self.melee_combos={}
            for key,val in (raw.get('combos',{}) if isinstance(raw,dict) else {}).items():
                try:
                    n=int(key)
                    combo=self._deserialize_melee_combo(val)
                    if 1<=n<=COMBO_SLOT_COUNT and combo: self.melee_combos[n]=combo
                except Exception:
                    continue
            self.active_combo_slot=max(1,min(COMBO_SLOT_COUNT,int(raw.get('active_combo_slot',1)))) if isinstance(raw,dict) else 1
        except Exception as exc:
            print(f'ANATOMIC_MELEE_SLOT_LOAD_WARNING={type(exc).__name__}:{exc}',file=sys.stderr)
        return slots

    def _save_melee_slots(self):
        try:
            MELEE_SLOT_PATH.parent.mkdir(parents=True,exist_ok=True)
            payload={'schema':'anatomic.melee_slots.v3','slots':{str(k):self._serialize_melee_recording(v) for k,v in sorted(self.melee_slots.items())},'combos':{str(k):self._serialize_melee_combo(v) for k,v in sorted(self.melee_combos.items())},'active_combo_slot':int(self.active_combo_slot)}
            tmp=MELEE_SLOT_PATH.with_suffix('.tmp')
            tmp.write_text(json.dumps(payload,indent=2),encoding='utf-8')
            os.replace(tmp,MELEE_SLOT_PATH)
            return True
        except Exception as exc:
            print(f'ANATOMIC_MELEE_SLOT_SAVE_WARNING={type(exc).__name__}:{exc}',file=sys.stderr)
            return False

    @staticmethod
    def _copy_melee_recording(recording):
        if not recording: return None
        out={
            'side':str(recording.get('side','right')),
            'duration':float(recording.get('duration',0.0)),
            'travel':float(recording.get('travel',0.0)),
            'samples':[{'t':float(q['t']),'target':_v3(q['target']),'hpr':_v3(q['hpr'])} for q in recording.get('samples',())],
        }
        out.update(ASCIIMatterLab._recording_meta_defaults(recording))
        return out

    def _effective_melee_recording(self, recording):
        """Build an edited clip while keeping the original captured samples untouched."""
        rec=self._copy_melee_recording(recording)
        if not rec or len(rec['samples'])<2: return None
        duration=max(.001,float(rec['duration']))
        start=max(0.0,min(duration-MOTION_FORGE_MIN_DURATION,float(rec.get('trim_start',0.0))))
        end=max(start+MOTION_FORGE_MIN_DURATION,min(duration,duration-float(rec.get('trim_end',0.0))))
        if end-start<MOTION_FORGE_MIN_DURATION: start=max(0.0,end-MOTION_FORGE_MIN_DURATION)
        points=[]
        first=self._sample_recorded_motion(rec['samples'],start); last=self._sample_recorded_motion(rec['samples'],end)
        if first: points.append({'t':0.0,'target':_v3(first[0]),'hpr':_v3(first[1])})
        for q in rec['samples']:
            if start < float(q['t']) < end:
                points.append({'t':float(q['t'])-start,'target':_v3(q['target']),'hpr':_v3(q['hpr'])})
        if last: points.append({'t':end-start,'target':_v3(last[0]),'hpr':_v3(last[1])})
        if len(points)<2: return None
        if rec.get('mirrored'):
            pivot=MELEE_NEUTRAL_X if rec.get('side')=='right' else -MELEE_NEUTRAL_X
            for q in points:
                q['target'].x=2.0*pivot-q['target'].x
                q['hpr']=Vec3(-q['hpr'].x,q['hpr'].y,-q['hpr'].z)
        return {'side':rec['side'],'duration':max(.001,end-start),'travel':float(rec.get('travel',0.0)),
                'samples':points,'playback_speed':float(rec.get('playback_speed',MELEE_REPLAY_SPEED)),
                'name':str(rec.get('name',MOTION_FORGE_DEFAULT_NAME)),'mirrored':bool(rec.get('mirrored',False)),
                'trim_start':start,'trim_end':max(0.0,duration-end),'raw_duration':duration}

    def _capture_melee_motion_sample(self, side, stamp=None, force=False):
        arm=self.melee_arms.get(side)
        if not arm: return
        stamp=float(self.melee_hold_time[side] if stamp is None else stamp)
        samples=self.melee_motion_recordings[side]
        if samples and not force and stamp-samples[-1]['t']<MELEE_RECORD_SAMPLE_DT: return
        target=_v3(arm.get('last_target',self._melee_target_from_cursor(side)))
        # Record the solved local hand position, not merely the requested cursor target.
        # Keeping the historical assignment above preserves the Pass 40 contract marker,
        # while this second assignment makes new recordings literal performance capture.
        if self.melee_root is not None:
            target=_v3(arm['fist'].getPos(self.melee_root))
        hpr=_v3(arm['fist'].getHpr())
        sample={'t':stamp,'target':target,'hpr':hpr}
        if samples and force and abs(stamp-samples[-1]['t'])<1e-6: samples[-1]=sample
        else: samples.append(sample)

    def _begin_melee_charge(self, side):
        if self.combat_mode!='melee': return
        # A new performance always begins from the weapon's authored starting pose.  This
        # guarantees that recorded and numbered playback have one stable local origin.
        self.melee_playback[side]=None
        sign=-1.0 if side=='left' else 1.0
        neutral=Vec3(MELEE_NEUTRAL_X*sign,MELEE_NEUTRAL_Y,-.18)
        self.melee_hold[side]=False
        self._update_melee_pose(side,neutral)
        self.melee_hold[side]=True; self.melee_hold_time[side]=0.0
        self.melee_cursor[side]=[0.0,0.0]; self.melee_paths[side]=[(0.0,0.0)]
        self.melee_recordings[side]=[(0.0,0.0,0.0)]
        self.melee_motion_recordings[side]=[]
        self._capture_melee_motion_sample(side,0.0,True)
        self.melee_audio_motion_accum[side]=0.0
        self.melee_audio_cooldown[side]=0.0
        self.melee_audio_last_target[side]=None
        self._rebuild_melee_trail(side)

    def _start_recorded_melee_playback(self, recording, source='recording'):
        rec=self._effective_melee_recording(recording)
        if not rec or len(rec['samples'])<2: return False
        side=rec['side']; samples=rec['samples']; self.melee_hold[side]=False
        first=samples[0]
        self._update_melee_pose(side,first['target']); self.melee_arms[side]['fist'].setHpr(first['hpr'])
        speed=max(MOTION_FORGE_MIN_SPEED,min(MOTION_FORGE_MAX_SPEED,float(rec.get('playback_speed',MELEE_REPLAY_SPEED))))
        self.melee_playback[side]={
            'mode':'recorded','samples':samples,'elapsed':0.0,'speed':speed,
            'duration':max(.001,float(rec['duration'])),'charge':max(0.0,min(1.0,float(rec['duration'])/MELEE_FULL_CHARGE_TIME)),
            'travel':float(rec.get('travel',0.0)),'weapon':('sword' if side=='right' else 'fist'),
            'source':str(source),'hit_count':0,'last_source_time':0.0,'name':str(rec.get('name',MOTION_FORGE_DEFAULT_NAME)),
        }
        self.melee_fist_world_prev[side]=None
        if side=='right': self.sword_base_prev=None; self.sword_tip_prev=None
        self._play_weapon_sfx(side+'_arm_move',1.0,1.05)
        if side=='right': self._play_weapon_sfx('sword_move',1.0,1.08)
        return True

    def _number_key(self, slot):
        slot=int(slot)
        if self.combo_composer_visible:
            self._combo_append_move(slot); return
        if self.motion_forge_visible:
            self._forge_select_slot(slot); return
        if self.combat_mode!='melee':
            if slot==1: self.set_weapon_mode('AUTO')
            elif slot==2: self.set_weapon_mode('SHOTGUN')
            elif slot==3: self.set_weapon_mode('SNIPER')
            return
        if self.melee_pending_slot_save and self.melee_last_recording.get('right'):
            self.melee_slots[slot]=self._copy_melee_recording(self.melee_last_recording['right'])
            self.melee_slots[slot]['name']=f'SWORD MOTION {slot:02d}'
            self.melee_pending_slot_save=False
            saved=self._save_melee_slots()
            self.last_hit=f'SWORD RECORDING SAVED TO SLOT {slot}' + ('' if saved else ' (SESSION ONLY)')
            self._status(); return
        rec=self.melee_slots.get(slot)
        if rec:
            self._start_recorded_melee_playback(rec,source=f'slot_{slot}')
            speed=float(rec.get('playback_speed',MELEE_REPLAY_SPEED)); self.last_hit=f'SWORD SLOT {slot} — {speed:.2f}x REPLAY'; self._status()
        else:
            self.last_hit=f'SWORD SLOT {slot} EMPTY — RECORD RMB THEN PRESS {slot}'; self._status()

    @staticmethod
    def _melee_angle_lerp(a, b, t):
        d=((float(b)-float(a)+180.0)%360.0)-180.0
        return float(a)+d*max(0.0,min(1.0,float(t)))

    def _preserve_melee_release_orientation(self, side, pb, t):
        """Blend out of the exact held wrist orientation instead of snapping at release."""
        release=pb.get('release_hpr')
        arm=self.melee_arms.get(side)
        if release is None or not arm or pb.get('index',0)!=0: return
        hand=arm['fist']; current=_v3(hand.getHpr())
        blend=max(0.0,min(1.0,float(t)/max(1e-6,MELEE_RELEASE_ORIENTATION_BLEND)))
        hand.setHpr(
            self._melee_angle_lerp(release.x,current.x,blend),
            self._melee_angle_lerp(release.y,current.y,blend),
            self._melee_angle_lerp(release.z,current.z,blend))

    def _apply_sword_flurry_rotation(self, side, pb, strike_progress):
        """Drive a fast wrist moulinet while the arm travels through the outward strike.

        The arm path remains the positional authority.  These local hand rotations make the
        blade tip orbit around the wrist, so the visible/collision sword really performs the
        flurry rather than drawing a decorative trail.  The envelope reaches zero before the
        recovery segment so the wrist settles cleanly into the forward commit.
        """
        if side!='right' or not pb.get('flurry'): return 0.0
        p=max(0.0,min(1.0,float(strike_progress)))
        local=min(1.0,p/max(1e-6,SWORD_FLURRY_PORTION))
        if local>=1.0: return 0.0
        envelope=math.sin(math.pi*local)
        turns=float(pb.get('flurry_turns',SWORD_FLURRY_TURNS))
        angle=math.tau*turns*local
        hand=self.melee_arms['right']['fist']
        hand.setH(hand.getH()+math.sin(angle)*SWORD_FLURRY_HEADING_DEG*envelope)
        hand.setP(hand.getP()+math.cos(angle)*SWORD_FLURRY_PITCH_DEG*envelope)
        hand.setR(hand.getR()+SWORD_FLURRY_ROLL_DEG*turns*local*envelope)
        return envelope

    def _seed_sword_flurry_trail(self, pb):
        """Sample the real blade tip through the attack's flurry phase for visual QA."""
        if self.sword_tip is None or self.melee_root is None: return
        samples=[]; attack_segments=max(1,int(pb.get('hit_end',0))+1)
        phases=(.05,.12,.20,.28,.36,.44,.52,.60,.68,.75)
        for phase in phases:
            segf=phase*attack_segments; idx=min(attack_segments-1,int(segf)); t=max(0.0,min(1.0,segf-idx))
            a=pb['targets'][idx]; b=pb['targets'][min(idx+1,len(pb['targets'])-1)]
            tt=t*t*(3.0-2.0*t); target=a+(b-a)*tt
            self._update_melee_pose('right',target)
            temp={'index':idx,'release_hpr':pb.get('release_hpr')}
            self._preserve_melee_release_orientation('right',temp,t)
            self._apply_sword_flurry_rotation('right',pb,phase)
            tip=_v3(self.sword_tip.getPos(self.render)); local=_v3(self.melee_root.getRelativePoint(self.render,tip))
            samples.append(local)
        now=self.melee_time
        self.sword_tip_history=[(now-(len(samples)-i)*.008,p) for i,p in enumerate(samples)]
        self._rebuild_sword_trail()

    @staticmethod
    def _sample_recorded_motion(samples, source_time):
        if not samples: return None
        t=max(0.0,float(source_time))
        if t<=samples[0]['t']: return (_v3(samples[0]['target']),_v3(samples[0]['hpr']),0)
        if t>=samples[-1]['t']: return (_v3(samples[-1]['target']),_v3(samples[-1]['hpr']),len(samples)-1)
        lo=0; hi=len(samples)-1
        while lo+1<hi:
            mid=(lo+hi)//2
            if samples[mid]['t']<=t: lo=mid
            else: hi=mid
        a=samples[lo]; b=samples[hi]; span=max(1e-6,b['t']-a['t']); u=max(0.0,min(1.0,(t-a['t'])/span)); e=u*u*(3.0-2.0*u)
        target=_v3(a['target'])+(_v3(b['target'])-_v3(a['target']))*e
        ah=_v3(a['hpr']); bh=_v3(b['hpr'])
        hpr=Vec3(
            ASCIIMatterLab._melee_angle_lerp(ah.x,bh.x,e),
            ASCIIMatterLab._melee_angle_lerp(ah.y,bh.y,e),
            ASCIIMatterLab._melee_angle_lerp(ah.z,bh.z,e))
        return target,hpr,lo

    def _finish_melee_charge(self, side):
        if self.combat_mode!='melee' or not self.melee_hold.get(side): return
        held=float(self.melee_hold_time[side]); cursor_record=list(self.melee_recordings.get(side) or ())
        path=[(float(q[1]),float(q[2])) for q in cursor_record] if cursor_record else list(self.melee_paths.get(side,()))
        travel=sum(math.hypot(b[0]-a[0],b[1]-a[1]) for a,b in zip(path[:-1],path[1:]))
        charge=max(0.0,min(1.0,held/MELEE_FULL_CHARGE_TIME))
        # Capture the literal final held transform before HOLD authority is released.
        release_target=_v3(self._melee_target_from_cursor(side)); self._update_melee_pose(side,release_target)
        self._capture_melee_motion_sample(side,held,True)
        self.melee_hold[side]=False

        motion=list(self.melee_motion_recordings.get(side) or ())
        # A tap remains the authored quick attack. Any genuine hold/drag becomes exact replay.
        if held<MELEE_TAP_TIME and travel<0.09:
            sign=-1.0 if side=='left' else 1.0
            if side=='right':
                out1=Vec3(sign*max(MELEE_OUTWARD_ARC_X,abs(release_target.x)+.10),min(.68,release_target.y+.07),release_target.z+.11)
                commit=self._melee_enemy_commit_target(side,out1,0.0)
                targets=[release_target,out1,commit,Vec3(MELEE_NEUTRAL_X,.50,-.18)]; hit_start=0; hit_end=1
            else:
                commit=self._melee_enemy_commit_target(side,release_target,0.0)
                targets=[release_target,commit,Vec3(-MELEE_NEUTRAL_X,.50,-.18)]; hit_start=0; hit_end=0
            self.melee_playback[side]={'mode':'authored','targets':targets,'index':0,'segment_t':0.0,'duration':.20,'charge':0.0,'hit':False,'hit_start':hit_start,'hit_end':hit_end,'travel':travel,'weapon':('sword' if side=='right' else 'fist')}
            return

        if len(motion)<2:
            # Defensive fallback for extremely low frame-rate capture.
            sign=-1.0 if side=='left' else 1.0
            neutral=Vec3(MELEE_NEUTRAL_X*sign,MELEE_NEUTRAL_Y,-.18)
            hpr=_v3(self.melee_arms[side]['fist'].getHpr())
            motion=[{'t':0.0,'target':neutral,'hpr':hpr},{'t':max(.05,held),'target':release_target,'hpr':hpr}]
        # Normalize sample times to zero so saved slots are portable and deterministic.
        base=float(motion[0]['t']); samples=[]
        for q in motion:
            samples.append({'t':max(0.0,float(q['t'])-base),'target':_v3(q['target']),'hpr':_v3(q['hpr'])})
        duration=max(.001,float(samples[-1]['t']))
        recording={'side':side,'duration':duration,'travel':travel,'samples':samples,'name':MOTION_FORGE_DEFAULT_NAME,'playback_speed':MELEE_REPLAY_SPEED,'trim_start':0.0,'trim_end':0.0,'mirrored':False}
        self.melee_last_recording[side]=self._copy_melee_recording(recording)
        if side=='right': self.melee_pending_slot_save=True
        self._start_recorded_melee_playback(recording,source='fresh')
        self.last_hit=(f'RIGHT SWORD FULL RECORDING — {len(samples)} SAMPLES @150%' if side=='right' else f'LEFT FIST FULL RECORDING — {len(samples)} SAMPLES @150%')

    def _record_melee_delta(self, dx, dy):
        active=[s for s in ('left','right') if self.melee_hold.get(s)]
        if not active: return False
        for side in active:
            cur=self.melee_cursor[side]
            cur[0]=max(-1.0,min(1.0,cur[0] + dx*.0075))
            cur[1]=max(-1.0,min(1.0,cur[1] + dy*.0075))
            pts=self.melee_paths[side]
            if not pts or math.hypot(cur[0]-pts[-1][0],cur[1]-pts[-1][1])>=MELEE_GESTURE_SAMPLE_DIST:
                pts.append((cur[0],cur[1]))
                # Full-path authority: never discard the beginning of a held gesture.  The
                # 4096-point safety ceiling is many minutes of normal input and, if reached,
                # preserves both endpoints while compacting only redundant adjacent samples.
                if len(pts)>MELEE_MAX_PATH_POINTS:
                    pts[:]=[pts[0]]+pts[1:-1:2]+[pts[-1]]
                self.melee_recordings[side].append((float(self.melee_hold_time[side]),float(cur[0]),float(cur[1])))
                self._rebuild_melee_trail(side)
        return True

    @staticmethod
    def _closest_points_segments(p1, q1, p2, q2):
        """Return (distance, point_on_first, point_on_second) for two finite 3D segments."""
        p1=_v3(p1); q1=_v3(q1); p2=_v3(p2); q2=_v3(q2)
        d1=q1-p1; d2=q2-p2; r=p1-p2
        a=d1.dot(d1); e=d2.dot(d2); eps=1e-10
        if a<=eps and e<=eps: return (r.length(),p1,p2)
        if a<=eps:
            s0=0.0; t=max(0.0,min(1.0,d2.dot(p1-p2)/max(e,eps)))
        else:
            c=d1.dot(r)
            if e<=eps:
                t=0.0; s0=max(0.0,min(1.0,-c/a))
            else:
                b=d1.dot(d2); f=d2.dot(r); denom=a*e-b*b
                s0=max(0.0,min(1.0,(b*f-c*e)/denom)) if abs(denom)>eps else 0.0
                t=(b*s0+f)/e
                if t<0.0:
                    t=0.0; s0=max(0.0,min(1.0,-c/a))
                elif t>1.0:
                    t=1.0; s0=max(0.0,min(1.0,(b-c)/a))
        c1=p1+d1*s0; c2=p2+d2*t
        return ((c1-c2).length(),c1,c2)

    def _sword_blade_world(self):
        if self.sword_base is None or self.sword_tip is None:
            return None
        return (_v3(self.sword_base.getPos(self.render)), _v3(self.sword_tip.getPos(self.render)))

    def _rebuild_sword_trail(self):
        old=getattr(self,'sword_trail_node',None)
        if old is not None and not old.isEmpty(): old.removeNode()
        self.sword_trail_node=None
        if self.melee_root is None or len(self.sword_tip_history)<2: return
        now=self.melee_time
        pts=[(t,p) for t,p in self.sword_tip_history if now-t<=SWORD_TRAIL_LIFE]
        self.sword_tip_history=pts[-SWORD_TRAIL_POINTS:]
        if len(self.sword_tip_history)<2: return
        ls=LineSegs('laser_sword_motion_trail'); ls.setThickness(5.0); ls.setColor(SWORD_EDGE.x,SWORD_EDGE.y,SWORD_EDGE.z,.52)
        for i,(_,p) in enumerate(self.sword_tip_history):
            if i==0: ls.moveTo(p)
            else: ls.drawTo(p)
        node=self.melee_root.attachNewNode(ls.create()); node.setLightOff(); node.setTransparency(TransparencyAttrib.MAlpha)
        node.setDepthWrite(False); node.setDepthTest(False); node.setBin('fixed',34); self.sword_trail_node=node

    def _rebuild_sword_distortion(self):
        old=self.sword_distortion_node
        if old is not None and not old.isEmpty(): old.removeNode()
        self.sword_distortion_node=None
        if self.melee_root is None or len(self.sword_distortion_history)<2: return
        now=self.melee_time
        rows=[q for q in self.sword_distortion_history if now-q[0]<=SWORD_DISTORTION_LIFE]
        self.sword_distortion_history=rows[-SWORD_DISTORTION_POINTS:]
        if len(rows)<2: return
        fmt=GeomVertexFormat.getV3c4(); vd=GeomVertexData('sword_distortion',fmt,Geom.UHDynamic)
        vw=GeomVertexWriter(vd,'vertex'); cw=GeomVertexWriter(vd,'color'); prim=GeomTriangles(Geom.UHDynamic); row=0
        palette=(Vec4(.22,.86,1.0,1),Vec4(.78,.30,1.0,1),Vec4(1.0,.82,.98,1))
        for band,offx in enumerate(SWORD_DISTORTION_OFFSETS):
            color=palette[band%len(palette)]
            for i in range(len(rows)-1):
                ta,b0,t0,sp0=rows[i]; tb,b1,t1,sp1=rows[i+1]
                age=max(0.0,now-tb); fade=max(0.0,1.0-age/SWORD_DISTORTION_LIFE)
                speed=max(sp0,sp1); strength=max(0.0,min(1.0,(speed-SWORD_DISTORTION_MIN_SPEED)/(SWORD_DISTORTION_MAX_SPEED-SWORD_DISTORTION_MIN_SPEED)))
                alpha=SWORD_DISTORTION_ALPHA*fade*strength*(.72 if band!=1 else 1.0)
                if alpha<=.008: continue
                ofs=Vec3(offx,0,0)
                for pt in (b0+ofs,t0+ofs,t1+ofs,b1+ofs): vw.addData3(pt); cw.addData4(color.x,color.y,color.z,alpha)
                prim.addVertices(row,row+1,row+2); prim.addVertices(row,row+2,row+3); row+=4
        if row==0: return
        geom=Geom(vd); geom.addPrimitive(prim); node=GeomNode('laser_sword_velocity_distortion'); node.addGeom(geom)
        np=self.melee_root.attachNewNode(node); np.setLightOff(); np.setTransparency(TransparencyAttrib.MAlpha); np.setDepthWrite(False); np.setDepthTest(False); np.setTwoSided(True); np.setBin('fixed',35)
        self.sword_distortion_node=np

    def _spawn_sword_sparks(self, world_point, incoming, intensity=1.0):
        p=_v3(world_point); d=_v3(incoming)
        if d.lengthSquared()<1e-8: d=Vec3(0,1,0)
        d.normalize()
        ls=LineSegs('laser_sword_cut_sparks'); ls.setThickness(2.3); ls.setColor(1.0,.78,.96,.92)
        spark_count=max(6,min(20,int(round(8+7*max(0.0,min(1.8,float(intensity)))))))
        for i in range(spark_count):
            v=Vec3(self.rng.uniform(-1,1),self.rng.uniform(-1,1),self.rng.uniform(-.2,1.0)) + d*.35
            if v.lengthSquared()<1e-8: v=Vec3(0,0,1)
            v.normalize(); v*=self.rng.uniform(.08,.22)*(0.82+0.28*max(0.0,min(1.8,float(intensity))))
            ls.moveTo(p); ls.drawTo(p+v)
        node=self.render.attachNewNode(ls.create()); node.setLightOff(); node.setTransparency(TransparencyAttrib.MAlpha); node.setDepthWrite(False); node.setBin('fixed',40)
        self.sword_sparks.append([node,SWORD_SPARK_LIFE])

    def _update_sword_fx(self, dt):
        if self.sword_root is None: return
        self.sword_pulse += max(0.0,float(dt))
        pulse=.80+.20*(.5+.5*math.sin(self.sword_pulse*18.0))
        if self.sword_blade_glow is not None and not self.sword_blade_glow.isEmpty(): self.sword_blade_glow.setColorScale(1,1,1,pulse)
        blade=self._sword_blade_world(); pb=self.melee_playback.get('right')
        sword_active=(self.melee_hold.get('right',False) or pb is not None)
        if self.combat_mode=='melee' and blade is not None and sword_active:
            base,tip=blade; localtip=_v3(self.melee_root.getRelativePoint(self.render,tip)); localbase=_v3(self.melee_root.getRelativePoint(self.render,base))
            if not self.sword_tip_history or (localtip-self.sword_tip_history[-1][1]).length()>.018:
                self.sword_tip_history.append((self.melee_time,localtip)); self.sword_tip_history=self.sword_tip_history[-SWORD_TRAIL_POINTS:]
            self._rebuild_sword_trail()
            # Distortion is playback-only: recording/holding stays readable, while the actual
            # accelerated attack produces a swept translucent field proportional to blade speed.
            if pb is not None:
                prev=self.sword_last_distortion_tip
                speed=(localtip-prev).length()/max(1e-5,float(dt)) if prev is not None else 0.0
                self.sword_last_distortion_tip=_v3(localtip)
                if speed>=SWORD_DISTORTION_MIN_SPEED:
                    self.sword_distortion_history.append((self.melee_time,localbase,localtip,speed))
                    self.sword_distortion_history=self.sword_distortion_history[-SWORD_DISTORTION_POINTS:]
                self._rebuild_sword_distortion()
            else:
                self.sword_last_distortion_tip=None; self.sword_distortion_history=[]; self._rebuild_sword_distortion()
        else:
            self.sword_last_distortion_tip=None
            if self.sword_tip_history: self.sword_tip_history=[]; self._rebuild_sword_trail()
            if self.sword_distortion_history: self.sword_distortion_history=[]; self._rebuild_sword_distortion()
        kept=[]
        for node,life in self.sword_sparks:
            life-=dt
            if life<=0 or node.isEmpty():
                if not node.isEmpty(): node.removeNode()
                continue
            node.setColorScale(1,1,1,max(0.0,life/SWORD_SPARK_LIFE)); kept.append([node,life])
        self.sword_sparks=kept

    def _joint_descendants(self, root_name):
        out={str(root_name)}; changed=True
        while changed:
            changed=False
            for name,parent in self.rig_parent_names.items():
                if name not in out and parent in out:
                    out.add(name); changed=True
        return out

    def _joint_is_detached(self, name):
        return str(name) in self.detached_joint_names

    def _bone_is_severable(self, name, spec):
        name=str(name)
        if name in self.severed_bone_names: return False
        if name in ('neck_head','left_clavicle','right_clavicle','left_humerus','right_humerus','left_radius','right_radius',
                    'left_palm','right_palm','left_femur','right_femur','left_tibia','right_tibia','left_foot_arch','right_foot_arch'):
            return True
        return any(tok in name for tok in ('thumb_','index_','middle_','ring_','pinky_'))

    def _sword_bone_cut_test(self, base0, tip0, base1, tip1):
        best=None
        segments=((base0,tip0),(base1,tip1),(tip0,tip1))
        for name,spec in self.skeleton_bone_specs.items():
            if not self._bone_is_severable(name,spec): continue
            a_name=spec.get('a'); b_name=spec.get('b')
            if a_name not in self.rig_joints or b_name not in self.rig_joints: continue
            if self._joint_is_detached(a_name) or self._joint_is_detached(b_name): continue
            a=_v3(self.rig_joints[a_name].getPos(self.render)); b=_v3(self.rig_joints[b_name].getPos(self.render))
            threshold=float(spec.get('radius',.006))+SWORD_CUT_RADIUS
            for s0,s1 in segments:
                dist,blade_p,bone_p=self._closest_points_segments(s0,s1,a,b)
                if dist<=threshold and (best is None or dist<best[0]): best=(dist,name,bone_p,blade_p,spec)
        return best

    def _sword_ascii_hit_test(self, base0, tip0, base1, tip1, radius=SWORD_CUT_RADIUS):
        best=None
        segments=((base0,tip0),(base1,tip1),(tip0,tip1),(base0,base1))
        for bind,(local_center,bradius) in self.binding_bounds.items():
            parent=self._glyph_parent(bind); center=_v3(self.render.getRelativePoint(parent,local_center))
            if min(self._point_segment_distance(center,a,b) for a,b in segments)>bradius+radius: continue
            for i in self.binding_members.get(bind,()):
                if not self.live[i]: continue
                p=self._current_glyph_world_pos(i)
                d=min(self._point_segment_distance(p,a,b) for a,b in segments)
                if d<=radius and (best is None or d<best[0]): best=(d,p,i)
        return (best[1],best[2]) if best else None

    def _sample_detached_limb(self, limb, force=False):
        limb.sample_clock += MEMORY_SAMPLE_DT if force else 0.0
        if force or limb.sample_clock>=MEMORY_SAMPLE_DT:
            p=_v3(limb.root.getPos(self.render)); hpr=_v3(limb.root.getHpr(self.render))
            limb.samples.append((limb.age,(p.x,p.y,p.z),(hpr.x,hpr.y,hpr.z))); limb.sample_clock=0.0

    @staticmethod
    def _detached_limb_memory_pose(limb, age):
        samples=limb.samples
        if not samples: return (_v3(limb.root.getPos()),_v3(limb.root.getHpr()))
        if age<=samples[0][0]: return (Vec3(*samples[0][1]),Vec3(*samples[0][2]))
        if age>=samples[-1][0]: return (Vec3(*samples[-1][1]),Vec3(*samples[-1][2]))
        lo,hi=0,len(samples)-1
        while lo+1<hi:
            mid=(lo+hi)//2
            if samples[mid][0]<=age: lo=mid
            else: hi=mid
        ta,pa,ra=samples[lo]; tb,pb,rb=samples[hi]; alpha=0.0 if tb<=ta else (age-ta)/(tb-ta)
        return (Vec3(*pa)+(Vec3(*pb)-Vec3(*pa))*alpha, Vec3(*ra)+(Vec3(*rb)-Vec3(*ra))*alpha)

    def _reattach_detached_limb(self, limb):
        if limb.root is None or limb.root.isEmpty(): return
        limb.root.reparentTo(limb.parent); limb.root.setTransform(limb.local_transform)
        if limb.cut_node is not None and not limb.cut_node.isEmpty():
            if self.internal_detail_visible: limb.cut_node.show()
        self.severed_bone_names.discard(limb.cut_bone)
        self.detached_joint_names.difference_update(limb.descendants)

    def _sever_bone(self, bone_name, cut_point, incoming, charge, dynamics=None):
        spec=self.skeleton_bone_specs.get(str(bone_name))
        if not spec or not self._bone_is_severable(bone_name,spec): return False
        parent_name=str(spec['a']); root_name=str(spec['b'])
        if root_name not in self.rig_joints or parent_name not in self.rig_joints: return False
        descendants=self._joint_descendants(root_name)
        if self._joint_is_detached(parent_name) or self._joint_is_detached(root_name) or any(n in self.detached_joint_names for n in descendants): return False
        root=self.rig_joints[root_name]; parent=self.rig_joints[parent_name]
        local_transform=root.getTransform(parent)
        # Compute one conservative floor offset from the actual connected ASCII at the cut moment.
        member_indices=[i for i,b in enumerate(self.body_bindings) if b in descendants and self.live[i]]
        rz=float(root.getZ(self.render)); minz=min((self._current_glyph_world_pos(i).z for i in member_indices),default=rz-.10)
        floor_offset=max(.045,rz-minz+.025)
        d=_v3(incoming)
        if d.lengthSquared()<1e-8: d=Vec3(0,1,0)
        dyn=max(.60,min(1.70,float((dynamics or {}).get('impact',1.0))))
        d.normalize(); vel=(d*(.95+1.25*charge)+Vec3(0,0,.55+.48*charge))*dyn
        ang=Vec3(self.rng.uniform(-145,145),self.rng.uniform(-110,110),self.rng.uniform(-180,180))*(.55+.65*charge)*(.82+.24*dyn)
        cut_node=self.skeleton_bone_nodes.get(str(bone_name))
        if cut_node is not None and not cut_node.isEmpty(): cut_node.hide()
        root.wrtReparentTo(self.render)
        limb=DetachedLimb(root_name,root,parent_name,parent,local_transform,bone_name,cut_node,vel,ang,floor_offset,descendants)
        self.detached_limbs.append(limb); self.detached_joint_names.update(descendants); self.severed_bone_names.add(str(bone_name))
        self._sample_detached_limb(limb,True); self.sword_cut_count+=1; self.sword_last_cut_bone=str(bone_name)
        self.last_hit=f'LASER CUT {str(bone_name).upper()} — {len(member_indices)} ASCII CONNECTED'
        return True

    def _update_detached_limbs(self, dt):
        if not self.detached_limbs or self.rewinding: return
        dt=max(0.0,min(.05,float(dt)))
        for limb in self.detached_limbs:
            limb.age+=dt; limb.sample_clock+=dt
            if not limb.settled:
                limb.velocity.z-=SWORD_GRAVITY*dt
                p=_v3(limb.root.getPos(self.render))+limb.velocity*dt
                floor=limb.floor_offset
                if p.z<floor:
                    p.z=floor
                    if abs(limb.velocity.z)>.45: limb.velocity.z=abs(limb.velocity.z)*SWORD_LIMB_BOUNCE
                    else: limb.velocity.z=0.0
                    limb.velocity.x*=.74; limb.velocity.y*=.74
                limb.root.setPos(self.render,p)
                hpr=_v3(limb.root.getHpr(self.render))+limb.angular_velocity*dt; limb.root.setHpr(self.render,hpr)
                limb.velocity*=max(0.0,1.0-SWORD_LIMB_DRAG*dt); limb.angular_velocity*=max(0.0,1.0-SWORD_ANGULAR_DRAG*dt)
                if limb.velocity.length()<.045 and limb.angular_velocity.length()<3.0 and abs(p.z-floor)<.005: limb.settled=True
            self._sample_detached_limb(limb)

    def _rewind_detached_limbs(self, amount):
        kept=[]
        for limb in self.detached_limbs:
            limb.age=max(0.0,limb.age-amount)
            if limb.age<=0.0:
                self._reattach_detached_limb(limb); continue
            pos,hpr=self._detached_limb_memory_pose(limb,limb.age); limb.root.setPos(self.render,pos); limb.root.setHpr(self.render,hpr); kept.append(limb)
        self.detached_limbs=kept

    def _sword_motion_dynamics(self, base0, tip0, base1, tip1, dt=1.0/60.0, contact_point=None):
        """Return bounded sword-impact dynamics from the *real* blade sweep.

        Speed comes from the moving blade midpoint/tip. Alignment is measured against
        the blade's current local axes: X is the cutting-edge direction, Y is blade length,
        and Z is the broad/flat normal. This lets a fast edge-leading cut, an axial thrust,
        and a flat-side slap produce different physical results without changing the
        player-authored animation.
        """
        b0,t0,b1,t1=map(_v3,(base0,tip0,base1,tip1)); dt=max(1e-4,float(dt))
        mid0=(b0+t0)*.5; mid1=(b1+t1)*.5
        tip_v=(t1-t0)/dt; mid_v=(mid1-mid0)/dt
        motion=tip_v*.72+mid_v*.28
        speed=float(motion.length())
        if speed<1e-6:
            motion=_v3(t1-b1); speed=0.0
        vdir=_v3(motion)
        if vdir.lengthSquared()<1e-10: vdir=Vec3(0,1,0)
        else: vdir.normalize()
        blade_dir=_v3(t1-b1)
        blade_len=max(1e-6,float(blade_dir.length())); blade_dir/=blade_len
        # sword_root local X follows the cutting edge; local Z is the broad-face normal.
        if self.sword_root is not None and not self.sword_root.isEmpty():
            edge_axis=_v3(self.render.getRelativeVector(self.sword_root,Vec3(1,0,0)))
            flat_axis=_v3(self.render.getRelativeVector(self.sword_root,Vec3(0,0,1)))
        else:
            edge_axis=Vec3(1,0,0); flat_axis=Vec3(0,0,1)
        if edge_axis.lengthSquared()>1e-10: edge_axis.normalize()
        if flat_axis.lengthSquared()>1e-10: flat_axis.normalize()
        edge=abs(float(vdir.dot(edge_axis))); thrust=abs(float(vdir.dot(blade_dir))); flat=abs(float(vdir.dot(flat_axis)))
        total=max(1e-6,edge+thrust+flat)
        edge_n=edge/total; thrust_n=thrust/total; flat_n=flat/total
        point=_v3(contact_point) if contact_point is not None else _v3(t1)
        lever=max(0.0,min(1.0,float((point-b1).dot(blade_dir))/blade_len))
        # Smooth speed authority: very slow drags remain damaging but cannot match a fast authored cut.
        sn=max(0.0,min(1.0,(speed-SWORD_DYN_MIN_SPEED)/max(1e-6,SWORD_DYN_REFERENCE_SPEED-SWORD_DYN_MIN_SPEED)))
        speed_factor=0.42+1.28*(sn**0.68)
        if speed>SWORD_DYN_REFERENCE_SPEED:
            speed_factor+=0.24*max(0.0,min(1.0,(speed-SWORD_DYN_REFERENCE_SPEED)/max(1e-6,SWORD_DYN_MAX_SPEED-SWORD_DYN_REFERENCE_SPEED)))
        lever_factor=SWORD_DYN_LEVER_BASE+SWORD_DYN_LEVER_GAIN*lever
        impact=max(SWORD_DYN_MIN_IMPACT,min(SWORD_DYN_MAX_IMPACT,speed_factor*lever_factor))
        if thrust_n>=SWORD_DYN_THRUST_THRESHOLD and thrust_n>edge_n:
            kind='THRUST'; alignment=.35+.90*thrust_n; cut=impact*alignment
        elif flat_n>edge_n*1.08 and flat_n>thrust_n:
            kind='FLAT'; alignment=.20+.38*edge_n; cut=impact*SWORD_DYN_FLAT_CUT_SCALE*(.72+.28*edge_n)
        else:
            kind='CLEAN CUT' if edge_n>=SWORD_DYN_CLEAN_EDGE_THRESHOLD else 'CUT'
            alignment=.28+1.02*edge_n; cut=impact*alignment
        cut=max(SWORD_DYN_MIN_CUT,min(SWORD_DYN_MAX_CUT,cut))
        out={'type':kind,'speed':speed,'speed_factor':speed_factor,'edge':edge_n,'thrust':thrust_n,'flat':flat_n,
             'lever':lever,'impact':impact,'cut':cut,'alignment':alignment}
        self.sword_last_dynamics=out; self.sword_dynamics_peak=max(self.sword_dynamics_peak,impact)
        return out

    def _apply_sword_hit(self, base0, tip0, base1, tip1, charge, travel, dt=1.0/60.0):
        ascii_hit=self._sword_ascii_hit_test(base0,tip0,base1,tip1,SWORD_CUT_RADIUS+.014*charge)
        bone_hit=self._sword_bone_cut_test(base0,tip0,base1,tip1)
        if ascii_hit is None and bone_hit is None: return False
        incoming=_v3(tip1-tip0)
        if incoming.lengthSquared()<1e-8: incoming=_v3(tip1-base1)
        if incoming.lengthSquared()<1e-8: incoming=Vec3(0,1,0)
        incoming.normalize()
        if ascii_hit is not None:
            point,index=ascii_hit
        else:
            point=_v3(bone_hit[2]); index=min(range(len(self.surface)),key=lambda i:(self._current_glyph_world_pos(i)-point).lengthSquared() if self.live[i] else 1e9)
        dyn=self._sword_motion_dynamics(base0,tip0,base1,tip1,dt,point)
        base_count=SWORD_ASCII_DAMAGE+int(round((SWORD_ASCII_DAMAGE_CHARGED-SWORD_ASCII_DAMAGE)*charge))
        count=max(5,min(SWORD_DYN_DAMAGE_MAX,int(round(base_count*(.58+.58*dyn['cut'])))))
        wound_radius=(.18+.055*charge)*(.90+.16*dyn['cut'])
        impulse=(.62+.70*charge)*SWORD_IMPACT_MULTIPLIER*dyn['impact']
        self.damage_at(point,wound_radius,count,hit_index=index,wound_outer=MELEE_MID_RED,wound_core=MELEE_CORE_RED,
                       impulse_scale=impulse,incoming_world=incoming,mode='SWORD')
        self._apply_impact_reaction(index,incoming,'SWORD',force_scale=dyn['impact'])
        self._play_weapon_sfx('sword_impact', min(1.0,.72+.20*dyn['impact']), .88+.12*min(1.6,dyn['speed_factor']))
        self._spawn_sword_sparks(point,incoming,dyn['impact'])
        severed=False
        sever_ready=(charge>=SWORD_MIN_SEVER_CHARGE or travel>=SWORD_MIN_SEVER_TRAVEL)
        if bone_hit is not None and sever_ready and dyn['cut']>=SWORD_DYN_SEVER_THRESHOLD:
            severed=self._sever_bone(bone_hit[1],bone_hit[2],incoming,charge,dynamics=dyn)
        self.npc_defense_timer=max(self.npc_defense_timer,.38+.15*min(1.5,dyn['impact']))
        if not severed: self.last_hit=f"{dyn['type']} {dyn['speed']:.1f}M/S — {count} GLYPHS"
        return True

    def _melee_hit_test(self, a_world, b_world, radius):
        # Swept-sphere contact against the ASCII surface. Rank hits by the actual
        # entry time of the fist volume, not by closest-point distance. This is
        # important for hollow shells such as the head: the fist should contact
        # the front surface before a torso glyph that happens to be closer to the
        # final fist center.
        a=_v3(a_world); b=_v3(b_world); ab=b-a; length=ab.length()
        if length < 1e-8: return None
        direction=ab/length
        best=None
        for bind,(local_center,bradius) in self.binding_bounds.items():
            parent=self._glyph_parent(bind); center=_v3(self.render.getRelativePoint(parent,local_center))
            if self._point_segment_distance(center,a,b)>bradius+radius: continue
            for i in self.binding_members.get(bind,()):
                if not self.live[i]: continue
                p=self._current_glyph_world_pos(i); rel=p-a
                along=rel.dot(direction)
                perp2=max(0.0,rel.lengthSquared()-along*along)
                r2=radius*radius
                if perp2>r2: continue
                reach=math.sqrt(max(0.0,r2-perp2))
                entry=along-reach; leave=along+reach
                if leave<0.0 or entry>length: continue
                t=max(0.0,entry/length)
                pd=math.sqrt(perp2)
                if best is None or t<best[0] or (abs(t-best[0])<1e-6 and pd<best[1]):
                    best=(t,pd,p,i)
        return (best[2],best[3]) if best else None

    def _apply_melee_hit(self, side, a_world, b_world, charge):
        hit=self._melee_hit_test(a_world,b_world,MELEE_PUNCH_RADIUS+.035*charge)
        if hit is None: return False
        point,index=hit
        region=self._impact_region(index)
        if ARGS.melee_smoke:
            print(f'ANATOMIC_MELEE_HIT side={side} region={region} bind={self.body_bindings[index]} index={index} point=({point.x:.3f},{point.y:.3f},{point.z:.3f}) charge={charge:.3f}')
        if region=='head': self.melee_head_hits += 1
        else: self.melee_body_hits += 1
        incoming=_v3(b_world-a_world)
        if incoming.lengthSquared()<1e-8: incoming=Vec3(0,1,0)
        incoming.normalize()
        count=MELEE_DIRECT_DAMAGE+int(round((MELEE_CHARGED_DAMAGE-MELEE_DIRECT_DAMAGE)*charge))
        radius=.16+.055*charge
        # Punch wounds intentionally start purple at the fringe and become red at the core.
        self.damage_at(point,radius,count,hit_index=index,wound_outer=MELEE_OUTER_PURPLE,wound_core=MELEE_CORE_RED,
                       impulse_scale=.48+.72*charge,incoming_world=incoming,mode='MELEE')
        self._play_weapon_sfx('fist_impact', .92+.08*charge, 1.03 if side=='left' else .97)
        self._apply_impact_reaction(index,incoming,'MELEE_CHARGED' if charge>.55 else 'MELEE')
        self.npc_defense_timer=max(self.npc_defense_timer,NPC_DEFENSE_TIME + .30*charge)
        self.npc_defense_side=-1.0 if side=='left' else 1.0
        self.npc_last_damage_mode='MELEE'
        self.last_hit=f'{side.upper()} FIST IMPACT {count} GLYPHS'
        return True

    def _update_melee(self, dt):
        self.melee_time += dt
        if self.combat_mode!='melee':
            self._update_sword_fx(dt)
            return
        self.melee_raise_blend=min(1.0,self.melee_raise_blend+dt*5.8)
        eased=self.melee_raise_blend*self.melee_raise_blend*(3.0-2.0*self.melee_raise_blend)
        if self.melee_root is not None:
            horizontal_speed=math.hypot(self.player_vel.x,self.player_vel.y)
            move_ratio=min(1.20,horizontal_speed/max(0.001,WALK_SPEED)) if self.on_ground else 0.0
            walk_sway=math.sin(self.locomotion_phase)*LOCOMOTION_SWAY_SCALE*.72*move_ratio
            walk_bob=math.sin(self.locomotion_phase*2.0)*LOCOMOTION_BOB_SCALE*.72*move_ratio
            self.melee_root.setPos(walk_sway,0.0,-.38*(1.0-eased)+walk_bob)
        self._update_melee_body_solver(dt)
        for side in ('left','right'):
            if self.melee_hold[side]:
                self.melee_hold_time[side]=min(MELEE_FULL_CHARGE_TIME*1.3,self.melee_hold_time[side]+dt)
                target=self._melee_target_from_cursor(side)
                wrist=self._update_melee_pose(side,target)
                self._capture_melee_motion_sample(side,float(self.melee_hold_time[side]))
                self._tick_melee_motion_audio(side,target,dt,sword=(side=='right'))
                if side=='right':
                    blade=self._sword_blade_world()
                    if blade is not None: self.sword_base_prev,self.sword_tip_prev=blade
                self.melee_fist_world_prev[side]=_v3(self.melee_arms[side].get('strike_tip',self.melee_arms[side]['fist']).getPos(self.render)) if wrist is not None else None
                rec=self.melee_recordings[side]; stamp=float(self.melee_hold_time[side]); x,z=self.melee_cursor[side]
                if not rec or stamp-rec[-1][0]>=1.0/60.0:
                    rec.append((stamp,float(x),float(z)))
                continue
            pb=self.melee_playback.get(side)
            if pb:
                if pb.get('mode')=='recorded':
                    pb['elapsed']+=dt
                    source_time=min(pb['duration'],pb['elapsed']*pb.get('speed',MELEE_REPLAY_SPEED))
                    sample=self._sample_recorded_motion(pb['samples'],source_time)
                    if sample is None:
                        self.melee_playback[side]=None; continue
                    target,hpr,_sample_index=sample
                    wrist=self._update_melee_pose(side,target); self.melee_arms[side]['fist'].setHpr(hpr)
                    self._tick_melee_motion_audio(side,target,dt,sword=(side=='right'))
                    if wrist is not None:
                        if side=='right':
                            blade=self._sword_blade_world()
                            if blade is not None:
                                base,tip=blade
                                if self.sword_base_prev is not None and self.sword_tip_prev is not None:
                                    # Full recorded path is collision authority.  Distinct crossings can
                                    # strike again, but a short source-time gate prevents one continuous
                                    # overlap from becoming dozens of hits.
                                    combo_hit=self._combo_window_at(pb,source_time,pb.get('last_sample_time')) if pb.get('combo_windows') else None
                                    if combo_hit is not None:
                                        wi,w=combo_hit; last=pb['combo_last_hit_times'].get(wi,-9.0); count=pb['combo_hit_counts'].get(wi,0)
                                        if source_time-last>=.16 and count<5:
                                            if self._apply_sword_hit(self.sword_base_prev,self.sword_tip_prev,base,tip,float(w['charge']),float(w['travel']),dt):
                                                pb['combo_hit_counts'][wi]=count+1; pb['combo_last_hit_times'][wi]=source_time
                                    elif not pb.get('combo_windows') and source_time-pb.get('last_source_time',-9.0)>=.16 and pb.get('hit_count',0)<5:
                                        if self._apply_sword_hit(self.sword_base_prev,self.sword_tip_prev,base,tip,pb['charge'],pb.get('travel',0.0),dt):
                                            pb['hit_count']=pb.get('hit_count',0)+1; pb['last_source_time']=source_time
                                self.sword_base_prev,self.sword_tip_prev=base,tip
                        else:
                            world=_v3(self.melee_arms[side].get('strike_tip',self.melee_arms[side]['fist']).getPos(self.render)); prev=self.melee_fist_world_prev.get(side)
                            if prev is not None and source_time-pb.get('last_source_time',-9.0)>=.16 and pb.get('hit_count',0)<4 and (world-prev).length()>.003:
                                if self._apply_melee_hit(side,prev,world,pb['charge']): pb['hit_count']=pb.get('hit_count',0)+1; pb['last_source_time']=source_time
                            self.melee_fist_world_prev[side]=world
                    pb['last_sample_time']=source_time
                    if source_time>=pb['duration']-1e-5:
                        self.melee_playback[side]=None; self._rebuild_melee_trail(side,[])
                        if side=='right': self.sword_base_prev=None; self.sword_tip_prev=None
                else:
                    targets=pb['targets']; idx=pb['index']
                    if idx>=len(targets)-1:
                        self.melee_playback[side]=None; self._rebuild_melee_trail(side,[])
                        neutral=Vec3((-MELEE_NEUTRAL_X if side=='left' else MELEE_NEUTRAL_X),MELEE_NEUTRAL_Y,-.18); self._update_melee_pose(side,neutral)
                        if side=='right': self.sword_base_prev=None; self.sword_tip_prev=None
                        continue
                    pb['segment_t'] += dt/max(.025,pb['duration']/max(1,len(targets)-1))
                    while pb['segment_t']>=1.0 and pb['index']<len(targets)-2:
                        pb['segment_t']-=1.0; pb['index']+=1; idx=pb['index']
                    t=max(0.0,min(1.0,pb['segment_t'])); a=targets[idx]; b=targets[min(idx+1,len(targets)-1)]
                    tt=t*t*(3.0-2.0*t); target=a+(b-a)*tt
                    wrist=self._update_melee_pose(side,target)
                    self._tick_melee_motion_audio(side,target,dt,sword=(side=='right'))
                    if wrist is not None:
                        if side=='right' and not ARGS.melee_smoke:
                            blade=self._sword_blade_world()
                            if blade is not None:
                                base,tip=blade
                                if self.sword_base_prev is not None and self.sword_tip_prev is not None and not pb['hit'] and pb['index']>=pb.get('hit_start',0) and pb['index']<=pb.get('hit_end',999):
                                    if self._apply_sword_hit(self.sword_base_prev,self.sword_tip_prev,base,tip,pb['charge'],pb.get('travel',0.0),dt): pb['hit']=True
                                self.sword_base_prev,self.sword_tip_prev=base,tip
                        else:
                            world=_v3(self.melee_arms[side].get('strike_tip',self.melee_arms[side]['fist']).getPos(self.render)); prev=self.melee_fist_world_prev.get(side)
                            if prev is not None and not pb['hit'] and pb['index']>=pb.get('hit_start',0) and pb['index']<=pb.get('hit_end',999) and (world-prev).length()>0.003:
                                if self._apply_melee_hit(side,prev,world,pb['charge']): pb['hit']=True
                            self.melee_fist_world_prev[side]=world
                    if idx>=len(targets)-2 and t>=.98:
                        self.melee_playback[side]=None; self._rebuild_melee_trail(side,[])
                        if side=='right': self.sword_base_prev=None; self.sword_tip_prev=None
            else:
                neutral=Vec3((-MELEE_NEUTRAL_X if side=='left' else MELEE_NEUTRAL_X),MELEE_NEUTRAL_Y,-.18)
                wrist=self._update_melee_pose(side,neutral)
                self.melee_fist_world_prev[side]=_v3(self.melee_arms[side].get('strike_tip',self.melee_arms[side]['fist']).getPos(self.render)) if wrist is not None else None
                if side=='right':
                    blade=self._sword_blade_world()
                    if blade is not None: self.sword_base_prev,self.sword_tip_prev=blade
        for side in ('left','right'):
            if not self.melee_hold.get(side) and not self.melee_playback.get(side):
                arm=self.melee_arms.get(side)
                if arm:
                    neutral=Vec3((-MELEE_NEUTRAL_X if side=='left' else MELEE_NEUTRAL_X),MELEE_NEUTRAL_Y,-.18)
                    self._update_melee_pose(side,_v3(arm.get('last_target',neutral)))
        self._update_sword_fx(dt)

    def _apply_weapon_palette(self):
        spec = self.weapon_modes[self.current_weapon_mode]
        for node in self.weapon_fill_nodes: node.setColor(*spec['fill'])
        for node in self.weapon_wire_nodes: node.setColor(*spec['wire'])
        if self.weapon_palette_glow is not None: self.weapon_palette_glow.setColor(*spec['glow'])

    def set_weapon_mode(self, mode):
        mode = str(mode).upper()
        if mode not in self.weapon_modes:
            return
        self.current_weapon_mode = mode
        self._apply_weapon_palette()
        self.last_hit = f'RIFLE MODE {self.weapon_modes[mode]["display"]}'
        self._status()

    def cycle_weapon_mode(self):
        if self.combat_mode != 'rifle': return
        idx = self.weapon_mode_order.index(self.current_weapon_mode)
        self.set_weapon_mode(self.weapon_mode_order[(idx + 1) % len(self.weapon_mode_order)])

    def _update_viewmodels(self, dt):
        horizontal_speed = math.hypot(self.player_vel.x, self.player_vel.y)
        move_ratio = min(1.35, horizontal_speed / max(0.001, WALK_SPEED)) if self.on_ground else 0.0
        if self.on_ground and horizontal_speed>0.03:
            self.locomotion_phase=(self.locomotion_phase+horizontal_speed*max(0.0,float(dt))*LOCOMOTION_PHASE_RATE)%(2.0*math.pi)
        phase=self.locomotion_phase
        bob = math.sin(phase*2.0) * LOCOMOTION_BOB_SCALE * move_ratio
        sway = math.sin(phase) * LOCOMOTION_SWAY_SCALE * move_ratio
        self.weapon_recoil = max(0.0, self.weapon_recoil - dt * 6.2)
        r = self.weapon_recoil
        base_pos, base_h, base_p, base_r = self.weapon_base
        self.weapon_root.setPos(base_pos + Vec3(sway * 1.4, -r * .12, bob - r * .025))
        self.weapon_root.setHpr(base_h - sway * 240.0, base_p - r * 8.5, base_r - sway * 180.0)
        for spinner, speed, direction in self.weapon_spinner_groups:
            spinner.setR((spinner.getR() + speed * direction * dt) % 360.0)


    # ---------- ASCII BODY ----------
    def _build_glyph_prototypes(self):
        self.glyph_proto = {}
        for ch in '@#%+=*:.' + '&()<>~SL8K|/\\':
            t = TextNode('glyph_' + ch)
            t.setText(ch)
            t.setAlign(TextNode.ACenter)
            t.setTextColor(1,1,1,1)
            np = NodePath(t.generate())
            np.setLightOff()
            self.glyph_proto[ch] = np

    @staticmethod
    def _apply_glyph_color(node, color):
        # TextNode.generate() carries white vertex color.  ColorScale is the
        # intended modulation path for generated/per-vertex-colored geometry.
        node.clearColor()
        node.setColorScale(color)

    @staticmethod
    def _base_glyph_color(item):
        base = Vec4(MEMORY_PALETTE.get(item.get('region'), MEMORY_PALETTE['torso']))
        normal = item.get('n', (0.0, 0.0, 1.0))
        depth = max(-1.0, min(1.0, float(normal[1])))
        lift = 0.055 * (depth + 1.0) * 0.5
        return Vec4(
            min(1.0, base.x + lift * 0.35),
            min(1.0, base.y + lift),
            min(1.0, base.z + lift),
            1.0,
        )

    @staticmethod
    def _ellipsoid_points(center, radii, count):
        cx, cy, cz = center
        rx, ry, rz = radii
        phi = (1.0 + math.sqrt(5.0)) * 0.5
        out = []
        for i in range(count):
            z = 1.0 - 2.0 * (i + 0.5) / count
            theta = 2.0 * math.pi * i / phi
            rr = math.sqrt(max(0.0, 1.0 - z * z))
            out.append(Vec3(cx + rx * rr * math.cos(theta),
                            cy + ry * rr * math.sin(theta),
                            cz + rz * z))
        return out

    @staticmethod
    def _polyline_points(points, spacing=NEURAL_PATH_SPACING):
        out=[]
        for a,b in zip(points[:-1],points[1:]):
            a=Vec3(*a); b=Vec3(*b); d=b-a; length=d.length()
            steps=max(1,int(math.ceil(length/spacing)))
            for i in range(steps): out.append(a+d*(i/float(steps)))
        out.append(Vec3(*points[-1])); return out

    @staticmethod
    def _point_clearance(point, points):
        p=_v3(point); best=1e9
        for q in points:
            qv=_v3(q); d=(p-qv).length()
            if d<best: best=d
        return best

    def _build_neural_system(self):
        """Build sparse neural glyphs in joint-local batches so the network follows the rig."""
        _checkpoint('neural_build_begin')
        surface_points=[item['p'] for item in self.surface]
        organ_points=[(p.x,p.y,p.z) for p in self.organ_points]
        accepted=[]; accepted_meta=[]
        glyph_cycle = "|/\\+:."
        groups={}

        def bind_for(path_name,pos):
            if not self.rig_joints:
                return 'static'
            if path_name == 'spinal_trunk':
                names=['head_base','neck','spine_high','spine_mid','spine_low','pelvis']
            elif path_name.startswith('left_shoulder') or path_name.startswith('left_arm'):
                names=['left_shoulder','left_elbow','left_wrist','left_hand']
            elif path_name.startswith('right_shoulder') or path_name.startswith('right_arm'):
                names=['right_shoulder','right_elbow','right_wrist','right_hand']
            elif path_name.startswith('left_leg'):
                names=['left_hip','left_knee','left_ankle','left_foot']
            elif path_name.startswith('right_leg'):
                names=['right_hip','right_knee','right_ankle','right_foot']
            else:
                names=list(self.rig_joints)
            return self._rig_joint_for_point(pos,names)

        for path_name,path in NEURAL_PATHS.items():
            for pos in self._polyline_points(path,spacing=0.060):
                if self._point_clearance(pos,surface_points) < NEURAL_BODY_CLEARANCE: continue
                organ_clear=self._point_clearance(pos,organ_points)
                brain_stem=path_name == 'spinal_trunk' and pos.z > 1.60
                if organ_clear < NEURAL_ORGAN_CLEARANCE and not brain_stem: continue
                if accepted and min((pos-q).length() for q in accepted) < .024: continue
                bind_name=bind_for(path_name,pos)
                accepted.append(_v3(pos)); accepted_meta.append((path_name,bind_name))
                if bind_name not in groups:
                    parent=self.body_root if bind_name=='static' else self.rig_joints[bind_name]
                    groups[bind_name]=parent.attachNewNode('neural_group_'+bind_name)
                    groups[bind_name].setTwoSided(True)
                holder=self.body_root.attachNewNode(f'neural_{path_name}_{len(accepted)-1:03d}')
                self.glyph_proto[glyph_cycle[(len(accepted)-1)%len(glyph_cycle)]].instanceTo(holder)
                holder.setPos(pos); holder.setScale(NEURAL_GLYPH_SCALE*1.12); holder.setLightOff()
                self._reparent_preserve(holder,groups[bind_name])
        self.neural_count=len(accepted)
        self.neural_points=[_v3(p) for p in accepted]
        self.neural_names=[m[0] for m in accepted_meta]
        self.neural_bindings=[m[1] for m in accepted_meta]
        self.neural_nodes=[]
        for group in groups.values():
            group.flattenStrong(); self._apply_glyph_color(group,NEURAL_RED); self.neural_nodes.append(group)
        _checkpoint('neural_build_ready',f'glyphs={self.neural_count} groups={len(self.neural_nodes)} rigged={bool(self.rig_joints)}')

    # ---------- SOLID INTERNAL SKELETON ----------
    @staticmethod
    def _make_unit_bone_proto(sides=10):
        """Create a faceted long-bone prototype with gently flared ends."""
        fmt = GeomVertexFormat.getV3n3()
        vd = GeomVertexData('unit_internal_bone', fmt, Geom.UHStatic)
        vw = GeomVertexWriter(vd, 'vertex')
        nw = GeomVertexWriter(vd, 'normal')
        prim = GeomTriangles(Geom.UHStatic)
        rings = ((0.00,1.18),(0.16,0.90),(0.84,0.90),(1.00,1.18))
        ridx=[]
        for y,rad in rings:
            row=[]
            for i in range(sides):
                a=2.0*math.pi*i/sides
                x,z=math.cos(a)*rad,math.sin(a)*rad
                idx=vd.getNumRows(); row.append(idx)
                vw.addData3f(x,y,z); nw.addData3f(math.cos(a),0,math.sin(a))
            ridx.append(row)
        for r0,r1 in zip(ridx[:-1],ridx[1:]):
            for i in range(sides):
                j=(i+1)%sides
                prim.addVertices(r0[i],r0[j],r1[j]); prim.addVertices(r0[i],r1[j],r1[i])
        for y,row,normal,reverse in ((0.0,ridx[0],(0,-1,0),True),(1.0,ridx[-1],(0,1,0),False)):
            center=vd.getNumRows(); vw.addData3f(0,y,0); nw.addData3f(*normal)
            cap=[]
            for i in range(sides):
                a=2.0*math.pi*i/sides; idx=vd.getNumRows(); cap.append(idx)
                vw.addData3f(math.cos(a)*1.18,y,math.sin(a)*1.18); nw.addData3f(*normal)
            for i in range(sides):
                j=(i+1)%sides
                if reverse: prim.addVertices(center,cap[j],cap[i])
                else: prim.addVertices(center,cap[i],cap[j])
        g=Geom(vd); g.addPrimitive(prim)
        gn=GeomNode('unit_internal_bone'); gn.addGeom(g)
        return NodePath(gn)

    @staticmethod
    def _make_joint_proto(slices=10, stacks=5):
        """Create a reusable low-poly rounded joint instead of an octahedron."""
        fmt=GeomVertexFormat.getV3n3()
        vd=GeomVertexData('unit_internal_joint',fmt,Geom.UHStatic)
        vw=GeomVertexWriter(vd,'vertex'); nw=GeomVertexWriter(vd,'normal')
        rows=[]
        for si in range(stacks+1):
            phi=math.pi*si/stacks; sp,cp=math.sin(phi),math.cos(phi)
            row=[]
            for ti in range(slices):
                th=2.0*math.pi*ti/slices
                v=Vec3(sp*math.cos(th),sp*math.sin(th),cp)
                idx=vd.getNumRows(); row.append(idx); vw.addData3f(v); nw.addData3f(v)
            rows.append(row)
        prim=GeomTriangles(Geom.UHStatic)
        for si in range(stacks):
            for ti in range(slices):
                tj=(ti+1)%slices
                a,b,c,d=rows[si][ti],rows[si][tj],rows[si+1][tj],rows[si+1][ti]
                prim.addVertices(a,b,c); prim.addVertices(a,c,d)
        g=Geom(vd); g.addPrimitive(prim)
        gn=GeomNode('unit_internal_joint'); gn.addGeom(g)
        return NodePath(gn)

    @staticmethod
    def _make_skull_shell_proto(spec):
        """Create a thick faceted cranium cap with an open face and neck side.

        The outer and inner ellipsoid patches are joined at their four borders,
        so the cranium is genuine closed solid geometry rather than a one-sided
        decorative surface.  Facial bones remain separate named solid segments.
        """
        center=spec.get('center',[0.0,0.018,1.692])
        radii=spec.get('outer_radii',[0.058,0.060,0.064])
        thickness=float(spec.get('thickness',0.0030))
        slices=max(6,int(spec.get('slices',18)))
        stacks=max(4,int(spec.get('stacks',12)))
        theta0=math.radians(float(spec.get('theta_min_deg',-10.0)))
        theta1=math.radians(float(spec.get('theta_max_deg',190.0)))
        phi0=math.radians(float(spec.get('phi_min_deg',12.0)))
        phi1=math.radians(float(spec.get('phi_max_deg',150.0)))
        cx,cy,cz=(float(center[0]),float(center[1]),float(center[2]))
        rx,ry,rz=(float(radii[0]),float(radii[1]),float(radii[2]))
        irx,iry,irz=(max(.001,rx-thickness),max(.001,ry-thickness),max(.001,rz-thickness))

        fmt=GeomVertexFormat.getV3n3()
        vd=GeomVertexData('formed_ascii_skull',fmt,Geom.UHStatic)
        vw=GeomVertexWriter(vd,'vertex'); nw=GeomVertexWriter(vd,'normal')
        outer=[]; inner=[]

        def ellipsoid_normal(x,y,z,rrx,rry,rrz,sign=1.0):
            n=Vec3((x-cx)/(rrx*rrx),(y-cy)/(rry*rry),(z-cz)/(rrz*rrz))
            if n.lengthSquared() > 1e-12: n.normalize()
            else: n=Vec3(0,0,1)
            return n*sign

        for si in range(stacks+1):
            phi=phi0+(phi1-phi0)*si/stacks
            sp,cp=math.sin(phi),math.cos(phi)
            orow=[]; irow=[]
            for ti in range(slices+1):
                theta=theta0+(theta1-theta0)*ti/slices
                ct,st=math.cos(theta),math.sin(theta)
                ox,oy,oz=cx+rx*sp*ct,cy+ry*sp*st,cz+rz*cp
                oi=vd.getNumRows(); vw.addData3f(ox,oy,oz); on=ellipsoid_normal(ox,oy,oz,rx,ry,rz,1.0); nw.addData3f(float(on.x),float(on.y),float(on.z)); orow.append(oi)
                ix,iy,iz=cx+irx*sp*ct,cy+iry*sp*st,cz+irz*cp
                ii=vd.getNumRows(); vw.addData3f(ix,iy,iz); inn=ellipsoid_normal(ix,iy,iz,irx,iry,irz,-1.0); nw.addData3f(float(inn.x),float(inn.y),float(inn.z)); irow.append(ii)
            outer.append(orow); inner.append(irow)

        prim=GeomTriangles(Geom.UHStatic)
        for si in range(stacks):
            for ti in range(slices):
                a,b,c,d=outer[si][ti],outer[si][ti+1],outer[si+1][ti+1],outer[si+1][ti]
                prim.addVertices(a,b,c); prim.addVertices(a,c,d)
                a,b,c,d=inner[si][ti],inner[si+1][ti],inner[si+1][ti+1],inner[si][ti+1]
                prim.addVertices(a,b,c); prim.addVertices(a,c,d)

        # Close the open face-side edges and the upper/lower cut edges, turning the
        # ellipsoid patch into a thick solid shell with a genuine rim.
        for si in range(stacks):
            for ti in (0,slices):
                oa,ob=outer[si][ti],outer[si+1][ti]
                ia,ib=inner[si][ti],inner[si+1][ti]
                if ti==0:
                    prim.addVertices(oa,ia,ib); prim.addVertices(oa,ib,ob)
                else:
                    prim.addVertices(oa,ob,ib); prim.addVertices(oa,ib,ia)
        for ti in range(slices):
            for si in (0,stacks):
                oa,ob=outer[si][ti],outer[si][ti+1]
                ia,ib=inner[si][ti],inner[si][ti+1]
                if si==0:
                    prim.addVertices(oa,ob,ib); prim.addVertices(oa,ib,ia)
                else:
                    prim.addVertices(oa,ia,ib); prim.addVertices(oa,ib,ob)

        g=Geom(vd); g.addPrimitive(prim)
        gn=GeomNode('formed_ascii_skull'); gn.addGeom(g)
        return NodePath(gn)

    def _style_bone_node(self, node):
        node.setColor(self.skeleton_bone_color)
        node.setTwoSided(True)
        node.setLight(self.skeleton_ambient_np)
        node.setLight(self.skeleton_key_np)

    def _rig_joint_for_point(self, point, candidates=None):
        if not self.rig_joints:
            return None
        p=_v3(point)
        names=list(candidates or self.rig_joints.keys())
        return min(names, key=lambda n:(p-self.rig_rest_positions[n]).lengthSquared())

    def _reparent_preserve(self, node, parent):
        if parent is not None and not parent.isEmpty():
            node.wrtReparentTo(parent)
        return node

    def _add_solid_bone(self, name, a, b, radius, parent_node=None):
        a=_v3(a); b=_v3(b); delta=b-a; length=delta.length()
        if length <= 1e-6:
            return None
        holder=self.body_root.attachNewNode('bone_'+str(name))
        self.skeleton_bone_proto.instanceTo(holder)
        holder.setPos(a); holder.lookAt(b); holder.setScale(float(radius),float(length),float(radius))
        self._style_bone_node(holder)
        if parent_node is not None: self._reparent_preserve(holder,parent_node)
        self.skeleton_bones.append(holder)
        self.skeleton_bone_nodes[str(name)] = holder
        return holder

    def _build_internal_skeleton(self):
        """Build the visible skeleton and make its joint hierarchy the NPC parent authority."""
        if ARGS.safe_mode or ARGS.no_skeleton:
            self.skeleton_segment_count=0; self.skeleton_joint_count=0; self.skeleton_skull_count=0
            self.rig_root=None; self.rig_joints={}; self.rig_rest_positions={}; self.head_track_h=0.0; self.head_track_p=0.0
            _checkpoint('solid_skeleton_disabled')
            return
        _checkpoint('solid_skeleton_begin')
        data=json.loads(SKELETON_CACHE.read_text())
        self.skeleton_data=data
        self.rig_root=self.body_root.attachNewNode('skeleton_rig_parent')
        self.skeleton_root=self.rig_root
        self.skeleton_bone_proto=self._make_unit_bone_proto(12)
        self.skeleton_joint_proto=self._make_joint_proto(12,6)
        self.skeleton_bone_color=Vec4(*data.get('color',[.86,.91,.80,1.0]))
        amb=AmbientLight('skeleton_ambient'); amb.setColor(Vec4(.14,.16,.17,1))
        self.skeleton_ambient_np=self.render.attachNewNode(amb)
        key=DirectionalLight('skeleton_key'); key.setColor(Vec4(.55,.60,.61,1))
        self.skeleton_key_np=self.render.attachNewNode(key); self.skeleton_key_np.setHpr(-35,-55,0)
        self.rig_rest_positions={name:_v3(pos) for name,pos in data['joints'].items()}
        parents=data.get('rig_parent',{})
        self.rig_parent_names=dict(parents)
        self.skeleton_bone_specs={str(b['name']):dict(b) for b in data.get('bones',[])}
        pending=set(self.rig_rest_positions)
        while pending:
            progressed=False
            for name in list(pending):
                parent_name=parents.get(name)
                if parent_name is not None and parent_name not in self.rig_joints: continue
                parent=self.rig_root if parent_name is None else self.rig_joints[parent_name]
                node=parent.attachNewNode('rig_joint_'+name)
                if parent_name is None: node.setPos(self.rig_rest_positions[name])
                else: node.setPos(self.rig_rest_positions[name]-self.rig_rest_positions[parent_name])
                self.rig_joints[name]=node; pending.remove(name); progressed=True
            if not progressed: raise RuntimeError('Rig hierarchy contains unresolved parents')
        for bone in data['bones']:
            self._add_solid_bone(bone['name'],self.rig_rest_positions[bone['a']],self.rig_rest_positions[bone['b']],bone['radius'],self.rig_joints.get(bone['a']))
        curve_bind=data.get('curve_bindings',{})
        for curve in data.get('curves',[]):
            pts=[_v3(p) for p in curve['points']]
            parent=self.rig_joints.get(curve_bind.get(curve['name'],'spine_high'))
            for i,(a,b) in enumerate(zip(pts[:-1],pts[1:]),1):
                self._add_solid_bone(f"{curve['name']}_{i}",a,b,curve['radius'],parent)
        skull_spec=data.get('skull')
        if skull_spec:
            skull_holder=self.body_root.attachNewNode('skull_cranium_solid')
            self._make_skull_shell_proto(skull_spec).instanceTo(skull_holder)
            self._style_bone_node(skull_holder)
            self._reparent_preserve(skull_holder,self.rig_joints.get(data.get('skull_joint','head_base')))
            self.skeleton_skull_parts.append(skull_holder)
        joint_radius=float(data.get('joint_radius',.007))
        joint_radii=data.get('joint_radii',{})
        for name,node in self.rig_joints.items():
            holder=node.attachNewNode('joint_visual_'+name)
            jr=float(joint_radii.get(name,joint_radius))
            self.skeleton_joint_proto.instanceTo(holder); holder.setScale(jr)
            self._style_bone_node(holder); self.skeleton_joints.append(holder)
        self.skeleton_segment_count=len(self.skeleton_bones)
        self.skeleton_joint_count=len(self.skeleton_joints)
        self.skeleton_skull_count=len(self.skeleton_skull_parts)
        _checkpoint('solid_skeleton_ready',f'segments={self.skeleton_segment_count} joints={self.skeleton_joint_count} skull={self.skeleton_skull_count} rig=parent')

    def _build_internal_organs(self):
        self.organ_root = self.body_root.attachNewNode('ascii_internal_organs_manifest')
        organ_bind_map=getattr(self,'skeleton_data',{}).get('organ_bindings',{}) if self.rig_joints else {}
        for organ_name, recipe in ORGAN_RECIPES.items():
            pts=self._ellipsoid_points(recipe['center'],recipe['radii'],recipe['count'])
            glyphs=recipe['glyphs']
            bind_name=organ_bind_map.get(organ_name)
            bind_joint=self.rig_joints.get(bind_name) if bind_name else None
            for j,pos in enumerate(pts):
                holder=self.body_root.attachNewNode(f'organ_{organ_name}_{j:02d}')
                self.glyph_proto[glyphs[j%len(glyphs)]].instanceTo(holder)
                holder.setPos(pos); holder.setScale(ORGAN_GLYPH_SCALE); holder.setBillboardPointEye(); holder.setLightOff()
                color=Vec4(recipe['color']); self._apply_glyph_color(holder,color)
                if bind_joint is not None: self._reparent_preserve(holder,bind_joint)
                self.organ_nodes.append(holder); self.organ_points.append(_v3(pos)); self.organ_original_colors.append(color); self.organ_names.append(organ_name); self.organ_bindings.append(bind_name or 'static')
        if not (ARGS.safe_mode or ARGS.no_neural):
            try: self._build_neural_system()
            except Exception as exc:
                for n in list(self.neural_nodes):
                    try: n.removeNode()
                    except Exception: pass
                self.neural_nodes=[]; self.neural_points=[]; self.neural_names=[]; self.neural_bindings=[]; self.neural_count=0
                _checkpoint('neural_disabled',f'{type(exc).__name__}: {exc}')
                print(f'ASCII_MATTER_NEURAL_DISABLED={type(exc).__name__}: {exc}',file=sys.stderr)
        else:
            self.neural_count=0

    def _glyph_parent(self, bind_name):
        return self.rig_joints.get(bind_name, self.body_root)

    @staticmethod
    def _lod_hash(index):
        return ((int(index) * 1103515245 + 12345) >> 8) & 255

    def _glyph_kept_for_lod(self, index):
        tier = max(0, min(2, self.lod_tier if self.lod_tier >= 0 else 0))
        return self._lod_hash(index) < LOD_KEEP_THRESHOLDS[tier]

    def _glyph_render_color(self, index):
        base = self.original_colors[index]
        tint,influence = self._wound_tint(self._current_glyph_world_pos(index)) if self.wounds else (MEMORY_WOUND_RED,0.0)
        if influence <= 0.0001: return base
        return Vec4(base.x + (tint.x-base.x)*influence,
                    base.y + (tint.y-base.y)*influence,
                    base.z + (tint.z-base.z)*influence, 1.0)

    def _build_binding_bounds(self):
        self.binding_bounds = {}
        for bind, members in self.binding_members.items():
            if not members:
                continue
            pts=[self.glyph_local_positions[i] for i in members]
            center=Vec3(0,0,0)
            for q in pts: center += q
            center /= float(len(pts))
            radius=max((q-center).length() for q in pts) + BODY_GLYPH_SCALE*1.75
            self.binding_bounds[bind]=(center,float(radius))

    def _rebuild_glyph_batch(self, bind_name):
        old=self.glyph_batches.pop(bind_name,None)
        self.glyph_batch_vdatas.pop(bind_name,None)
        self.glyph_batch_color_rows.pop(bind_name,None)
        if old is not None and not old.isEmpty(): old.removeNode()
        parent=self._glyph_parent(bind_name)
        root=parent.attachNewNode('ascii_batch_'+str(bind_name))
        fmt=GeomVertexFormat.getV3c4()
        vd=GeomVertexData('ascii_strokes_'+str(bind_name),fmt,Geom.UHDynamic)
        vw=GeomVertexWriter(vd,'vertex'); cw=GeomVertexWriter(vd,'color')
        prim=GeomLines(Geom.UHStatic)
        row=0; visible=0; color_rows={}
        up=Vec3(0,0,1)
        for i in self.binding_members.get(bind_name,()):
            if not self.live[i] or not self._glyph_kept_for_lod(i): continue
            pos=self.glyph_local_positions[i]; n=_v3(self.glyph_local_normals[i])
            if n.lengthSquared()<1e-10: n=Vec3(0,1,0)
            else: n.normalize()
            ref=up if abs(n.dot(up))<.92 else Vec3(0,1,0)
            tangent=ref.cross(n)
            if tangent.lengthSquared()<1e-10: tangent=Vec3(1,0,0)
            else: tangent.normalize()
            bitangent=n.cross(tangent); bitangent.normalize()
            color=self._glyph_render_color(i)
            strokes=ASCII_STROKES.get(self.surface[i]['g'],ASCII_STROKES['.'])
            row_start=row
            for u1,v1,u2,v2 in strokes:
                a=pos + tangent*(u1*BODY_GLYPH_SCALE) + bitangent*(v1*BODY_GLYPH_SCALE)
                b=pos + tangent*(u2*BODY_GLYPH_SCALE) + bitangent*(v2*BODY_GLYPH_SCALE)
                vw.addData3f(a); cw.addData4f(color)
                vw.addData3f(b); cw.addData4f(color)
                prim.addVertices(row,row+1); row += 2
            color_rows[i]=(row_start,row)
            visible += 1
        if row:
            geom=Geom(vd); geom.addPrimitive(prim)
            gn=GeomNode('ascii_strokes_'+str(bind_name)); gn.addGeom(geom)
            node=root.attachNewNode(gn); node.setLightOff(); node.setRenderModeThickness(1.50)
        self.glyph_batches[bind_name]=root
        self.glyph_batch_vdatas[bind_name]=vd
        self.glyph_batch_color_rows[bind_name]=color_rows
        self.perf_counters['glyph_batch_rebuilds'] += 1
        return visible

    def _rebuild_all_glyph_batches(self):
        visible=0
        for bind in self.binding_members:
            visible += self._rebuild_glyph_batch(bind)
        self.lod_visible_count=visible

    def _update_glyph_batch_colors(self, bind_name):
        """Update only the color column of an existing ASCII batch.

        Wound bloom/rewind changes color, not topology. Rewriting the small dynamic color
        column avoids allocating a new Geom/NodePath every visual tick.
        """
        vd=self.glyph_batch_vdatas.get(bind_name)
        rows=self.glyph_batch_color_rows.get(bind_name)
        if vd is None or not rows:
            return
        cw=GeomVertexWriter(vd,'color')
        for i,(start,end) in rows.items():
            color=self._glyph_render_color(i)
            for row in range(start,end):
                cw.setRow(row); cw.setData4f(color)
        self.perf_counters['glyph_color_updates'] += 1

    def _wound_affected_bindings(self):
        if not self.wounds:
            return set(self.binding_members)
        affected=set()
        for wound in self.wounds:
            center=self._wound_center_world(wound)
            for bind,(local_center,radius) in self.binding_bounds.items():
                parent=self._glyph_parent(bind)
                world_center=_v3(self.render.getRelativePoint(parent, local_center))
                if (world_center-center).length() <= radius+wound.radius+BODY_GLYPH_SCALE:
                    affected.add(bind)
        return affected

    def _glyph_batch_stats(self):
        geoms=0; nodes=0
        for batch in self.glyph_batches.values():
            if batch is None or batch.isEmpty(): continue
            nodes += batch.getNumDescendants()+1
            geoms += batch.findAllMatches('**/+GeomNode').getNumPaths()
        return nodes,geoms

    def _load_body(self):
        data=json.loads(GLYPH_CACHE.read_text())
        self.surface=data['points']
        self.body_root=self.render.attachNewNode('ascii_npc_root')
        self.body_root.setPos(0,0,0.15)
        # Skeleton first: its joint hierarchy becomes the parent transform tree.
        self._build_internal_skeleton()
        bind_map=getattr(self,'skeleton_data',{}).get('body_bindings',[]) if self.rig_joints else []
        for i,item in enumerate(self.surface):
            # Pass 28 keeps a transform-only logical anchor for hit/wound/rig authority.
            # Visible text is emitted later as flattened per-joint batches.
            holder=self.body_root.attachNewNode(f'glyph_anchor_{i:04d}')
            holder.setPos(*item['p'])
            bind_name=bind_map[i] if i<len(bind_map) else None
            parent=self.rig_joints.get(bind_name, self.body_root)
            if bind_name in self.rig_joints:
                self._reparent_preserve(holder,parent)
            original=self._base_glyph_color(item)
            self.glyph_nodes.append(holder); self.original_colors.append(original); self.live.append(True); self.body_bindings.append(bind_name or 'static')
            self.glyph_local_positions.append(_v3(holder.getPos(parent)))
            normal=Vec3(*item.get('n',(0,1,0)))
            if parent != self.body_root:
                normal=_v3(parent.getRelativeVector(self.body_root,normal))
            if normal.lengthSquared() < 1e-10: normal=Vec3(0,1,0)
            else: normal.normalize()
            self.glyph_local_normals.append(normal)
        self.body_count=len(self.glyph_nodes)
        self.binding_members={}
        for i,b in enumerate(self.body_bindings): self.binding_members.setdefault(b,[]).append(i)
        self._build_binding_bounds()
        # Initial tier is full; _update_render_lod immediately selects the normal-distance tier.
        if self.lod_tier < 0: self.lod_tier=0
        self._rebuild_all_glyph_batches()
        self._build_internal_organs()

    # ---------- UI ----------
    def _build_ui(self):
        self.cross = DirectLabel(text='+', scale=.031, pos=(0,0,0), text_fg=(.72,.96,1,.88), frameColor=(0,0,0,0))
        self.status = DirectLabel(text='', scale=.033, pos=(-1.27,0,.92), text_align=TextNode.ALeft,
                                  text_fg=(.63,.82,.88,.92), frameColor=(0,0,0,0))
        self.hint = DirectLabel(text='F1 CONTROLS', scale=.028, pos=(1.27,0,.92), text_align=TextNode.ARight,
                                text_fg=(.42,.56,.60,.72), frameColor=(0,0,0,0))
        self.help = DirectFrame(frameColor=(.0,.0,.0,.80), frameSize=(-.60,.60,-.34,.34), pos=(.60,0,.60))
        DirectLabel(parent=self.help, text='FIRST-PERSON CONTROLS', scale=.048, pos=(-.53,0,.24), text_align=TextNode.ALeft,
                    text_fg=(.72,.96,1,1), frameColor=(0,0,0,0))
        help_controls = (
            'WASD   move\nMOUSE   look\nSHIFT   sprint\nSPACE   jump\nCTRL    crouch\nM       rifle / holo fists\n'
            'LMB     rifle fire / left holo fist\nRMB     cycle ammo / right laser sword\n'
            'HOLD+DRAG melee = record hand/wrist / release = full 150% replay\n'
            'MELEE 1-9  save fresh RMB recording / replay saved sword slot\n'
            'F2      Motion Forge editor\nF3      Combo Composer\n'
            + ('X       play armed combo\nC       cycle armed combos\nTAB     return to HoloVerse\nF10     release / capture mouse\nESC     HoloVerse pause\n'
               if self._holoverse_embedded else
               '0       play armed combo\nTAB     cycle armed combos\nESC     release / capture mouse\n')
            + 'RIFLE 1/2/3   automatic / shotgun / sniper\nHOLD R  rewind wound memory\nF1      controls\nF11     fullscreen'
        )
        DirectLabel(parent=self.help,
                    text=help_controls,
                    scale=.034, pos=(-.53,0,.16), text_align=TextNode.ALeft,
                    text_fg=(.83,.88,.90,1), frameColor=(0,0,0,0))
        self.help.hide()
        self._build_motion_forge_ui()
        self._build_combo_composer_ui()
        self._status()

    def _status(self):
        active = sum(self.live)
        state = 'CROUCH' if self.crouching else ('AIR' if not self.on_ground else 'GROUND')
        memory = 'MEMORY <<' if self.rewinding else ('WOUNDED' if (self.wounds or self.detached_limbs) else 'MEMORY READY')
        ammo = self.weapon_modes[self.current_weapon_mode]['label'] if self.combat_mode=='rifle' else 'FIST+SWORD'
        perf=('FULL','BAL','FAR')[max(0,min(2,self.lod_tier))] if self.lod_tier >= 0 else 'FULL'
        txt=f'ASCII {active:04d}/{self.body_count:04d}   ORGAN {len(ORGAN_RECIPES):02d}   BONE {self.skeleton_segment_count:02d}   SEVER {len(self.detached_limbs):02d}   FRAG {len(self.fragments):03d}   WOUND {len(self.wounds):02d}   COMBAT {ammo}   PERF {perf}   {memory}   {state}'
        if txt != self.status_cache:
            self.status['text']=txt; self.status_cache=txt

    # ---------- PASS 43 MOTION FORGE ----------
    def _build_motion_forge_ui(self):
        self.motion_forge=DirectFrame(frameColor=(.012,.018,.026,.96),frameSize=(-1.05,1.05,-.67,.67),pos=(0,0,0))
        DirectLabel(parent=self.motion_forge,text='MOTION FORGE',scale=.060,pos=(-.95,0,.56),text_align=TextNode.ALeft,text_fg=(.64,.94,1,1),frameColor=(0,0,0,0))
        DirectLabel(parent=self.motion_forge,text='PLAYER-AUTHORED SWORD ANIMATION LIBRARY',scale=.027,pos=(-.95,0,.49),text_align=TextNode.ALeft,text_fg=(.46,.61,.67,1),frameColor=(0,0,0,0))
        self.motion_forge_slot_buttons=[]
        for i in range(1,MELEE_SLOT_COUNT+1):
            x=-.86+(i-1)*.215
            b=DirectButton(parent=self.motion_forge,text=str(i),scale=.042,pos=(x,0,.37),frameSize=(-.68,.68,-.58,.58),frameColor=(.07,.10,.13,.96),text_fg=(.82,.90,.94,1),command=self._forge_select_slot,extraArgs=[i])
            self.motion_forge_slot_buttons.append(b)
        self.motion_forge_labels['name']=DirectLabel(parent=self.motion_forge,text='',scale=.044,pos=(-.94,0,.24),text_align=TextNode.ALeft,text_fg=(.94,.98,1,1),frameColor=(0,0,0,0))
        self.motion_forge_labels['stats']=DirectLabel(parent=self.motion_forge,text='',scale=.031,pos=(-.94,0,.13),text_align=TextNode.ALeft,text_fg=(.74,.82,.86,1),frameColor=(0,0,0,0))
        self.motion_forge_labels['edit']=DirectLabel(parent=self.motion_forge,text='',scale=.031,pos=(-.94,0,-.02),text_align=TextNode.ALeft,text_fg=(.70,.93,1,1),frameColor=(0,0,0,0))
        DirectLabel(parent=self.motion_forge,text='NAME',scale=.026,pos=(-.94,0,-.16),text_align=TextNode.ALeft,text_fg=(.48,.60,.65,1),frameColor=(0,0,0,0))
        self.motion_forge_name_entry=DirectEntry(parent=self.motion_forge,scale=.037,pos=(-.79,0,-.17),width=25,numLines=1,frameColor=(.04,.06,.08,.98),text_fg=(.90,.96,1,1),cursorKeys=1,focus=0,command=self._forge_commit_name)
        actions=[
            ('PREVIEW',self._forge_preview,()),('MIRROR',self._forge_mirror,()),('SPEED -',self._forge_speed_delta,(-MOTION_FORGE_SPEED_STEP,)),('SPEED +',self._forge_speed_delta,(MOTION_FORGE_SPEED_STEP,)),
            ('TRIM START',self._forge_trim_start,()),('TRIM END',self._forge_trim_end,()),('RESET',self._forge_reset_edits,()),('DELETE',self._forge_delete_slot,()),
        ]
        for idx,(label,cmd,args) in enumerate(actions):
            row=idx//4; col=idx%4; x=-.79+col*.52; z=-.30-row*.12
            DirectButton(parent=self.motion_forge,text=label,scale=.027,pos=(x,0,z),frameSize=(-3.5,3.5,-.70,.70),frameColor=(.055,.085,.105,.98),text_fg=(.76,.91,.96,1),command=cmd,extraArgs=list(args))
        self.motion_forge_labels['keys']=DirectLabel(parent=self.motion_forge,text='1-9 SELECT    ARROWS BROWSE    ENTER PREVIEW    M MIRROR    F2 CLOSE',scale=.026,pos=(-.94,0,-.53),text_align=TextNode.ALeft,text_fg=(.61,.72,.77,1),frameColor=(0,0,0,0))
        self.motion_forge_labels['note']=DirectLabel(parent=self.motion_forge,text='NON-DESTRUCTIVE EDITS — ORIGINAL CAPTURE REMAINS INTACT',scale=.024,pos=(-.94,0,-.60),text_align=TextNode.ALeft,text_fg=(.80,.62,.98,1),frameColor=(0,0,0,0))
        self.motion_forge.hide()

    def _forge_current(self): return self.melee_slots.get(int(self.motion_forge_slot))

    def _forge_update_ui(self):
        if self.motion_forge is None: return
        slot=int(self.motion_forge_slot); rec=self._forge_current()
        for i,b in enumerate(self.motion_forge_slot_buttons,1):
            selected=i==slot; occupied=i in self.melee_slots
            b['frameColor']=(.16,.30,.36,.98) if selected else ((.07,.13,.16,.96) if occupied else (.035,.045,.055,.92))
            b['text_fg']=(.92,1,1,1) if occupied or selected else (.38,.44,.47,1)
        if not rec:
            self.motion_forge_labels['name']['text']=f'SLOT {slot} — EMPTY'
            self.motion_forge_labels['stats']['text']='Record with RMB, release, then press this number to save the performance.'
            self.motion_forge_labels['edit']['text']='No motion selected.'
            if self.motion_forge_name_entry: self.motion_forge_name_entry.enterText('')
            return
        eff=self._effective_melee_recording(rec); name=str(rec.get('name',f'SWORD MOTION {slot:02d}'))
        raw=float(rec.get('duration',0.0)); samples=len(rec.get('samples',())); speed=float(rec.get('playback_speed',MELEE_REPLAY_SPEED))
        trim_a=float(rec.get('trim_start',0.0)); trim_b=float(rec.get('trim_end',0.0)); effdur=float(eff.get('duration',raw)) if eff else raw
        playdur=effdur/max(.001,speed)
        self.motion_forge_labels['name']['text']=f'SLOT {slot} — {name}'
        self.motion_forge_labels['stats']['text']=f'CAPTURE  {raw:.2f}s    SAMPLES  {samples}    PATH  {float(rec.get("travel",0.0)):.2f}\nACTIVE CLIP  {effdur:.2f}s    PLAYBACK  {playdur:.2f}s'
        self.motion_forge_labels['edit']['text']=f'SPEED  {speed:.2f}x    TRIM  +{trim_a:.2f}s / -{trim_b:.2f}s    MIRROR  {"ON" if rec.get("mirrored") else "OFF"}'
        if self.motion_forge_name_entry and not self.motion_forge_name_entry['focus']: self.motion_forge_name_entry.enterText(name)

    def toggle_motion_forge(self):
        if self.combo_composer_visible:
            self.toggle_combo_composer()
        if self.combat_mode!='melee' and not self.motion_forge_visible:
            self.last_hit='MOTION FORGE REQUIRES MELEE MODE'; self._status(); return
        self.motion_forge_visible=not self.motion_forge_visible
        if self.motion_forge_visible:
            self.motion_forge_mouse_was_captured=bool(self.mouse_captured); self.keys.clear(); self.melee_hold={'left':False,'right':False}
            self._set_mouse_capture(False); self.motion_forge.show(); self.help.hide(); self.help_visible=False
            if self.melee_root is not None: self.melee_root.hide()
            self.cross.hide(); self.status.hide(); self.hint.hide(); self._forge_update_ui()
        else:
            if self.motion_forge_name_entry: self.motion_forge_name_entry['focus']=0
            self.motion_forge.hide(); self.cross.show(); self.status.show(); self.hint.show()
            if self.melee_root is not None: self.melee_root.show()
            if self.motion_forge_mouse_was_captured: self._set_mouse_capture(True)

    def _forge_select_slot(self,slot):
        if self.motion_forge_visible: self.motion_forge_slot=max(1,min(MELEE_SLOT_COUNT,int(slot))); self._forge_update_ui()
    def _forge_select_delta(self,delta):
        if self.motion_forge_visible: self._forge_select_slot(((int(self.motion_forge_slot)-1+int(delta))%MELEE_SLOT_COUNT)+1)
    def _forge_preview(self):
        if not self.motion_forge_visible: return
        if self.motion_forge_name_entry is not None and bool(self.motion_forge_name_entry['focus']): return
        rec=self._forge_current()
        if not rec: return
        slot=int(self.motion_forge_slot); self.motion_forge_visible=False
        if self.motion_forge_name_entry: self.motion_forge_name_entry['focus']=0
        self.motion_forge.hide(); self.cross.show(); self.status.show(); self.hint.show()
        if self.melee_root is not None: self.melee_root.show()
        if self.motion_forge_mouse_was_captured: self._set_mouse_capture(True)
        self._start_recorded_melee_playback(rec,source=f'forge_preview_{slot}')
        self.last_hit=f'FORGE PREVIEW — SLOT {slot}'; self._status()
    def _forge_mirror(self):
        if not self.motion_forge_visible: return
        rec=self._forge_current()
        if rec: rec['mirrored']=not bool(rec.get('mirrored',False)); self._save_melee_slots(); self._forge_update_ui()
    def _forge_speed_delta(self,delta):
        if not self.motion_forge_visible: return
        rec=self._forge_current()
        if rec: rec['playback_speed']=round(max(MOTION_FORGE_MIN_SPEED,min(MOTION_FORGE_MAX_SPEED,float(rec.get('playback_speed',MELEE_REPLAY_SPEED))+float(delta))),2); self._save_melee_slots(); self._forge_update_ui()
    def _forge_trim_start(self):
        if not self.motion_forge_visible: return
        rec=self._forge_current()
        if rec:
            d=float(rec.get('duration',0.0)); e=float(rec.get('trim_end',0.0)); a=float(rec.get('trim_start',0.0)); rec['trim_start']=min(max(0.0,d-e-MOTION_FORGE_MIN_DURATION),a+MOTION_FORGE_TRIM_STEP); self._save_melee_slots(); self._forge_update_ui()
    def _forge_trim_end(self):
        if not self.motion_forge_visible: return
        rec=self._forge_current()
        if rec:
            d=float(rec.get('duration',0.0)); a=float(rec.get('trim_start',0.0)); e=float(rec.get('trim_end',0.0)); rec['trim_end']=min(max(0.0,d-a-MOTION_FORGE_MIN_DURATION),e+MOTION_FORGE_TRIM_STEP); self._save_melee_slots(); self._forge_update_ui()
    def _forge_reset_edits(self):
        if not self.motion_forge_visible: return
        rec=self._forge_current()
        if rec: rec['playback_speed']=MELEE_REPLAY_SPEED; rec['trim_start']=0.0; rec['trim_end']=0.0; rec['mirrored']=False; self._save_melee_slots(); self._forge_update_ui()
    def _forge_delete_slot(self):
        if self.motion_forge_visible and int(self.motion_forge_slot) in self.melee_slots: del self.melee_slots[int(self.motion_forge_slot)]; self._save_melee_slots(); self._forge_update_ui()
    def _forge_commit_name(self,text=None):
        if not self.motion_forge_visible: return
        rec=self._forge_current()
        if rec:
            value=str(text if text is not None else (self.motion_forge_name_entry.get() if self.motion_forge_name_entry else '')).strip() or f'SWORD MOTION {self.motion_forge_slot:02d}'
            rec['name']=value[:32]; self._save_melee_slots(); self._forge_update_ui()

    # ---------- PASS 44 COMBO COMPOSER ----------
    def _build_combo_composer_ui(self):
        self.combo_composer=DirectFrame(frameColor=(.011,.016,.023,.97),frameSize=(-1.08,1.08,-.69,.69),pos=(0,0,0))
        DirectLabel(parent=self.combo_composer,text='COMBO COMPOSER',scale=.058,pos=(-.98,0,.58),text_align=TextNode.ALeft,text_fg=(.76,.70,1,1),frameColor=(0,0,0,0))
        DirectLabel(parent=self.combo_composer,text='CHAIN PLAYER-AUTHORED MOTIONS - GENERATED BRIDGES NEVER DEAL DAMAGE',scale=.025,pos=(-.98,0,.51),text_align=TextNode.ALeft,text_fg=(.48,.61,.68,1),frameColor=(0,0,0,0))
        self.combo_composer_bank_buttons=[]
        for i in range(1,COMBO_SLOT_COUNT+1):
            x=-.88+(i-1)*.22
            b=DirectButton(parent=self.combo_composer,text=f'C{i}',scale=.035,pos=(x,0,.40),frameSize=(-.84,.84,-.62,.62),frameColor=(.06,.085,.11,.96),text_fg=(.82,.90,.94,1),command=self._combo_select_slot,extraArgs=[i])
            self.combo_composer_bank_buttons.append(b)
        self.combo_composer_labels['name']=DirectLabel(parent=self.combo_composer,text='',scale=.042,pos=(-.98,0,.29),text_align=TextNode.ALeft,text_fg=(.94,.98,1,1),frameColor=(0,0,0,0))
        self.combo_composer_labels['sequence']=DirectLabel(parent=self.combo_composer,text='',scale=.035,pos=(-.98,0,.18),text_align=TextNode.ALeft,text_fg=(.70,.93,1,1),frameColor=(0,0,0,0))
        self.combo_composer_labels['stats']=DirectLabel(parent=self.combo_composer,text='',scale=.028,pos=(-.98,0,.075),text_align=TextNode.ALeft,text_fg=(.69,.78,.83,1),frameColor=(0,0,0,0))
        DirectLabel(parent=self.combo_composer,text='ADD SOURCE MOTION',scale=.024,pos=(-.98,0,-.055),text_align=TextNode.ALeft,text_fg=(.50,.62,.67,1),frameColor=(0,0,0,0))
        self.combo_composer_move_buttons=[]
        for i in range(1,MELEE_SLOT_COUNT+1):
            x=-.88+(i-1)*.22
            b=DirectButton(parent=self.combo_composer,text=f'+{i}',scale=.034,pos=(x,0,-.13),frameSize=(-.84,.84,-.62,.62),frameColor=(.05,.10,.12,.96),text_fg=(.72,.91,.97,1),command=self._combo_append_move,extraArgs=[i])
            self.combo_composer_move_buttons.append(b)
        DirectLabel(parent=self.combo_composer,text='NAME',scale=.024,pos=(-.98,0,-.245),text_align=TextNode.ALeft,text_fg=(.50,.62,.67,1),frameColor=(0,0,0,0))
        self.combo_composer_name_entry=DirectEntry(parent=self.combo_composer,scale=.036,pos=(-.82,0,-.255),width=24,numLines=1,frameColor=(.04,.06,.08,.98),text_fg=(.91,.96,1,1),cursorKeys=1,focus=0,command=self._combo_commit_name)
        actions=[('PREVIEW',self._combo_preview),('ARM',self._combo_arm),('REMOVE LAST',self._combo_remove_last),('CLEAR',self._combo_clear)]
        for idx,(label,cmd) in enumerate(actions):
            x=-.77+idx*.51
            DirectButton(parent=self.combo_composer,text=label,scale=.027,pos=(x,0,-.38),frameSize=(-3.7,3.7,-.72,.72),frameColor=(.07,.075,.12,.98),text_fg=(.83,.82,1,1),command=cmd)
        self.combo_composer_labels['keys']=DirectLabel(parent=self.combo_composer,text='[ / ] OR ARROWS SELECT COMBO    1-9 APPEND MOVE    BACKSPACE REMOVE    ENTER PREVIEW',scale=.023,pos=(-.98,0,-.51),text_align=TextNode.ALeft,text_fg=(.62,.71,.76,1),frameColor=(0,0,0,0))
        combo_note = ('GAMEPLAY: X PLAYS ARMED COMBO    C CYCLES ARMED COMBOS    TAB RETURNS HOME'
                      if self._holoverse_embedded else
                      'GAMEPLAY: 0 PLAYS ARMED COMBO    TAB CYCLES ARMED COMBOS')
        self.combo_composer_labels['note']=DirectLabel(parent=self.combo_composer,text=combo_note,scale=.024,pos=(-.98,0,-.59),text_align=TextNode.ALeft,text_fg=(.78,.67,1,1),frameColor=(0,0,0,0))
        self.combo_composer.hide()

    def _combo_current(self): return self.melee_combos.get(int(self.combo_composer_slot))

    def _combo_update_ui(self):
        if self.combo_composer is None: return
        slot=int(self.combo_composer_slot); combo=self._combo_current(); active=int(self.active_combo_slot)==slot
        for i,b in enumerate(self.combo_composer_bank_buttons,1):
            occupied=i in self.melee_combos; selected=i==slot
            if selected: col=(.25,.20,.40,.98)
            elif occupied: col=(.09,.08,.18,.96)
            else: col=(.035,.045,.055,.92)
            b['frameColor']=col; b['text_fg']=(1,.93,1,1) if selected or occupied else (.38,.44,.47,1)
        for i,b in enumerate(self.combo_composer_move_buttons,1):
            valid=i in self.melee_slots; b['frameColor']=(.055,.12,.14,.96) if valid else (.035,.04,.045,.90); b['text_fg']=(.76,.95,1,1) if valid else (.32,.36,.38,1)
        if not combo:
            self.combo_composer_labels['name']['text']=f'COMBO {slot} - EMPTY' + ('    [ARMED]' if active else '')
            self.combo_composer_labels['sequence']['text']='SEQUENCE  -'
            self.combo_composer_labels['stats']['text']='Append at least two existing Motion Forge slots. Maximum six moves.'
            if self.combo_composer_name_entry: self.combo_composer_name_entry.enterText('')
            return
        seq=list(combo.get('sequence',())); compiled=self._compile_melee_combo(combo)
        seq_text='  >  '.join(f'{n}:{self.melee_slots.get(n,{}).get("name",f"MOVE {n}")[:14]}' for n in seq) or '—'
        bridges=len(compiled.get('transition_ranges',())) if compiled else 0; dur=float(compiled.get('duration',0.0)) if compiled else 0.0
        name=str(combo.get('name',f'COMBO {slot:02d}'))
        missing=[n for n in seq if n not in self.melee_slots]
        self.combo_composer_labels['name']['text']=f'COMBO {slot} - {name}' + ('    [ARMED]' if active else '')
        self.combo_composer_labels['sequence']['text']=f'SEQUENCE  {seq_text}'
        self.combo_composer_labels['stats']['text']=(f'MOVES {len(seq)}/{COMBO_MAX_MOVES}    BRIDGES {bridges}    PLAYBACK {dur:.2f}s    DAMAGE BRIDGES 0' if not missing else f'MISSING SOURCE SLOT(S): {", ".join(map(str,missing))}')
        if self.combo_composer_name_entry and not self.combo_composer_name_entry['focus']: self.combo_composer_name_entry.enterText(name)

    def toggle_combo_composer(self):
        if self.combat_mode!='melee' and not self.combo_composer_visible:
            self.last_hit='COMBO COMPOSER REQUIRES MELEE MODE'; self._status(); return
        if self.motion_forge_visible:
            self.toggle_motion_forge()
        self.combo_composer_visible=not self.combo_composer_visible
        if self.combo_composer_visible:
            self.combo_composer_mouse_was_captured=bool(self.mouse_captured); self.keys.clear(); self.melee_hold={'left':False,'right':False}
            self._set_mouse_capture(False); self.combo_composer.show(); self.help.hide(); self.help_visible=False
            if self.melee_root is not None: self.melee_root.hide()
            self.cross.hide(); self.status.hide(); self.hint.hide(); self._combo_update_ui()
        else:
            if self.combo_composer_name_entry: self.combo_composer_name_entry['focus']=0
            self.combo_composer.hide(); self.cross.show(); self.status.show(); self.hint.show()
            if self.melee_root is not None: self.melee_root.show()
            if self.combo_composer_mouse_was_captured: self._set_mouse_capture(True)

    def _combo_select_slot(self,slot):
        if not self.combo_composer_visible: return
        self.combo_composer_slot=max(1,min(COMBO_SLOT_COUNT,int(slot))); self._combo_update_ui()

    def _combo_select_delta(self,delta):
        if self.combo_composer_visible: self._combo_select_slot(((int(self.combo_composer_slot)-1+int(delta))%COMBO_SLOT_COUNT)+1)

    def _combo_append_move(self,move_slot):
        if not self.combo_composer_visible: return
        move_slot=int(move_slot)
        if move_slot not in self.melee_slots:
            self.combo_composer_labels['stats']['text']=f'SOURCE SLOT {move_slot} IS EMPTY — RECORD OR CREATE IT IN MOTION FORGE FIRST'; return
        slot=int(self.combo_composer_slot); combo=self.melee_combos.get(slot)
        if not combo: combo={'name':f'COMBO {slot:02d}','sequence':[]}; self.melee_combos[slot]=combo
        seq=combo.setdefault('sequence',[])
        if len(seq)>=COMBO_MAX_MOVES:
            self.combo_composer_labels['stats']['text']=f'COMBO LIMIT {COMBO_MAX_MOVES} MOVES'; return
        seq.append(move_slot); self._save_melee_slots(); self._combo_update_ui()

    def _combo_remove_last(self):
        if not self.combo_composer_visible: return
        combo=self._combo_current()
        if combo and combo.get('sequence'):
            combo['sequence'].pop()
            if not combo['sequence']: self.melee_combos.pop(int(self.combo_composer_slot),None)
            self._save_melee_slots(); self._combo_update_ui()

    def _combo_clear(self):
        if not self.combo_composer_visible: return
        self.melee_combos.pop(int(self.combo_composer_slot),None); self._save_melee_slots(); self._combo_update_ui()

    def _combo_commit_name(self,text=None):
        if not self.combo_composer_visible: return
        combo=self._combo_current()
        if combo:
            value=str(text if text is not None else (self.combo_composer_name_entry.get() if self.combo_composer_name_entry else '')).strip() or f'COMBO {self.combo_composer_slot:02d}'
            combo['name']=value[:32]; self._save_melee_slots(); self._combo_update_ui()

    def _combo_arm(self):
        if not self.combo_composer_visible: return
        combo=self._combo_current()
        if combo and len(combo.get('sequence',()))>=COMBO_MIN_MOVES and self._compile_melee_combo(combo):
            self.active_combo_slot=int(self.combo_composer_slot); self._save_melee_slots(); self._combo_update_ui()
            self.combo_composer_labels['stats']['text']+=f'    ARMED AS COMBO {self.active_combo_slot}'

    def _combo_preview(self):
        if not self.combo_composer_visible: return
        if self.combo_composer_name_entry is not None and bool(self.combo_composer_name_entry['focus']): return
        slot=int(self.combo_composer_slot)
        if not self._compile_melee_combo(self.melee_combos.get(slot)): return
        self.combo_composer_visible=False
        if self.combo_composer_name_entry: self.combo_composer_name_entry['focus']=0
        self.combo_composer.hide(); self.cross.show(); self.status.show(); self.hint.show()
        if self.melee_root is not None: self.melee_root.show()
        if self.combo_composer_mouse_was_captured: self._set_mouse_capture(True)
        if self._start_combo_playback(slot,source='composer_preview'):
            self.last_hit=f'COMBO PREVIEW — {self.melee_combos[slot].get("name",f"COMBO {slot}")}'; self._status()

    def _play_active_combo(self):
        if self.motion_forge_visible or self.combo_composer_visible or self.combat_mode!='melee': return
        slot=int(self.active_combo_slot)
        if self._start_combo_playback(slot,source='armed_combo'):
            self.last_hit=f'COMBO {slot} — {self.melee_combos[slot].get("name",f"COMBO {slot}")}'; self._status()
        else:
            self.last_hit=f'COMBO {slot} UNAVAILABLE — F3 TO COMPOSE'; self._status()

    def _cycle_active_combo(self):
        if self.combo_composer_visible:
            self._combo_select_delta(1); return
        if self.motion_forge_visible or self.combat_mode!='melee': return
        occupied=[i for i in range(1,COMBO_SLOT_COUNT+1) if i in self.melee_combos and len(self.melee_combos[i].get('sequence',()))>=COMBO_MIN_MOVES]
        if not occupied:
            self.last_hit='NO COMBOS — F3 TO COMPOSE'; self._status(); return
        try: idx=occupied.index(int(self.active_combo_slot)); self.active_combo_slot=occupied[(idx+1)%len(occupied)]
        except ValueError: self.active_combo_slot=occupied[0]
        self._save_melee_slots(); self.last_hit=f'ARMED COMBO {self.active_combo_slot} — {self.melee_combos[self.active_combo_slot].get("name","")}'; self._status()

    # ---------- INPUT ----------
    def _bind(self):
        for key in ('w','a','s','d','shift','control','r'):
            self.accept(key, self._key, [key, True])
            self.accept(key+'-up', self._key, [key, False])
        self.accept('space', self.jump)
        self.accept('m', self.toggle_combat_mode)
        self.accept('mouse1', self._mouse_primary, [True])
        self.accept('mouse1-up', self._mouse_primary, [False])
        self.accept('mouse3', self._mouse_secondary, [True])
        self.accept('mouse3-up', self._mouse_secondary, [False])
        for slot in range(1,MELEE_SLOT_COUNT+1):
            self.accept(str(slot), self._number_key, [slot])
        self.accept('f1', self.toggle_help)
        self.accept('f2', self.toggle_motion_forge)
        self.accept('f3', self.toggle_combo_composer)
        self.accept('0', self._play_active_combo)
        if self._holoverse_embedded:
            self.accept('c', self._cycle_active_combo)
        else:
            self.accept('tab', self._cycle_active_combo)
        self.accept('arrow_left', self._forge_select_delta, [-1])
        self.accept('arrow_right', self._forge_select_delta, [1])
        self.accept('enter', self._forge_preview)
        self.accept('q', self._forge_trim_start)
        self.accept('e', self._forge_trim_end)
        self.accept('-', self._forge_speed_delta, [-MOTION_FORGE_SPEED_STEP])
        self.accept('=', self._forge_speed_delta, [MOTION_FORGE_SPEED_STEP])
        self.accept('backspace', self._forge_reset_edits)
        self.accept('delete', self._forge_delete_slot)
        self.accept('arrow_left', self._combo_select_delta, [-1])
        self.accept('arrow_right', self._combo_select_delta, [1])
        self.accept('enter', self._combo_preview)
        self.accept('backspace', self._combo_remove_last)
        self.accept('delete', self._combo_clear)
        self.accept('f11', self.toggle_fullscreen)
        self.accept('escape', self.toggle_mouse_capture)
        self.accept('window-event', self._window_event)

    def _mouse_fire(self, down):
        self.fire_button_down = bool(down)
        if not down: self.fire_latch = False

    def _mouse_primary(self, down):
        if self.motion_forge_visible or self.combo_composer_visible: return
        if self.combat_mode=='melee':
            self._begin_melee_charge('left') if down else self._finish_melee_charge('left')
        else:
            self._mouse_fire(down)

    def _mouse_secondary(self, down):
        if self.motion_forge_visible or self.combo_composer_visible: return
        if self.combat_mode=='melee':
            self._begin_melee_charge('right') if down else self._finish_melee_charge('right')
        elif down:
            self.cycle_weapon_mode()

    def _key(self, key, down):
        if self.motion_forge_visible or self.combo_composer_visible:
            self.keys.discard(key); return
        if down: self.keys.add(key)
        else: self.keys.discard(key)

    def toggle_help(self):
        if self.motion_forge_visible or self.combo_composer_visible: return
        self.help_visible = not self.help_visible
        self.help.show() if self.help_visible else self.help.hide()

    def _set_mouse_capture(self, enabled):
        self.mouse_captured = bool(enabled)
        if not self.win or not hasattr(self.win, 'requestProperties'):
            return
        props = WindowProperties()
        props.setCursorHidden(enabled)
        props.setMouseMode(WindowProperties.M_confined if enabled else WindowProperties.M_absolute)
        self.win.requestProperties(props)
        if enabled:
            self.mouse_ignore_frames = 2
            self._center_pointer()

    def toggle_mouse_capture(self):
        if self.combo_composer_visible:
            self.toggle_combo_composer(); return
        if self.motion_forge_visible:
            self.toggle_motion_forge(); return
        self._set_mouse_capture(not self.mouse_captured)

    def _window_event(self, win):
        if win is None: return
        props = win.getProperties()
        if not props.getForeground() and self.mouse_captured:
            self._set_mouse_capture(False)

    def _center_pointer(self):
        if not self.win: return
        props = self.win.getProperties()
        if props.getXSize() > 0 and props.getYSize() > 0:
            self.win.movePointer(0, props.getXSize()//2, props.getYSize()//2)

    def _mouse_look(self):
        if self.motion_forge_visible or self.combo_composer_visible: return
        watcher = getattr(self, 'mouseWatcherNode', None)
        if not self.mouse_captured or not self.win or watcher is None or not watcher.hasMouse(): return
        props = self.win.getProperties()
        cx, cy = props.getXSize()//2, props.getYSize()//2
        pointer = self.win.getPointer(0)
        dx, dy = pointer.getX()-cx, pointer.getY()-cy
        if self.mouse_ignore_frames > 0:
            self.mouse_ignore_frames -= 1
            self._center_pointer()
            return
        dx = max(-MAX_MOUSE_PIXEL_DELTA, min(MAX_MOUSE_PIXEL_DELTA, dx))
        dy = max(-MAX_MOUSE_PIXEL_DELTA, min(MAX_MOUSE_PIXEL_DELTA, dy))
        if dx or dy:
            if not (self.combat_mode=='melee' and self._record_melee_delta(dx,dy)):
                self.yaw = (self.yaw - dx * self.mouse_sensitivity) % 360.0
                self.pitch = max(-CAMERA_PITCH_LIMIT, min(CAMERA_PITCH_LIMIT, self.pitch - dy*self.mouse_pitch_sensitivity))
            self._center_pointer()

    def toggle_fullscreen(self):
        # HoloVerse is the sole window authority while embedded.  Anatomic must
        # never resize, fullscreen-toggle, or otherwise replace the host window.
        if self._holoverse_embedded:
            self.last_hit = 'HOLOVERSE OWNS WINDOW MODE'
            self._status()
            return False
        if not self.win:
            return False
        self.fullscreen = not self.fullscreen
        props = WindowProperties()
        props.setFullscreen(self.fullscreen)
        if not self.fullscreen:
            props.setSize(1920,1080)
        self.win.requestProperties(props)
        return True

    # ---------- PLAYER ----------
    def _set_spawn_camera_facing_npc(self):
        """Aim the initial camera at the NPC upper torso using Panda's own lookAt convention."""
        self.current_eye_height = STAND_EYE
        self.camera.setPos(self.player_pos.x, self.player_pos.y, self.player_pos.z + self.current_eye_height)
        target = Vec3(0.0, 0.0, SPAWN_LOOK_TARGET_Z)
        self.camera.lookAt(target)
        hpr = self.camera.getHpr(self.render)
        self.yaw = float(hpr.x) % 360.0
        self.pitch = max(-CAMERA_PITCH_LIMIT, min(CAMERA_PITCH_LIMIT, float(hpr.y)))
        self.camera.setR(0.0)
        forward = self.camera.getQuat(self.render).getForward()
        desired = target - self.camera.getPos(self.render)
        if desired.lengthSquared() > 1e-10:
            desired.normalize()
            self.spawn_facing_dot = float(forward.dot(desired))

    def jump(self):
        # Queue the request briefly so a Space press just before landing still fires.
        self.jump_buffer_timer = JUMP_BUFFER_TIME

    @staticmethod
    def _approach(current, target, max_delta):
        if current < target:
            return min(target, current + max_delta)
        return max(target, current - max_delta)

    @staticmethod
    def _move_towards_planar(current, target, max_delta):
        """Move horizontal velocity toward target without per-axis bias."""
        cur=Vec3(float(current.x),float(current.y),0.0)
        tgt=Vec3(float(target.x),float(target.y),0.0)
        delta=tgt-cur; dist=delta.length(); step=max(0.0,float(max_delta))
        if dist <= step or dist < 1e-9:
            return tgt
        return cur + delta*(step/dist)

    def _resolve_body_collision(self, pos):
        # The NPC can now walk, so collision follows body_root instead of assuming origin.
        npc = self.body_root.getPos(self.render) if getattr(self, 'body_root', None) is not None else Vec3(0,0,0)
        dx, dy = pos.x - npc.x, pos.y - npc.y
        dist2 = dx*dx + dy*dy
        min_d = BODY_COLLISION_RADIUS + PLAYER_RADIUS
        collided = False
        normal = Vec3(0,0,0)
        if dist2 < min_d*min_d:
            d = math.sqrt(max(dist2, 1e-8))
            if d < 1e-4:
                dx, dy, d = 0.0, -1.0, 1.0
            normal = Vec3(dx/d, dy/d, 0.0)
            pos.x = npc.x + normal.x * min_d
            pos.y = npc.y + normal.y * min_d
            collided = True
        return pos, collided, normal

    @staticmethod
    def _movement_basis_for_yaw(yaw_degrees):
        """Return Panda3D-correct horizontal forward/right vectors for camera heading.

        Panda3D uses +Y as forward and positive Heading turns toward -X (left).
        Keeping this conversion in one place prevents WASD from silently using the
        opposite yaw convention and makes movement remain camera-relative in every
        quadrant without changing the camera orientation itself.
        """
        h = math.radians(float(yaw_degrees))
        forward = Vec3(-math.sin(h), math.cos(h), 0.0)
        right = Vec3(math.cos(h), math.sin(h), 0.0)
        return forward, right

    def _update_player(self, dt):
        dt = max(0.0, min(float(dt), 0.05))
        self.jump_buffer_timer = max(0.0, self.jump_buffer_timer - dt)
        if self.on_ground:
            self.coyote_timer = COYOTE_TIME
        else:
            self.coyote_timer = max(0.0, self.coyote_timer - dt)

        self.crouching = 'control' in self.keys and self.on_ground
        target_eye = CROUCH_EYE if self.crouching else STAND_EYE
        self.current_eye_height = self._approach(self.current_eye_height, target_eye, EYE_TRANSITION_SPEED * dt)

        # Movement is camera-heading-relative.  Do not derive this with the usual
        # mathematical positive-angle convention: Panda3D positive Heading turns
        # left.  The Pass 20 signs were mirrored, which made WASD rotate away from
        # the view direction as the player looked around.
        forward, right = self._movement_basis_for_yaw(self.yaw)
        wish = Vec3(0,0,0)
        if 'w' in self.keys: wish += forward
        if 's' in self.keys: wish -= forward
        if 'd' in self.keys: wish += right
        if 'a' in self.keys: wish -= right
        if wish.lengthSquared() > 0:
            wish.normalize()

        speed = CROUCH_SPEED if self.crouching else (SPRINT_SPEED if 'shift' in self.keys else WALK_SPEED)
        has_input = wish.lengthSquared() > 0
        current_planar=Vec3(self.player_vel.x,self.player_vel.y,0.0)
        if self.on_ground:
            target_planar=wish*speed if has_input else Vec3(0,0,0)
            accel=GROUND_DECEL if not has_input else GROUND_ACCEL
            if has_input and current_planar.lengthSquared()>1e-7:
                cur_dir=Vec3(current_planar); cur_dir.normalize()
                alignment=float(cur_dir.dot(wish))
                if alignment < 0.0:
                    accel=GROUND_ACCEL+(GROUND_REVERSE_ACCEL-GROUND_ACCEL)*(-alignment)
            current_planar=self._move_towards_planar(current_planar,target_planar,accel*dt)
        elif has_input:
            # Releasing input in air preserves momentum; input provides bounded correction.
            target_planar=wish*speed; accel=AIR_ACCEL
            if current_planar.lengthSquared()>1e-7:
                cur_dir=Vec3(current_planar); cur_dir.normalize()
                alignment=float(cur_dir.dot(wish))
                if alignment < 0.0:
                    accel=AIR_ACCEL+(AIR_REVERSE_ACCEL-AIR_ACCEL)*(-alignment)
            current_planar=self._move_towards_planar(current_planar,target_planar,accel*dt)
        self.player_vel.x=current_planar.x
        self.player_vel.y=current_planar.y

        if self.jump_buffer_timer > 0.0 and self.coyote_timer > 0.0 and not self.crouching:
            self.player_vel_z = JUMP_SPEED
            self.on_ground = False
            self.coyote_timer = 0.0
            self.jump_buffer_timer = 0.0

        next_pos = self.player_pos + Vec3(self.player_vel.x * dt, self.player_vel.y * dt, 0.0)
        limit = WORLD_HALF - PLAYER_RADIUS
        clamped_x = max(-limit, min(limit, next_pos.x))
        clamped_y = max(-limit, min(limit, next_pos.y))
        if clamped_x != next_pos.x: self.player_vel.x = 0.0
        if clamped_y != next_pos.y: self.player_vel.y = 0.0
        next_pos.x, next_pos.y = clamped_x, clamped_y
        next_pos, collided, normal = self._resolve_body_collision(next_pos)
        if collided:
            inward = self.player_vel.x * normal.x + self.player_vel.y * normal.y
            if inward < 0.0:
                self.player_vel.x -= normal.x * inward
                self.player_vel.y -= normal.y * inward
        self.player_pos.x = next_pos.x
        self.player_pos.y = next_pos.y

        if not self.on_ground:
            self.player_vel_z -= GRAVITY * dt
            self.player_pos.z += self.player_vel_z * dt
            if self.player_pos.z <= 0:
                impact_speed=max(0.0,-float(self.player_vel_z))
                self.player_pos.z = 0
                self.player_vel_z = 0
                self.on_ground = True
                self.coyote_timer = COYOTE_TIME
                self.landing_camera_offset=-min(LANDING_DIP_MAX,impact_speed*LANDING_DIP_SCALE)
        self.landing_camera_offset=self._approach(self.landing_camera_offset,0.0,LANDING_RECOVER_SPEED*dt)

    def _update_camera(self):
        self.camera.setPos(self.player_pos.x, self.player_pos.y, self.player_pos.z + self.current_eye_height + self.landing_camera_offset)
        self.camera.setHpr(self.yaw, self.pitch, 0)

    # ---------- DAMAGE / PROJECTILES ----------
    def _restore_pristine_body(self):
        for limb in list(self.detached_limbs):
            self._reattach_detached_limb(limb)
        self.detached_limbs.clear(); self.detached_joint_names.clear(); self.severed_bone_names.clear()
        for f in self.fragments:
            self._release_fragment_node(f)
        self.fragments.clear()
        for s in self.shots:
            s.node.removeNode()
        self.shots.clear()
        self.wounds.clear()
        for particle in list(self.wound_ascii): self._release_wound_ascii_node(particle)
        self.wound_ascii.clear()
        self.wound_color_bindings.clear()
        self.wound_visual_clock=0.0
        self.rng.setstate(self.pristine_rng_state)
        self.weapon_recoil = 0.0
        self.fire_cooldown = 0.0
        self.fire_button_down = False
        self.fire_latch = False
        for i, n in enumerate(self.glyph_nodes):
            n.show()
        for i, n in enumerate(self.organ_nodes):
            n.show()
            self._apply_glyph_color(n, self.organ_original_colors[i])
        if getattr(self, 'neural_nodes', None):
            for n in self.neural_nodes:
                n.show(); self._apply_glyph_color(n, NEURAL_RED)
        for i in range(len(self.live)):
            self.live[i] = True
        self._rebuild_all_glyph_batches()
        self.rewinding = False
        if self.npc_damage_origin is not None and getattr(self,'body_root',None) is not None:
            pos,h=self.npc_damage_origin; self.body_root.setPos(self.render,pos); self.body_root.setH(self.render,h)
        self.npc_damage_origin=None
        self.npc_stagger_velocity=Vec3(0,0,0); self.npc_defense_timer=0.0
        self.impact_body_p=self.impact_body_r=self.impact_body_vp=self.impact_body_vr=0.0
        self.impact_head_h=self.impact_head_p=self.impact_head_r=0.0
        self.impact_head_vh=self.impact_head_vp=self.impact_head_vr=0.0
        self.last_hit = 'MEMORY RESTORED'
        self._status()

    @staticmethod
    def _smooth01(value):
        value = max(0.0, min(1.0, value))
        return value * value * (3.0 - 2.0 * value)

    def _wound_center_world(self, wound):
        if wound.bind_name in self.rig_joints:
            return self.render.getRelativePoint(self.rig_joints[wound.bind_name], wound.center)
        return self.render.getRelativePoint(self.body_root, wound.center)

    def _wound_tint(self, point_world):
        strength=0.0; tint=Vec4(MEMORY_WOUND_RED)
        p=_v3(point_world)
        for wound in self.wounds:
            if wound.age<=0.0: continue
            center=self._wound_center_world(wound); dist=(p-center).length()
            if dist>=wound.radius: continue
            if dist<=WOUND_CORE_RADIUS:
                local=1.0; radial=1.0
            else:
                span=max(1e-6,wound.radius-WOUND_CORE_RADIUS)
                local=1.0-((dist-WOUND_CORE_RADIUS)/span); local=self._smooth01(local); radial=local
            candidate=local*wound.strength
            if candidate>=strength:
                strength=candidate
                tint=Vec4(wound.outer_color.x+(wound.core_color.x-wound.outer_color.x)*radial,
                          wound.outer_color.y+(wound.core_color.y-wound.outer_color.y)*radial,
                          wound.outer_color.z+(wound.core_color.z-wound.outer_color.z)*radial,1.0)
        return tint,max(0.0,min(1.0,strength))

    def _wound_influence(self, point_world):
        return self._wound_tint(point_world)[1]

    def _refresh_wound_colors(self, binds=None):
        # Pass 32 preserves Pass 31 Holo Gesture Fists: wound bloom/rewind is a color-only operation. Geometry is rebuilt only
        # when a glyph actually leaves/rejoins the body or when LOD changes.
        if binds is None:
            binds = self.wound_color_bindings or self._wound_affected_bindings()
        for bind in tuple(binds):
            self._update_glyph_batch_colors(bind)
        for i, node in enumerate(self.organ_nodes):
            tint,influence = self._wound_tint(node.getPos(self.render))
            base = self.organ_original_colors[i]
            if influence <= 0.0001: self._apply_glyph_color(node, base)
            else:
                self._apply_glyph_color(node, Vec4(base.x+(tint.x-base.x)*influence,
                                                   base.y+(tint.y-base.y)*influence,
                                                   base.z+(tint.z-base.z)*influence,1.0))

    def _acquire_fragment_node(self, glyph):
        pool=self.fragment_pool.setdefault(glyph,[])
        if pool:
            node=pool.pop(); node.show(); self.perf_counters['fragment_pool_hits'] += 1
            return node
        holder=self.render.attachNewNode('fragment_pool_'+str(glyph))
        self.glyph_proto[glyph].instanceTo(holder)
        holder.setScale(.032); holder.setBillboardPointEye(); holder.setLightOff()
        self.perf_counters['fragment_pool_misses'] += 1
        return holder

    def _release_fragment_node(self, fragment):
        node=fragment.node
        node.hide(); node.setPos(0,0,-1000); node.setHpr(0,0,0)
        self.fragment_pool.setdefault(fragment.glyph,[]).append(node)

    def _sample_fragment_memory(self, fragment, force=False):
        fragment.sample_clock += MEMORY_SAMPLE_DT if force else 0.0
        if force or fragment.sample_clock >= MEMORY_SAMPLE_DT:
            fragment.samples.append((fragment.age, (fragment.pos.x, fragment.pos.y, fragment.pos.z), fragment.roll))
            fragment.sample_clock = 0.0

    @staticmethod
    def _fragment_memory_pose(fragment, age):
        samples = fragment.samples
        if not samples:
            return _v3(fragment.pos), fragment.roll
        if age <= samples[0][0]:
            t, pos, roll = samples[0]
            return Vec3(*pos), roll
        if age >= samples[-1][0]:
            t, pos, roll = samples[-1]
            return Vec3(*pos), roll
        lo, hi = 0, len(samples) - 1
        while lo + 1 < hi:
            mid = (lo + hi) // 2
            if samples[mid][0] <= age:
                lo = mid
            else:
                hi = mid
        ta, pa, ra = samples[lo]
        tb, pb, rb = samples[hi]
        alpha = 0.0 if tb <= ta else (age - ta) / (tb - ta)
        pos = Vec3(*pa) + (Vec3(*pb) - Vec3(*pa)) * alpha
        roll = ra + (rb - ra) * alpha
        return pos, roll

    def _rewind_memory(self, dt):
        amount = dt * REWIND_SPEED
        self.rewinding = True
        self._rewind_detached_limbs(amount)
        self._rewind_wound_ascii(amount)
        self.wound_visual_clock += dt
        for wound in self.wounds:
            wound.age = max(0.0, wound.age - amount)
        self.wounds = [w for w in self.wounds if w.age > 0.0]

        kept = []
        restored_bindings=set()
        for fragment in self.fragments:
            fragment.age = max(0.0, fragment.age - amount)
            if fragment.age <= 0.0:
                idx = fragment.index
                self.live[idx] = True
                self.glyph_nodes[idx].show()
                restored_bindings.add(self.body_bindings[idx])
                self._release_fragment_node(fragment)
                continue
            pos, roll = self._fragment_memory_pose(fragment, fragment.age)
            fragment.pos = _v3(pos)
            fragment.roll = roll
            fragment.node.setPos(pos)
            fragment.node.setR(roll)
            kept.append(fragment)
        self.fragments = kept

        # Topology changes are batched once after all fragments restored this frame.
        for bind in restored_bindings:
            self._rebuild_glyph_batch(bind)
            self.wound_color_bindings.add(bind)
        # Color fading runs at 30 Hz and modifies the existing vertex colors in place.
        if restored_bindings or self.wound_visual_clock >= WOUND_VISUAL_UPDATE_DT or not self.wounds:
            self._refresh_wound_colors()
            self.wound_visual_clock = 0.0
        if not self.fragments and not self.wounds and not self.detached_limbs:
            self._restore_pristine_body()


    def _octa(self, name, color, scale=.045):
        key=(round(float(scale),5), tuple(round(float(v),4) for v in color))
        proto=self.projectile_proto.get(key)
        if proto is None:
            pts=[(0,0,1),(1,0,0),(0,1,0),(-1,0,0),(0,-1,0),(0,0,-1)]
            tris=[(0,1,2),(0,2,3),(0,3,4),(0,4,1),(5,2,1),(5,3,2),(5,4,3),(5,1,4)]
            fmt=GeomVertexFormat.getV3n3(); vd=GeomVertexData('projectile_proto',fmt,Geom.UHStatic)
            vw=GeomVertexWriter(vd,'vertex'); nw=GeomVertexWriter(vd,'normal'); prim=GeomTriangles(Geom.UHStatic)
            for tri in tris:
                a,b,c=[Vec3(*pts[i]) for i in tri]; n=(b-a).cross(c-a); n.normalize(); base=vw.getWriteRow()
                for v in (a,b,c): vw.addData3f(v*scale); nw.addData3f(n)
                prim.addVertices(base,base+1,base+2)
            g=Geom(vd); g.addPrimitive(prim); gn=GeomNode('projectile_proto'); gn.addGeom(g)
            proto=NodePath(gn); proto.setColor(*color); proto.setLightOff(); self.projectile_proto[key]=proto
            self.perf_counters['projectile_builds']+=1
        holder=self.render.attachNewNode(name); proto.instanceTo(holder); return holder

    def _cache_hit_target(self, world_point, hit_index):
        bind=self.body_bindings[hit_index] if hit_index is not None and hit_index < len(self.body_bindings) else 'body_root'
        parent=self.rig_joints.get(bind, self.body_root)
        return bind, _v3(parent.getRelativePoint(self.render, world_point))

    def _cached_hit_world(self, shot):
        if shot.hit_index is None or shot.hit_local is None: return None
        parent=self.rig_joints.get(shot.hit_bind, self.body_root)
        return _v3(self.render.getRelativePoint(parent, shot.hit_local))

    def fire_side(self, side='rifle'):
        if self.combat_mode != 'rifle': return
        if 'r' in self.keys:
            return
        if not self.mouse_captured and not (ARGS.smoke_test or ARGS.test_shot or ARGS.combat_smoke):
            self._set_mouse_capture(True)
            return
        spec = self.weapon_modes[self.current_weapon_mode]
        cam_start = self.camera.getPos(self.render)
        cam_quat = self.camera.getQuat(self.render)
        cam_forward = cam_quat.getForward(); cam_right = cam_quat.getRight(); cam_up = cam_quat.getUp()
        cam_forward.normalize(); cam_right.normalize(); cam_up.normalize()
        start = self.weapon_muzzle.getPos(self.render)
        fired = 0
        for pellet_index in range(spec['pellets']):
            spread_deg = 0.0 if spec['pellets'] == 1 and pellet_index == 0 else self.rng.uniform(-spec['spread'], spec['spread'])
            spread_deg_y = 0.0 if spec['pellets'] == 1 and pellet_index == 0 else self.rng.uniform(-spec['spread'], spec['spread'])
            spread_x = math.tan(math.radians(spread_deg)); spread_y = math.tan(math.radians(spread_deg_y))
            direction = _v3(cam_forward + cam_right * spread_x + cam_up * spread_y)
            if direction.lengthSquared() < 1e-8:
                direction = _v3(cam_forward)
            direction.normalize()
            far = cam_start + direction * 96.0
            hit_threshold=.08 if self.current_weapon_mode == 'SNIPER' else .10
            hit = self._find_shot_hit(cam_start, far, hit_threshold)
            target = hit[0] if hit is not None else (cam_start + direction * 44.0)
            hit_index = hit[1] if hit is not None else None
            hit_bind, hit_local = self._cache_hit_target(target, hit_index) if hit_index is not None else ('body_root', None)
            shot_dir = target - start
            if shot_dir.lengthSquared() < 1e-8:
                shot_dir = _v3(direction)
            shot_dir.normalize()
            node = self._octa(f'{self.current_weapon_mode.lower()}_projectile_{pellet_index}', spec['color'], spec['scale'])
            node.setPos(start)
            self.shots.append(Shot(node, start, shot_dir * spec['speed'], side, radius=spec['radius'], count=spec['count'], life=spec['life'],
                                   mode=self.current_weapon_mode, hit_index=hit_index, hit_bind=hit_bind, hit_local=hit_local, hit_threshold=hit_threshold))
            fired += 1
        self._play_weapon_sfx('left_fire')
        self.weapon_recoil = max(self.weapon_recoil, spec['recoil'])
        self.fire_cooldown = spec['cooldown']
        self.last_hit = f'RIFLE {spec["display"]} FIRED x{fired}'

    def _update_weapon_fire(self, dt):
        if self.combat_mode != 'rifle': return
        self.fire_cooldown = max(0.0, self.fire_cooldown - dt)
        if not self.fire_button_down:
            return
        spec = self.weapon_modes[self.current_weapon_mode]
        if spec['label'] == 'AUTO':
            if self.fire_cooldown <= 0.0:
                self.fire_side('rifle')
        else:
            if not self.fire_latch and self.fire_cooldown <= 0.0:
                self.fire_side('rifle')
                self.fire_latch = True

    @staticmethod
    def _point_segment_distance(p, a, b):
        ab = b-a
        denom = ab.lengthSquared()
        if denom <= 1e-10: return (p-a).length()
        t = max(0.0, min(1.0, (p-a).dot(ab)/denom))
        return (p-(a+ab*t)).length()

    def _current_glyph_world_pos(self, index):
        return _v3(self.glyph_nodes[index].getPos(self.render))

    def _find_shot_hit(self, a, b, threshold=.075):
        best = None
        self.perf_counters['shot_queries'] += 1
        ab = b - a
        denom = max(ab.lengthSquared(), 1e-10)
        # Pass 28 broad phase: reject whole articulated body branches using a
        # conservative joint-local bounding sphere before touching individual glyphs.
        candidates=[]
        for bind,(local_center,radius) in self.binding_bounds.items():
            self.perf_counters['shot_binding_checks'] += 1
            parent=self._glyph_parent(bind)
            center=_v3(self.render.getRelativePoint(parent,local_center))
            if self._point_segment_distance(center,a,b) <= radius+threshold:
                candidates.extend(self.binding_members.get(bind,()))
        self.perf_counters['shot_query_candidates'] += len(candidates)
        for i in candidates:
            if not self.live[i]:
                continue
            self.perf_counters['shot_query_checks'] += 1
            p = self._current_glyph_world_pos(i)
            t = max(0.0, min(1.0, (p-a).dot(ab) / denom))
            nearest = a + ab * t
            d = (p-nearest).length()
            if d <= threshold and (best is None or t < best[0] or (abs(t-best[0]) < 1e-6 and d < best[1])):
                best = (t, d, p, i)
        return (best[2], best[3]) if best else None

    def _impact_region(self, hit_index):
        if hit_index is None: return 'body'
        bind=self.body_bindings[hit_index] if hit_index < len(self.body_bindings) else ''
        region=str(self.surface[hit_index].get('region','')) if hit_index < len(self.surface) else ''
        return 'head' if bind in ('head_base','neck') or 'head' in bind or region == 'head' else 'body'

    def _apply_impact_reaction(self, hit_index, incoming_world, mode, force_scale=1.0):
        if not self.rig_joints: return
        d=_v3(incoming_world)
        if d.lengthSquared() < 1e-8: d=Vec3(0,1,0)
        d.normalize(); local=self.body_root.getRelativeVector(self.render,d)
        force={'AUTO':0.72,'SHOTGUN':1.55,'SNIPER':1.95,'MELEE':1.08,'MELEE_CHARGED':1.82,'SWORD':1.58*SWORD_IMPACT_MULTIPLIER}.get(str(mode),1.0)*max(.20,min(2.0,float(force_scale)))
        head=self._impact_region(hit_index)=='head'
        # Body recoil is deliberately bounded; shotgun pellets can accumulate into a broad shove.
        self.impact_body_vp += max(-35.0,min(35.0, local.y * 20.0 * force))
        self.impact_body_vr += max(-28.0,min(28.0, -local.x * 18.0 * force))
        self.impact_body_p=max(-13.0,min(13.0,self.impact_body_p)); self.impact_body_r=max(-10.0,min(10.0,self.impact_body_r))
        if head:
            hm=2.6 if mode=='SNIPER' else (2.05 if mode=='SHOTGUN' else (2.25 if str(mode).startswith('MELEE') else (2.15 if str(mode)=='SWORD' else 1.55)))
            self.impact_head_vp += max(-120.0,min(120.0, local.y * 27.0 * force * hm))
            self.impact_head_vh += max(-105.0,min(105.0, -local.x * 24.0 * force * hm))
            self.impact_head_vr += max(-90.0,min(90.0, -local.x * 18.0 * force * hm))
        # Hits now move the whole NPC instead of leaving a wounded statue. Translation is
        # horizontal; head/torso springs above provide the vertical/angular knockback.
        shove=_v3(d); shove.z=0.0
        if shove.lengthSquared()>1e-8:
            shove.normalize()
            shove_scale={'AUTO':.18,'SHOTGUN':.54,'SNIPER':.72,'MELEE':.64,'MELEE_CHARGED':1.22,'SWORD':.88*SWORD_IMPACT_MULTIPLIER}.get(str(mode),.24)*max(.20,min(2.0,float(force_scale)))
            self.npc_stagger_velocity += shove*shove_scale
            if self.npc_stagger_velocity.length()>NPC_STAGGER_MAX_SPEED:
                self.npc_stagger_velocity.normalize(); self.npc_stagger_velocity*=NPC_STAGGER_MAX_SPEED
            self.npc_defense_timer=max(self.npc_defense_timer,NPC_DEFENSE_TIME*(1.0 if str(mode)=='AUTO' else 1.25))

    @staticmethod
    def _spring_axis(x,v,dt,k=58.0,damping=13.5):
        v += (-k*x-damping*v)*dt; x += v*dt; return x,v

    def _update_impact_reactions(self, dt):
        self.impact_body_p,self.impact_body_vp=self._spring_axis(self.impact_body_p,self.impact_body_vp,dt,48.0,12.5)
        self.impact_body_r,self.impact_body_vr=self._spring_axis(self.impact_body_r,self.impact_body_vr,dt,52.0,13.0)
        self.impact_head_h,self.impact_head_vh=self._spring_axis(self.impact_head_h,self.impact_head_vh,dt,70.0,14.5)
        self.impact_head_p,self.impact_head_vp=self._spring_axis(self.impact_head_p,self.impact_head_vp,dt,70.0,14.5)
        self.impact_head_r,self.impact_head_vr=self._spring_axis(self.impact_head_r,self.impact_head_vr,dt,74.0,15.0)
        if getattr(self,'body_root',None) is not None:
            self.body_root.setP(max(-13.0,min(13.0,self.impact_body_p)))
            self.body_root.setR(max(-10.0,min(10.0,self.impact_body_r)))

    def _damage_candidate_indices(self, world_point):
        """Return only rig branches whose world-space bounds can overlap BREAK_RADIUS."""
        point=_v3(world_point); candidates=[]
        for bind,(local_center,radius) in self.binding_bounds.items():
            self.perf_counters['damage_binding_checks'] += 1
            parent=self._glyph_parent(bind)
            world_center=_v3(self.render.getRelativePoint(parent, local_center))
            if (world_center-point).length() <= radius + BREAK_RADIUS + BODY_GLYPH_SCALE:
                candidates.extend(self.binding_members.get(bind,()))
        return candidates

    def damage_at(self, world_point, radius=WOUND_RADIUS, count=30, hit_index=None, wound_outer=None, wound_core=None, impulse_scale=1.0, incoming_world=None, mode='AUTO'):
        world_point = _v3(world_point)
        if self.npc_damage_origin is None and getattr(self,'body_root',None) is not None and not self.wounds and not self.fragments:
            self.npc_damage_origin=(Vec3(self.body_root.getPos(self.render)), float(self.body_root.getH(self.render)))
        # A recently hit NPC braces. Follow-up hits still hurt, but dislodge fewer glyphs;
        # this is a real defensive state rather than a cosmetic pose.
        if self.npc_defense_timer > 0.0:
            count=max(1,int(round(float(count)*0.72)))
            radius=float(radius)*0.92
        candidates = []
        candidate_indices=self._damage_candidate_indices(world_point)
        # A malformed/empty bounds table must never make damage disappear. This fallback is
        # defensive only; the normal path touches a few articulated branches, not 2,200 glyphs.
        if not candidate_indices:
            candidate_indices=range(len(self.surface))
        seen=set()
        for i in candidate_indices:
            if i in seen or not self.live[i]: continue
            seen.add(i)
            self.perf_counters['damage_checks'] += 1
            item=self.surface[i]; p_world=self._current_glyph_world_pos(i)
            dist=(p_world-world_point).length()
            if dist <= BREAK_RADIUS: candidates.append((dist,i,p_world,item))
        candidates.sort(key=lambda x: x[0])
        chosen = candidates[:count]
        if hit_index is None and chosen:
            hit_index = chosen[0][1]
        bind_name = self.body_bindings[hit_index] if hit_index is not None and hit_index < len(self.body_bindings) else 'body_root'
        if bind_name in self.rig_joints:
            center_local = self.rig_joints[bind_name].getRelativePoint(self.render, world_point)
        else:
            bind_name = 'body_root'
            center_local = self.body_root.getRelativePoint(self.render, world_point)
        wound=Wound(center_local, radius, bind_name, outer_color=wound_outer, core_color=wound_core, mode=mode)
        self.wounds.append(wound)
        self.wound_color_bindings.update(self._wound_affected_bindings())
        if str(mode).upper() in ('MELEE','MELEE_CHARGED','SWORD'):
            self._spawn_wound_ascii(wound, 7 if str(mode).upper()=='SWORD' else 4, burst=True)
        dirty_bindings=set()
        for dist, i, worldp, item in chosen:
            self.live[i] = False
            self.glyph_nodes[i].hide()
            dirty_bindings.add(self.body_bindings[i])
            holder = self._acquire_fragment_node(item['g'])
            # Directly impacted ASCII matter is solid wound-red, even after it leaves the body.
            self._apply_glyph_color(holder, wound_core or MEMORY_WOUND_RED)
            holder.setPos(worldp)
            out = worldp - world_point
            if out.length() < .02:
                out = Vec3(self.rng.uniform(-1,1), self.rng.uniform(-1,1), self.rng.uniform(.2,1))
            out.normalize()
            push=_v3(incoming_world) if incoming_world is not None else out
            if push.lengthSquared()<1e-8: push=out
            push.normalize()
            vel = (out * self.rng.uniform(1.0,3.0) + push*self.rng.uniform(.8,2.0) + Vec3(
                self.rng.uniform(-.45,.45), self.rng.uniform(-.45,.45), self.rng.uniform(.55,1.8))) * float(impulse_scale)
            fragment = Fragment(i, item['g'], holder, worldp, vel, self.rng.uniform(-280,280))
            self.fragments.append(fragment)
        # Remove all detached glyphs from their branch batches in one rebuild per branch.
        for bind in dirty_bindings:
            self._rebuild_glyph_batch(bind)
        self.wound_color_bindings.update(dirty_bindings)
        self.wound_visual_clock = WOUND_VISUAL_UPDATE_DT
        self._refresh_wound_colors()
        self.wound_visual_clock = 0.0
        self.last_hit = f'WOUND {len(chosen)} GLYPHS'
        self._status()

    def _update_shots(self, dt):
        kept=[]
        for sh in self.shots:
            old=_v3(sh.pos); sh.pos += sh.vel*dt; sh.life-=dt; sh.node.setPos(sh.pos)
            target=self._cached_hit_world(sh)
            if target is not None and self._point_segment_distance(target,old,sh.pos) <= max(sh.hit_threshold, sh.vel.length()*dt*.62):
                self._play_weapon_sfx('left_impact')
                self.damage_at(target, sh.radius, sh.count, hit_index=sh.hit_index, incoming_world=sh.vel, mode=sh.mode)
                self._apply_impact_reaction(sh.hit_index, sh.vel, sh.mode); sh.node.removeNode()
            elif sh.life<=0 or abs(sh.pos.x)>WORLD_HALF or abs(sh.pos.y)>WORLD_HALF or sh.pos.z<0 or sh.pos.z>20:
                sh.node.removeNode()
            else: kept.append(sh)
        self.shots=kept

    def _update_fragments(self, dt):
        kept = []
        for f in self.fragments:
            f.age += dt
            f.sample_clock += dt
            if not f.settled:
                f.vel.z -= 7.4 * dt
                f.pos += f.vel * dt
                if f.pos.z < .025:
                    f.pos.z = .025
                    f.vel.z = abs(f.vel.z) * .31
                    f.vel.x *= .76
                    f.vel.y *= .76
                if f.pos.x < -WORLD_HALF or f.pos.x > WORLD_HALF:
                    f.pos.x = max(-WORLD_HALF, min(WORLD_HALF, f.pos.x))
                    f.vel.x *= -.36
                if f.pos.y < -WORLD_HALF or f.pos.y > WORLD_HALF:
                    f.pos.y = max(-WORLD_HALF, min(WORLD_HALF, f.pos.y))
                    f.vel.y *= -.36
                f.roll = (f.roll + f.roll_v * dt) % 360
                if f.pos.z <= .026 and f.vel.lengthSquared() < .035:
                    f.vel = Vec3(0,0,0)
                    f.settled = True
                    self._sample_fragment_memory(f, force=True)
            if not f.settled:
                f.node.setPos(f.pos); f.node.setR(f.roll)
            if not f.settled and f.sample_clock >= MEMORY_SAMPLE_DT:
                f.samples.append((f.age, (f.pos.x, f.pos.y, f.pos.z), f.roll))
                f.sample_clock = 0.0
            kept.append(f)
        self.fragments = kept

    def _acquire_wound_ascii_node(self, glyph):
        pool=self.wound_ascii_pool.setdefault(glyph,[])
        if pool:
            node=pool.pop(); node.show(); return node
        node=self.render.attachNewNode('wound_ascii_'+glyph)
        self.glyph_proto[glyph].instanceTo(node); node.setScale(.030); node.setBillboardPointEye(); node.setLightOff()
        self._apply_glyph_color(node,MELEE_CORE_RED)
        return node

    def _release_wound_ascii_node(self, particle):
        particle.node.hide(); particle.node.setPos(0,0,-1000); particle.node.setHpr(0,0,0)
        self.wound_ascii_pool.setdefault(particle.glyph,[]).append(particle.node)

    def _spawn_wound_ascii(self, wound, count=1, burst=False):
        if len(self.wound_ascii)>=WOUND_ASCII_MAX or wound.age>WOUND_ASCII_EMIT_TIME: return
        center=_v3(self._wound_center_world(wound)); body_center=_v3(self.body_root.getPos(self.render))+Vec3(0,0,1.15)
        outward=center-body_center; outward.z*=.30
        if outward.lengthSquared()<1e-8: outward=Vec3(0,-1,0)
        outward.normalize()
        for _ in range(min(int(count),WOUND_ASCII_MAX-len(self.wound_ascii))):
            glyph=self.rng.choice(WOUND_ASCII_GLYPHS); node=self._acquire_wound_ascii_node(glyph)
            jitter=Vec3(self.rng.uniform(-.025,.025),self.rng.uniform(-.025,.025),self.rng.uniform(-.025,.025))
            pos=center+jitter; speed=self.rng.uniform(.30,.72) if burst else self.rng.uniform(.16,.42)
            vel=outward*speed+Vec3(self.rng.uniform(-.20,.20),self.rng.uniform(-.16,.16),self.rng.uniform(.02,.38 if burst else .18))
            node.setPos(pos); node.setR(self.rng.uniform(-180,180)); self._apply_glyph_color(node,MELEE_CORE_RED)
            self.wound_ascii.append(WoundASCII(glyph,node,pos,vel,self.rng.uniform(-260,260)))

    @staticmethod
    def _wound_ascii_memory_pose(particle, age):
        samples=particle.samples
        if not samples: return _v3(particle.origin),0.0
        if age<=samples[0][0]: return Vec3(*samples[0][1]),samples[0][2]
        if age>=samples[-1][0]: return Vec3(*samples[-1][1]),samples[-1][2]
        lo,hi=0,len(samples)-1
        while lo+1<hi:
            mid=(lo+hi)//2
            if samples[mid][0]<=age: lo=mid
            else: hi=mid
        ta,pa,ra=samples[lo]; tb,pb,rb=samples[hi]; u=0.0 if tb<=ta else (age-ta)/(tb-ta)
        return Vec3(*pa)+(Vec3(*pb)-Vec3(*pa))*u, ra+(rb-ra)*u

    def _update_wound_ascii(self, dt):
        kept=[]; dt=max(0.0,min(.05,float(dt)))
        for p in self.wound_ascii:
            p.age+=dt; p.sample_clock+=dt
            if not p.settled:
                p.vel.z-=WOUND_ASCII_GRAVITY*dt; p.pos+=p.vel*dt
                if p.pos.z<.025:
                    p.pos.z=.025
                    if abs(p.vel.z)>.28: p.vel.z=abs(p.vel.z)*.20
                    else: p.vel.z=0.0
                    p.vel.x*=.72; p.vel.y*=.72
                    if p.vel.lengthSquared()<.020: p.settled=True
                p.roll=(p.roll+p.roll_v*dt)%360.0; p.node.setPos(p.pos); p.node.setR(p.roll)
            if p.sample_clock>=MEMORY_SAMPLE_DT:
                p.samples.append((p.age,(p.pos.x,p.pos.y,p.pos.z),p.roll)); p.sample_clock=0.0
            if p.age>=p.life:
                self._release_wound_ascii_node(p)
            else: kept.append(p)
        self.wound_ascii=kept

    def _rewind_wound_ascii(self, amount):
        kept=[]
        for p in self.wound_ascii:
            p.age=max(0.0,p.age-amount)
            if p.age<=0.0:
                self._release_wound_ascii_node(p); continue
            pos,roll=self._wound_ascii_memory_pose(p,p.age); p.pos=_v3(pos); p.roll=roll; p.node.setPos(p.pos); p.node.setR(p.roll); kept.append(p)
        self.wound_ascii=kept

    def _advance_wound_memory(self, dt):
        changing=False
        self.wound_visual_clock += dt
        for wound in self.wounds:
            before=wound.strength; wound.age += dt
            if wound.mode in ('MELEE','MELEE_CHARGED','SWORD') and wound.age<=WOUND_ASCII_EMIT_TIME:
                rate=WOUND_ASCII_SWORD_RATE if wound.mode=='SWORD' else WOUND_ASCII_MELEE_RATE
                wound.spill_accum += dt*rate
                emit=int(wound.spill_accum)
                if emit>0:
                    wound.spill_accum-=emit; self._spawn_wound_ascii(wound,emit,burst=False)
            if wound.strength < 1.0 or before < 1.0: changing=True
        self._update_wound_ascii(dt)
        if changing and self.wound_visual_clock >= WOUND_VISUAL_UPDATE_DT:
            self._refresh_wound_colors()
            self.wound_visual_clock = 0.0



    def _update_npc_stagger_and_defense(self, dt):
        """Apply physical-looking root stagger and a short defensive recovery without freezing the NPC."""
        dt=max(0.0,min(.05,float(dt)))
        if getattr(self,'body_root',None) is None: return
        root=self.body_root.getPos(self.render)
        if self.npc_stagger_velocity.lengthSquared()>1e-6:
            root += self.npc_stagger_velocity*dt
            limit=WORLD_HALF-BODY_COLLISION_RADIUS
            root.x=max(-limit,min(limit,root.x)); root.y=max(-limit,min(limit,root.y))
            self.body_root.setPos(self.render,root)
            decay=max(0.0,1.0-NPC_STAGGER_DRAG*dt); self.npc_stagger_velocity*=decay
            if self.npc_stagger_velocity.length()<.025: self.npc_stagger_velocity=Vec3(0,0,0)
        self.npc_defense_timer=max(0.0,self.npc_defense_timer-dt)
        if self.npc_defense_timer>0.0 and self.rig_joints:
            blend=min(1.0,self.npc_defense_timer/NPC_DEFENSE_TIME)
            # Small lateral recovery step keeps the defender from reading like a stationary target.
            # It is bounded and fades with the brace timer, so walking authority resumes cleanly.
            if self.npc_stagger_velocity.lengthSquared()<0.20:
                side_vec=self.body_root.getRelativeVector(self.render,Vec3(self.npc_defense_side,0,0)); side_vec.z=0
                if side_vec.lengthSquared()>1e-8:
                    side_vec.normalize(); p=self.body_root.getPos(self.render); p += side_vec*(NPC_DEFENSE_SIDE_STEP*dt*0.22*blend)
                    limit=WORLD_HALF-BODY_COLLISION_RADIUS; p.x=max(-limit,min(limit,p.x)); p.y=max(-limit,min(limit,p.y)); self.body_root.setPos(self.render,p)
            # Guard/brace: forearms rise toward face/chest while torso leans off the impact line.
            for side in ('left','right'):
                sh=self.rig_joints.get(side+'_shoulder'); el=self.rig_joints.get(side+'_elbow')
                if sh is not None and not self._joint_is_detached(side+'_shoulder'):
                    sh.setH((18.0 if side=='left' else -18.0)*blend)
                    sh.setP(-18.0*blend); sh.setR((12.0 if side=='left' else -12.0)*blend)
                if el is not None and not self._joint_is_detached(side+'_elbow'): el.setP(-48.0*blend)
        elif self.rig_joints:
            # Autonomous arm controllers will smoothly retake authority next frame.
            pass

    # ---------- FIRST NPC WALKING GAIT ----------
    @staticmethod
    def _shortest_heading_delta(current, target):
        return ((float(target) - float(current) + 180.0) % 360.0) - 180.0

    def _clear_walk_pose(self, dt=1.0):
        """Ease locomotion-only joints back toward their rig rest transforms."""
        self.npc_walk_blend = self._approach_scalar(
            self.npc_walk_blend, 0.0, NPC_WALK_BLEND_SPEED * max(0.0, float(dt))
        )
        b = self.npc_walk_blend
        if self.rig_joints:
            for name in ('left_hip','right_hip','left_knee','right_knee','left_ankle','right_ankle','left_foot','right_foot'):
                if name in self.rig_joints and not self._joint_is_detached(name):
                    hpr=self.rig_joints[name].getHpr()
                    step=140.0*max(0.0,float(dt))
                    self.rig_joints[name].setHpr(
                        self._approach_scalar(hpr.x,0.0,step),
                        self._approach_scalar(hpr.y,0.0,step),
                        self._approach_scalar(hpr.z,0.0,step),
                    )
            if 'pelvis' in self.rig_joints:
                hpr=self.rig_joints['pelvis'].getHpr()
                self.rig_joints['pelvis'].setR(self._approach_scalar(hpr.z,0.0,140.0*max(0.0,float(dt))))
        if getattr(self,'body_root',None) is not None:
            pos=self.body_root.getPos(self.render)
            target_z=self.npc_walk_base_z
            pos.z=self._approach_scalar(pos.z,target_z,0.09*max(0.0,float(dt)))
            self.body_root.setPos(pos)
        self.npc_walk_moving=False
        return b

    @staticmethod
    def _smoothstep01(x):
        x=max(0.0,min(1.0,float(x)))
        return x*x*(3.0-2.0*x)

    @classmethod
    def _pass45_swing_shape(cls, progress):
        """Return (knee_flex, foot_world_pitch) for one swing leg.

        The user-authored joint map is the authority: the knee only folds in the
        forward swing and uses the opposite hinge direction from the elbows.  The
        foot is allowed a small relaxed droop after lift, then levels before contact.
        """
        p=max(0.0,min(1.0,float(progress)))
        if p <= NPC_KNEE_PEAK_SWING:
            knee=NPC_KNEE_FLEX_DEG*cls._smoothstep01(p/max(1e-6,NPC_KNEE_PEAK_SWING))
        else:
            knee=NPC_KNEE_FLEX_DEG*(1.0-cls._smoothstep01((p-NPC_KNEE_PEAK_SWING)/max(1e-6,1.0-NPC_KNEE_PEAK_SWING)))
        # Small early plantar-flexed/drooped presentation.  By terminal swing the
        # foot target is exactly flat; this lets the ankle absorb the upstream
        # hip+knee pitch without leaving the toes pointed at the floor.
        if p < NPC_ANKLE_LEVEL_BEGIN:
            droop=NPC_ANKLE_DROOP_DEG*math.sin(math.pi*min(1.0,p/max(1e-6,NPC_ANKLE_LEVEL_BEGIN)))
        elif p < NPC_ANKLE_LEVEL_END:
            droop=NPC_ANKLE_DROOP_DEG*(1.0-cls._smoothstep01((p-NPC_ANKLE_LEVEL_BEGIN)/max(1e-6,NPC_ANKLE_LEVEL_END-NPC_ANKLE_LEVEL_BEGIN)))
        else:
            droop=0.0
        return knee,droop

    def _pass45_leg_pose(self, side, phase, blend):
        phase=float(phase)%(2.0*math.pi); b=max(0.0,min(1.0,float(blend)))
        s=math.sin(phase)
        hip=(NPC_HIP_SWING_DEG*s if side=='left' else -NPC_HIP_SWING_DEG*s)*b
        if side=='right':
            swinging=(0.0 < phase < math.pi)
            progress=phase/math.pi if swinging else 0.0
        else:
            swinging=(math.pi < phase < 2.0*math.pi)
            progress=(phase-math.pi)/math.pi if swinging else 0.0
        knee=0.0; foot_world=0.0
        if swinging and b>1e-5:
            knee,foot_world=self._pass45_swing_shape(progress)
            knee*=b; foot_world*=b
        # Knee pitch is POSITIVE here by design: the NPC elbow animation bends with
        # negative pitch, so this is the opposite anatomical hinge direction from
        # the user's joint map.  No H/R is ever applied to a knee.
        ankle=foot_world-(hip+knee)
        return {'hip':hip,'knee':knee,'ankle':ankle,'foot':0.0,'swinging':swinging,'progress':progress,'foot_world':foot_world}

    def _pass45_capture_contact_plane(self):
        if not self.rig_joints: return
        for side in ('left','right'):
            name=side+'_foot'
            if name in self.rig_joints and self.npc_walk_contact_z.get(side) is None:
                self.npc_walk_contact_z[side]=float(self.rig_joints[name].getZ(self.render))

    def _apply_walk_gait(self, dt, moving):
        target_blend = 1.0 if moving else 0.0
        self.npc_walk_blend = self._approach_scalar(
            self.npc_walk_blend, target_blend, NPC_WALK_BLEND_SPEED * max(0.0, float(dt))
        )
        if moving:
            self.npc_walk_phase = (self.npc_walk_phase + 2.0*math.pi*NPC_GAIT_HZ*max(0.0,float(dt))) % (2.0*math.pi)
        b=self.npc_walk_blend
        phase=self.npc_walk_phase
        left=self._pass45_leg_pose('left',phase,b); right=self._pass45_leg_pose('right',phase,b)
        for side,pose in (('left',left),('right',right)):
            for joint,key in (('hip','hip'),('knee','knee'),('ankle','ankle'),('foot','foot')):
                name=f'{side}_{joint}'
                if name in self.rig_joints and not self._joint_is_detached(name):
                    # Pass 45 joint-map enforcement: gait knees/ankles are sagittal hinges.
                    self.rig_joints[name].setHpr(0.0,float(pose[key]),0.0)
        if 'pelvis' in self.rig_joints:
            self.rig_joints['pelvis'].setR(NPC_PELVIS_ROLL_DEG*math.sin(phase)*b)

        # Ground contact replaces generic vertical bob.  Re-evaluate from the neutral
        # root height every frame so the currently planted foot remains on its authored
        # contact plane while the opposite leg swings.
        self._pass45_capture_contact_plane()
        pos=self.body_root.getPos(self.render); pos.z=self.npc_walk_base_z; self.body_root.setPos(self.render,pos)
        if b>1e-4 and self.rig_joints:
            stance='left' if right['swinging'] else 'right'
            target=self.npc_walk_contact_z.get(stance)
            if target is not None and stance+'_foot' in self.rig_joints:
                current=float(self.rig_joints[stance+'_foot'].getZ(self.render))
                correction=float(target)-current
                # Direct solve is deliberate: root height is the contact constraint, not
                # decorative bobbing.  The correction is tiny because the authored leg
                # lengths and hip swing are preserved.
                pos=self.body_root.getPos(self.render); pos.z += correction; self.body_root.setPos(self.render,pos)
        self.npc_walk_debug={'left':left,'right':right,'stance':('left' if right['swinging'] else 'right')}

    def _update_npc_walk(self, dt):
        """Move body_root through a small patrol while the rig supplies gait.

        Translation lives at body_root; hips/knees/ankles remain local joint
        animation.  This preserves the skeleton as parent authority and keeps
        organs, neural matter, head tracking and ASCII skin attached.
        """
        if (ARGS.safe_mode or ARGS.no_skeleton or ARGS.no_npc_walk
                or ARGS.rig_smoke or ARGS.head_track_smoke or ARGS.arm_smoke
                or ARGS.shoulder_smoke or ARGS.fps_control_smoke):
            self._clear_walk_pose(dt)
            return
        if not self.rig_joints or not all(n in self.rig_joints for n in ('pelvis','left_hip','right_hip','left_knee','right_knee','left_ankle','right_ankle')):
            return
        self.npc_walk_time += max(0.0,float(dt))
        if self.npc_walk_time < NPC_WALK_START_DELAY and not ARGS.walk_smoke:
            self._clear_walk_pose(dt)
            return
        # Damage no longer freezes the NPC in place. Rewind still owns the reconstruction pose,
        # while ordinary wounds/fragments permit a reduced defensive stagger/walk response.
        if self.rewinding:
            self._clear_walk_pose(dt)
            return
        if any(name in self.detached_joint_names for name in ('left_hip','right_hip','left_knee','right_knee','left_ankle','right_ankle')):
            self._clear_walk_pose(dt)
            return

        root=self.body_root.getPos(self.render)
        tx,ty=NPC_WALK_ROUTE[self.npc_walk_route_index]
        dx,dy=tx-root.x,ty-root.y
        dist=math.hypot(dx,dy)
        if dist <= NPC_WAYPOINT_RADIUS:
            self.npc_walk_route_index=(self.npc_walk_route_index+1)%len(NPC_WALK_ROUTE)
            tx,ty=NPC_WALK_ROUTE[self.npc_walk_route_index]
            dx,dy=tx-root.x,ty-root.y
            dist=math.hypot(dx,dy)
        if dist <= 1e-7:
            self._apply_walk_gait(dt,False)
            return

        desired_h=math.degrees(math.atan2(dx,-dy))
        current_h=float(self.body_root.getH(self.render))
        delta_h=self._shortest_heading_delta(current_h,desired_h)
        turn_step=NPC_TURN_SPEED_DPS*max(0.0,float(dt))
        new_h=current_h+max(-turn_step,min(turn_step,delta_h))
        self.body_root.setH(self.render,new_h)
        aligned=abs(delta_h)<=10.0
        moving=aligned
        if moving:
            defense_scale=.42 if self.npc_defense_timer>0.0 else (.68 if self.wounds else 1.0)
            step=min(dist,NPC_WALK_SPEED*defense_scale*max(0.0,float(dt)))
            ux,uy=dx/dist,dy/dist
            root=self.body_root.getPos(self.render)
            root.x += ux*step; root.y += uy*step
            self.body_root.setPos(self.render,root)
            self.npc_walk_distance += step
        self.npc_walk_moving=moving
        self._apply_walk_gait(dt,moving)

    def _walk_smoke_step(self):
        """Fast deterministic Panda3D proof of root locomotion + leg hierarchy."""
        if not ARGS.walk_smoke:
            return
        if self.frame_count != 1:
            return
        required=('pelvis','left_hip','right_hip','left_knee','right_knee','left_ankle','right_ankle','left_foot','right_foot')
        if not self.rig_joints or not all(n in self.rig_joints for n in required):
            raise RuntimeError('WALK_SMOKE_REQUIRES_LEG_RIG')
        self.npc_walk_time=NPC_WALK_START_DELAY
        self.npc_walk_route_index=0
        self.npc_walk_phase=0.0
        self.npc_walk_blend=0.0
        self.npc_walk_distance=0.0
        self.body_root.setPos(0,0,self.npc_walk_base_z); self.body_root.setH(0)
        torso_idx=next(i for i,b in enumerate(self.body_bindings) if b=='spine_mid')
        brain_idx=next(i for i,b in enumerate(self.organ_bindings) if b=='head_base')
        root0=_v3(self.body_root.getPos(self.render))
        torso0=_v3(self.glyph_nodes[torso_idx].getPos(self.render))
        brain0=_v3(self.organ_nodes[brain_idx].getPos(self.render))
        left0=_v3(self.rig_joints['left_foot'].getPos(self.body_root))
        right0=_v3(self.rig_joints['right_foot'].getPos(self.body_root))
        left_exc=0.0; right_exc=0.0; max_knee=0.0; max_shoulder=0.0; max_elbow=0.0
        # About four seconds of full locomotion logic without asking TinyDisplay
        # to rasterize every substep.  This includes the inherited arm counter-
        # swing and neck tracking layered on top of the moving parent body.
        for _ in range(120):
            fixed=1.0/30.0
            self._update_npc_walk(fixed)
            self._update_shoulder_articulation(fixed)
            self._update_arm_articulation(fixed)
            self._update_head_tracking(fixed)
            left_exc=max(left_exc,(_v3(self.rig_joints['left_foot'].getPos(self.body_root))-left0).length())
            right_exc=max(right_exc,(_v3(self.rig_joints['right_foot'].getPos(self.body_root))-right0).length())
            max_knee=max(max_knee,abs(float(self.rig_joints['left_knee'].getP())),abs(float(self.rig_joints['right_knee'].getP())))
            max_shoulder=max(max_shoulder,abs(float(self.rig_joints['left_shoulder'].getP())),abs(float(self.rig_joints['right_shoulder'].getP())))
            max_elbow=max(max_elbow,abs(float(self.rig_joints['left_elbow'].getP())),abs(float(self.rig_joints['right_elbow'].getP())))
        root1=_v3(self.body_root.getPos(self.render))
        torso1=_v3(self.glyph_nodes[torso_idx].getPos(self.render))
        brain1=_v3(self.organ_nodes[brain_idx].getPos(self.render))
        root_move=(root1-root0).length()
        torso_move=(torso1-torso0).length()
        brain_move=(brain1-brain0).length()
        heading=abs(self._shortest_heading_delta(0.0,float(self.body_root.getH(self.render))))
        # Dynamic player collision should now resolve around the moved NPC center.
        npc=_v3(self.body_root.getPos(self.render))
        probe=Vec3(npc.x,npc.y-0.2,0.0)
        resolved,collided,_=self._resolve_body_collision(probe)
        collision_dist=math.hypot(resolved.x-npc.x,resolved.y-npc.y)
        ok=(self.npc_walk_distance>1.2 and root_move>0.4 and torso_move>0.4 and brain_move>0.4
            and left_exc>0.03 and right_exc>0.03 and max_knee>12.0 and max_shoulder>5.0 and max_elbow>8.0 and heading>20.0
            and collided and abs(collision_dist-(BODY_COLLISION_RADIUS+PLAYER_RADIUS))<0.002
            and abs(self.head_track_h)<=HEAD_TRACK_YAW_LIMIT+1e-3 and abs(self.head_track_p)<=max(HEAD_TRACK_PITCH_UP_LIMIT,HEAD_TRACK_PITCH_DOWN_LIMIT)+1e-3)
        print(
            "ASCII_MATTER_WALK_SMOKE="+('PASS' if ok else 'FAIL')
            +f" distance={self.npc_walk_distance:.3f} root_move={root_move:.3f} torso_move={torso_move:.3f} brain_move={brain_move:.3f}"
            +f" left_foot={left_exc:.3f} right_foot={right_exc:.3f} knee={max_knee:.2f} shoulder={max_shoulder:.2f} elbow={max_elbow:.2f}"
            +f" heading={heading:.2f} head={self.head_track_h:.2f}/{self.head_track_p:.2f} collision={collision_dist:.3f}"
        )
        if not ok:
            raise RuntimeError('NPC_WALK_SMOKE_FAILED')

    # ---------- INDEPENDENT SHOULDER ARTICULATION ----------
    def _shoulder_target(self, side, t):
        """Return local pitch/roll for one shoulder without touching the torso.

        The shoulder owns the whole downstream arm chain.  Local pitch provides
        a restrained front/back swing while mirrored roll provides a small
        lateral lift.  Elbow animation remains a separate child transform, so
        the two motions compose through the existing hierarchy.
        """
        phase = 0.0 if side == 'left' else math.pi * 1.08
        idle_swing = math.sin((2.0 * math.pi * SHOULDER_SWAY_SPEED_HZ * t) + phase)
        lift_wave = 0.5 + 0.5 * math.sin((2.0 * math.pi * SHOULDER_SWAY_SPEED_HZ * t * 0.73) + phase + 0.65)
        blend = float(getattr(self, 'npc_walk_blend', 0.0))
        if blend > 0.001:
            gait = math.sin(float(getattr(self, 'npc_walk_phase', 0.0)))
            gait_swing = (-gait if side == 'left' else gait)
            swing = idle_swing * (1.0 - blend) + gait_swing * blend
            pitch = (SHOULDER_SWING_DEG * (1.0 - blend) + 12.0 * blend) * swing
            lift = (SHOULDER_LIFT_DEG * (1.0 - blend) + 1.8 * blend) * lift_wave
        else:
            pitch = SHOULDER_SWING_DEG * idle_swing
            lift = SHOULDER_LIFT_DEG * lift_wave
        roll = lift if side == 'left' else -lift
        return pitch, roll

    def _update_shoulder_articulation(self, dt):
        if (ARGS.safe_mode or ARGS.no_skeleton or ARGS.no_shoulder_sway or self.npc_defense_timer>0.0
                or ARGS.rig_smoke or ARGS.head_track_smoke or ARGS.arm_smoke or ARGS.shoulder_smoke):
            return
        if not self.rig_joints or 'left_shoulder' not in self.rig_joints or 'right_shoulder' not in self.rig_joints:
            return
        self.shoulder_anim_time += max(0.0, float(dt))
        lp, lr = self._shoulder_target('left', self.shoulder_anim_time)
        rp, rr = self._shoulder_target('right', self.shoulder_anim_time)
        step = SHOULDER_RESPONSE_DPS * max(0.0, float(dt))
        self.shoulder_pitch_left = self._approach_scalar(self.shoulder_pitch_left, lp, step)
        self.shoulder_pitch_right = self._approach_scalar(self.shoulder_pitch_right, rp, step)
        self.shoulder_roll_left = self._approach_scalar(self.shoulder_roll_left, lr, step)
        self.shoulder_roll_right = self._approach_scalar(self.shoulder_roll_right, rr, step)
        if not self._joint_is_detached('left_shoulder'): self.rig_joints['left_shoulder'].setHpr(0.0, self.shoulder_pitch_left, self.shoulder_roll_left)
        if not self._joint_is_detached('right_shoulder'): self.rig_joints['right_shoulder'].setHpr(0.0, self.shoulder_pitch_right, self.shoulder_roll_right)

    def _shoulder_smoke_step(self):
        """Deterministic Panda3D proof that shoulders own only their arm subtree."""
        if not ARGS.shoulder_smoke:
            return
        required = ('left_shoulder','right_shoulder','left_elbow','right_elbow',
                    'left_hand','right_hand','left_middle_tip','right_middle_tip')
        if not self.rig_joints or not all(name in self.rig_joints for name in required):
            raise RuntimeError('SHOULDER_SMOKE_REQUIRES_FINGERED_RIG')
        if self.frame_count == 1:
            torso_idx = next(i for i,b in enumerate(self.body_bindings) if b == 'spine_mid')
            left_upper_idx = next(i for i,b in enumerate(self.body_bindings) if b == 'left_shoulder')
            right_upper_idx = next(i for i,b in enumerate(self.body_bindings) if b == 'right_shoulder')
            left_hand_idx = next(i for i,b in enumerate(self.body_bindings) if b == 'left_hand')
            right_hand_idx = next(i for i,b in enumerate(self.body_bindings) if b == 'right_hand')
            self.shoulder_test_state = {
                'torso_idx':torso_idx,'left_upper_idx':left_upper_idx,'right_upper_idx':right_upper_idx,
                'left_hand_idx':left_hand_idx,'right_hand_idx':right_hand_idx,
                'torso_rest':_v3(self.glyph_nodes[torso_idx].getPos(self.render)),
                'left_upper_rest':_v3(self.glyph_nodes[left_upper_idx].getPos(self.render)),
                'right_upper_rest':_v3(self.glyph_nodes[right_upper_idx].getPos(self.render)),
                'left_hand_rest':_v3(self.glyph_nodes[left_hand_idx].getPos(self.render)),
                'right_hand_rest':_v3(self.glyph_nodes[right_hand_idx].getPos(self.render)),
                'left_elbow_rest':_v3(self.rig_joints['left_elbow'].getPos(self.render)),
                'right_elbow_rest':_v3(self.rig_joints['right_elbow'].getPos(self.render)),
                'left_finger_rest':_v3(self.rig_joints['left_middle_tip'].getPos(self.render)),
                'right_finger_rest':_v3(self.rig_joints['right_middle_tip'].getPos(self.render)),
            }
            # Compose a shoulder swing with an elbow bend to prove forward
            # kinematics through the entire left arm subtree.
            self.rig_joints['left_shoulder'].setHpr(0.0, -18.0, 11.0)
            self.rig_joints['left_elbow'].setP(-32.0)
        elif self.frame_count == 2 and self.shoulder_test_state:
            st=self.shoulder_test_state
            st['left_upper_move']=(_v3(self.glyph_nodes[st['left_upper_idx']].getPos(self.render))-st['left_upper_rest']).length()
            st['left_elbow_move']=(_v3(self.rig_joints['left_elbow'].getPos(self.render))-st['left_elbow_rest']).length()
            st['left_hand_move']=(_v3(self.glyph_nodes[st['left_hand_idx']].getPos(self.render))-st['left_hand_rest']).length()
            st['left_finger_move']=(_v3(self.rig_joints['left_middle_tip'].getPos(self.render))-st['left_finger_rest']).length()
            st['torso_during_left']=(_v3(self.glyph_nodes[st['torso_idx']].getPos(self.render))-st['torso_rest']).length()
            st['right_hand_during_left']=(_v3(self.glyph_nodes[st['right_hand_idx']].getPos(self.render))-st['right_hand_rest']).length()
            self.rig_joints['left_elbow'].setP(0.0)
            self.rig_joints['left_shoulder'].setHpr(0.0,0.0,0.0)
            self.rig_joints['right_shoulder'].setHpr(0.0, 16.0, -10.0)
            self.rig_joints['right_elbow'].setP(-27.0)
        elif self.frame_count == 3 and self.shoulder_test_state:
            st=self.shoulder_test_state
            st['right_upper_move']=(_v3(self.glyph_nodes[st['right_upper_idx']].getPos(self.render))-st['right_upper_rest']).length()
            st['right_elbow_move']=(_v3(self.rig_joints['right_elbow'].getPos(self.render))-st['right_elbow_rest']).length()
            st['right_hand_move']=(_v3(self.glyph_nodes[st['right_hand_idx']].getPos(self.render))-st['right_hand_rest']).length()
            st['right_finger_move']=(_v3(self.rig_joints['right_middle_tip'].getPos(self.render))-st['right_finger_rest']).length()
            st['torso_during_right']=(_v3(self.glyph_nodes[st['torso_idx']].getPos(self.render))-st['torso_rest']).length()
            st['left_restore_mid']=(_v3(self.glyph_nodes[st['left_hand_idx']].getPos(self.render))-st['left_hand_rest']).length()
            self.rig_joints['right_elbow'].setP(0.0)
            self.rig_joints['right_shoulder'].setHpr(0.0,0.0,0.0)
        elif self.frame_count == 4 and self.shoulder_test_state:
            st=self.shoulder_test_state
            st['left_restore']=(_v3(self.glyph_nodes[st['left_hand_idx']].getPos(self.render))-st['left_hand_rest']).length()
            st['right_restore']=(_v3(self.glyph_nodes[st['right_hand_idx']].getPos(self.render))-st['right_hand_rest']).length()
            st['torso_final']=(_v3(self.glyph_nodes[st['torso_idx']].getPos(self.render))-st['torso_rest']).length()
            ok=(
                st['left_upper_move'] > 0.005 and st['right_upper_move'] > 0.005
                and st['left_elbow_move'] > 0.01 and st['right_elbow_move'] > 0.01
                and st['left_hand_move'] > 0.03 and st['right_hand_move'] > 0.03
                and st['left_finger_move'] > 0.03 and st['right_finger_move'] > 0.03
                and max(st['torso_during_left'],st['torso_during_right'],st['torso_final']) < 0.0005
                and st['right_hand_during_left'] < 0.0005
                and st['left_restore_mid'] < 0.0005
                and st['left_restore'] < 0.0005 and st['right_restore'] < 0.0005
            )
            print(
                "ASCII_MATTER_SHOULDER_SMOKE=" + ('PASS' if ok else 'FAIL')
                + f" left_upper={st['left_upper_move']:.6f} left_elbow={st['left_elbow_move']:.6f}"
                + f" left_hand={st['left_hand_move']:.6f} left_finger={st['left_finger_move']:.6f}"
                + f" right_upper={st['right_upper_move']:.6f} right_elbow={st['right_elbow_move']:.6f}"
                + f" right_hand={st['right_hand_move']:.6f} right_finger={st['right_finger_move']:.6f}"
                + f" torso={max(st['torso_during_left'],st['torso_during_right'],st['torso_final']):.6f}"
                + f" opposite={st['right_hand_during_left']:.6f} restore={max(st['left_restore'],st['right_restore']):.6f}"
            )
            if not ok:
                raise RuntimeError('INDEPENDENT_SHOULDER_SMOKE_FAILED')
            self.userExit()

    # ---------- INDEPENDENT ELBOW ARTICULATION ----------
    def _elbow_target(self, side, t):
        """Return a gentle elbow-local bend angle for one arm.

        The upper arm remains parented to the shoulder.  Applying pitch only at
        the elbow means the forearm, wrist, hand and finger descendants move,
        while the humerus, torso and opposite arm stay unchanged.
        """
        phase = 0.0 if side == 'left' else math.pi * 1.17
        blend = float(getattr(self, 'npc_walk_blend', 0.0))
        if blend > 0.001:
            gait = math.sin(float(getattr(self, 'npc_walk_phase', 0.0)) + (0.0 if side == 'left' else math.pi))
            walk_bend = -(12.0 + 6.0 * (0.5 + 0.5 * gait))
            idle_wave = 0.5 + 0.5 * math.sin((2.0 * math.pi * ELBOW_FLEX_SPEED_HZ * t) + phase)
            idle_bend = -(ELBOW_FLEX_MIN_DEG + (ELBOW_FLEX_MAX_DEG - ELBOW_FLEX_MIN_DEG) * idle_wave)
            return idle_bend * (1.0 - blend) + walk_bend * blend
        wave = 0.5 + 0.5 * math.sin((2.0 * math.pi * ELBOW_FLEX_SPEED_HZ * t) + phase)
        return -(ELBOW_FLEX_MIN_DEG + (ELBOW_FLEX_MAX_DEG - ELBOW_FLEX_MIN_DEG) * wave)

    def _update_arm_articulation(self, dt):
        if (ARGS.safe_mode or ARGS.no_skeleton or ARGS.no_arm_flex
                or ARGS.rig_smoke or ARGS.head_track_smoke or ARGS.arm_smoke or ARGS.shoulder_smoke):
            return
        if not self.rig_joints or 'left_elbow' not in self.rig_joints or 'right_elbow' not in self.rig_joints:
            return
        self.arm_anim_time += max(0.0, float(dt))
        left_target = self._elbow_target('left', self.arm_anim_time)
        right_target = self._elbow_target('right', self.arm_anim_time)
        step = ELBOW_FLEX_RESPONSE_DPS * max(0.0, float(dt))
        self.arm_flex_left = self._approach_scalar(self.arm_flex_left, left_target, step)
        self.arm_flex_right = self._approach_scalar(self.arm_flex_right, right_target, step)
        if not self._joint_is_detached('left_elbow'): self.rig_joints['left_elbow'].setP(self.arm_flex_left)
        if not self._joint_is_detached('right_elbow'): self.rig_joints['right_elbow'].setP(self.arm_flex_right)

    def _arm_smoke_step(self):
        """Deterministic Panda3D proof that elbows isolate the rest of the rig."""
        if not ARGS.arm_smoke:
            return
        required = ('left_elbow','right_elbow','left_hand','right_hand','left_middle_tip','right_middle_tip')
        if not self.rig_joints or not all(name in self.rig_joints for name in required):
            raise RuntimeError('ARM_SMOKE_REQUIRES_FINGERED_RIG')
        if self.frame_count == 1:
            torso_idx = next(i for i,b in enumerate(self.body_bindings) if b == 'spine_mid')
            left_upper_idx = next(i for i,b in enumerate(self.body_bindings) if b == 'left_shoulder')
            right_upper_idx = next(i for i,b in enumerate(self.body_bindings) if b == 'right_shoulder')
            left_hand_idx = next(i for i,b in enumerate(self.body_bindings) if b == 'left_hand')
            right_hand_idx = next(i for i,b in enumerate(self.body_bindings) if b == 'right_hand')
            # Pass 18 regression authority: these far-lateral samples are the actual
            # hanging hands.  Pass 17's z>=0.79 rectangle orphaned the lower 16
            # glyphs by attaching them to the hips.
            left_zone=[i for i,item in enumerate(self.surface) if item['p'][0] < 0 and abs(item['p'][0]) >= 0.30 and 0.70 <= item['p'][2] <= 1.02]
            right_zone=[i for i,item in enumerate(self.surface) if item['p'][0] >= 0 and abs(item['p'][0]) >= 0.30 and 0.70 <= item['p'][2] <= 1.02]
            left_low=[i for i in left_zone if self.surface[i]['p'][2] < 0.79]
            right_low=[i for i in right_zone if self.surface[i]['p'][2] < 0.79]
            allowed_left={'left_elbow','left_wrist','left_hand'}
            allowed_right={'right_elbow','right_wrist','right_hand'}
            orphan_left=sum(self.body_bindings[i] not in allowed_left for i in left_zone)
            orphan_right=sum(self.body_bindings[i] not in allowed_right for i in right_zone)
            low_wrong_left=sum(self.body_bindings[i] != 'left_hand' for i in left_low)
            low_wrong_right=sum(self.body_bindings[i] != 'right_hand' for i in right_low)
            self.arm_test_state = {
                'torso_idx':torso_idx,'left_upper_idx':left_upper_idx,'right_upper_idx':right_upper_idx,
                'left_hand_idx':left_hand_idx,'right_hand_idx':right_hand_idx,
                'left_zone':left_zone,'right_zone':right_zone,'left_low':left_low,'right_low':right_low,
                'orphan_left':orphan_left,'orphan_right':orphan_right,
                'low_wrong_left':low_wrong_left,'low_wrong_right':low_wrong_right,
                'torso_rest':_v3(self.glyph_nodes[torso_idx].getPos(self.render)),
                'left_upper_rest':_v3(self.glyph_nodes[left_upper_idx].getPos(self.render)),
                'right_upper_rest':_v3(self.glyph_nodes[right_upper_idx].getPos(self.render)),
                'left_hand_rest':_v3(self.glyph_nodes[left_hand_idx].getPos(self.render)),
                'right_hand_rest':_v3(self.glyph_nodes[right_hand_idx].getPos(self.render)),
                'left_low_rest':[_v3(self.glyph_nodes[i].getPos(self.render)) for i in left_low],
                'right_low_rest':[_v3(self.glyph_nodes[i].getPos(self.render)) for i in right_low],
                'left_finger_rest':_v3(self.rig_joints['left_middle_tip'].getPos(self.render)),
                'right_finger_rest':_v3(self.rig_joints['right_middle_tip'].getPos(self.render)),
                'left_elbow_z':float(self.rig_rest_positions['left_elbow'].z),
                'right_elbow_z':float(self.rig_rest_positions['right_elbow'].z),
            }
            self.rig_joints['left_elbow'].setP(-38.0)
        elif self.frame_count == 2 and self.arm_test_state:
            st=self.arm_test_state
            st['left_hand_move']=(_v3(self.glyph_nodes[st['left_hand_idx']].getPos(self.render))-st['left_hand_rest']).length()
            st['left_finger_move']=(_v3(self.rig_joints['left_middle_tip'].getPos(self.render))-st['left_finger_rest']).length()
            st['torso_left_move']=(_v3(self.glyph_nodes[st['torso_idx']].getPos(self.render))-st['torso_rest']).length()
            st['left_upper_move']=(_v3(self.glyph_nodes[st['left_upper_idx']].getPos(self.render))-st['left_upper_rest']).length()
            st['right_hand_during_left']=(_v3(self.glyph_nodes[st['right_hand_idx']].getPos(self.render))-st['right_hand_rest']).length()
            st['left_low_min_move']=min(((_v3(self.glyph_nodes[i].getPos(self.render))-rest).length() for i,rest in zip(st['left_low'],st['left_low_rest'])), default=0.0)
            self.rig_joints['left_elbow'].setP(0.0)
            self.rig_joints['right_elbow'].setP(-35.0)
        elif self.frame_count == 3 and self.arm_test_state:
            st=self.arm_test_state
            st['right_hand_move']=(_v3(self.glyph_nodes[st['right_hand_idx']].getPos(self.render))-st['right_hand_rest']).length()
            st['right_finger_move']=(_v3(self.rig_joints['right_middle_tip'].getPos(self.render))-st['right_finger_rest']).length()
            st['torso_right_move']=(_v3(self.glyph_nodes[st['torso_idx']].getPos(self.render))-st['torso_rest']).length()
            st['right_upper_move']=(_v3(self.glyph_nodes[st['right_upper_idx']].getPos(self.render))-st['right_upper_rest']).length()
            st['left_restore']=(_v3(self.glyph_nodes[st['left_hand_idx']].getPos(self.render))-st['left_hand_rest']).length()
            st['right_low_min_move']=min(((_v3(self.glyph_nodes[i].getPos(self.render))-rest).length() for i,rest in zip(st['right_low'],st['right_low_rest'])), default=0.0)
            self.rig_joints['right_elbow'].setP(0.0)
        elif self.frame_count == 4 and self.arm_test_state:
            st=self.arm_test_state
            st['right_restore']=(_v3(self.glyph_nodes[st['right_hand_idx']].getPos(self.render))-st['right_hand_rest']).length()
            st['torso_final']=(_v3(self.glyph_nodes[st['torso_idx']].getPos(self.render))-st['torso_rest']).length()
            ok=(
                st['left_hand_move'] > 0.02 and st['left_finger_move'] > 0.02
                and st['right_hand_move'] > 0.02 and st['right_finger_move'] > 0.02
                and max(st['torso_left_move'],st['torso_right_move'],st['torso_final']) < 0.0005
                and st['left_upper_move'] < 0.0005 and st['right_upper_move'] < 0.0005
                and st['right_hand_during_left'] < 0.0005
                and st['left_restore'] < 0.0005 and st['right_restore'] < 0.0005
                and st['orphan_left'] == 0 and st['orphan_right'] == 0
                and st['low_wrong_left'] == 0 and st['low_wrong_right'] == 0
                and st['left_low_min_move'] > 0.02 and st['right_low_min_move'] > 0.02
                and abs(st['left_elbow_z'] - 1.225) < 1e-6 and abs(st['right_elbow_z'] - 1.225) < 1e-6
            )
            print(
                "ASCII_MATTER_ARM_SMOKE=" + ('PASS' if ok else 'FAIL')
                + f" left_hand={st['left_hand_move']:.6f} left_finger={st['left_finger_move']:.6f}"
                + f" right_hand={st['right_hand_move']:.6f} right_finger={st['right_finger_move']:.6f}"
                + f" torso={max(st['torso_left_move'],st['torso_right_move'],st['torso_final']):.6f}"
                + f" upper={max(st['left_upper_move'],st['right_upper_move']):.6f}"
                + f" opposite={st['right_hand_during_left']:.6f} restore={max(st['left_restore'],st['right_restore']):.6f}"
                + f" low_hand_min={min(st['left_low_min_move'],st['right_low_min_move']):.6f}"
                + f" hand_orphans={st['orphan_left']+st['orphan_right']} low_wrong={st['low_wrong_left']+st['low_wrong_right']}"
                + f" elbow_z={st['left_elbow_z']:.3f}/{st['right_elbow_z']:.3f} joints={len(self.rig_joints)} fingers=10"
            )
            if not ok:
                raise RuntimeError('INDEPENDENT_ELBOW_SMOKE_FAILED')

    # ---------- HEAD / NECK TRACKING ----------
    @staticmethod
    def _approach_scalar(current, target, max_step):
        delta = float(target) - float(current)
        if abs(delta) <= max_step:
            return float(target)
        return float(current) + math.copysign(max_step, delta)

    def _head_track_target_angles(self, target_world):
        """Return bounded neck-local heading/pitch toward a world-space target.

        The body was authored facing world -Y.  Computing in the neck parent's
        coordinate space means future torso animation remains the parent frame;
        the neck only contributes its local swivel.
        """
        if not self.rig_joints or 'neck' not in self.rig_joints:
            return 0.0, 0.0
        neck = self.rig_joints['neck']
        parent = neck.getParent()
        target_local = parent.getRelativePoint(self.render, _v3(target_world))
        neck_local = neck.getPos(parent)
        delta = target_local - neck_local
        planar = math.hypot(delta.x, delta.y)
        if planar <= 1e-8 and abs(delta.z) <= 1e-8:
            return 0.0, 0.0
        # Authored face-forward vector is (0,-1,0).
        desired_h = math.degrees(math.atan2(delta.x, -delta.y))
        desired_p = -math.degrees(math.atan2(delta.z, max(planar, 1e-8)))
        desired_h = max(-HEAD_TRACK_YAW_LIMIT, min(HEAD_TRACK_YAW_LIMIT, desired_h))
        desired_p = max(-HEAD_TRACK_PITCH_UP_LIMIT, min(HEAD_TRACK_PITCH_DOWN_LIMIT, desired_p))
        if abs(desired_h) < HEAD_TRACK_DEADZONE_DEG:
            desired_h = 0.0
        if abs(desired_p) < HEAD_TRACK_DEADZONE_DEG:
            desired_p = 0.0
        return desired_h, desired_p

    def _update_head_tracking(self, dt):
        """Swivel the neck so all descendants above it follow the player."""
        if ARGS.safe_mode or ARGS.no_skeleton or ARGS.no_head_track or ARGS.rig_smoke:
            return
        if not self.rig_joints or 'neck' not in self.rig_joints or self._joint_is_detached('neck') or self._joint_is_detached('head_base'):
            return
        eye = CROUCH_EYE if self.crouching else STAND_EYE
        target_world = Vec3(self.player_pos.x, self.player_pos.y, self.player_pos.z + eye)
        target_h, target_p = self._head_track_target_angles(target_world)
        self.head_track_target_h = target_h
        self.head_track_target_p = target_p
        max_step = HEAD_TRACK_SPEED_DPS * max(0.0, float(dt))
        self.head_track_h = self._approach_scalar(self.head_track_h, target_h, max_step)
        self.head_track_p = self._approach_scalar(self.head_track_p, target_p, max_step)
        self.rig_joints['neck'].setHpr(self.head_track_h + self.impact_head_h,
                                           self.head_track_p + self.impact_head_p,
                                           self.impact_head_r)

    def _head_track_smoke_step(self):
        """Deterministic no-screenshot engine proof for the neck-parent contract."""
        if not ARGS.head_track_smoke:
            return
        if not self.rig_joints:
            raise RuntimeError('HEAD_TRACK_SMOKE_REQUIRES_ACTIVE_SKELETON')
        if self.frame_count == 1:
            head_idx = next(i for i,b in enumerate(self.body_bindings) if b == 'head_base')
            torso_idx = next(i for i,b in enumerate(self.body_bindings) if b == 'spine_mid')
            brain_idx = next(i for i,b in enumerate(self.organ_bindings) if b == 'head_base')
            self.head_track_state = {
                'head_idx': head_idx,
                'torso_idx': torso_idx,
                'brain_idx': brain_idx,
                'head_rest': _v3(self.glyph_nodes[head_idx].getPos(self.render)),
                'torso_rest': _v3(self.glyph_nodes[torso_idx].getPos(self.render)),
                'brain_rest': _v3(self.organ_nodes[brain_idx].getPos(self.render)),
            }
            self.player_pos = Vec3(2.2, -3.0, 0.0)
        elif self.frame_count == 14 and self.head_track_state:
            st = self.head_track_state
            st['right_h'] = self.head_track_h
            st['right_p'] = self.head_track_p
            st['head_right_move'] = (_v3(self.glyph_nodes[st['head_idx']].getPos(self.render)) - st['head_rest']).length()
            st['brain_right_move'] = (_v3(self.organ_nodes[st['brain_idx']].getPos(self.render)) - st['brain_rest']).length()
            st['torso_right_move'] = (_v3(self.glyph_nodes[st['torso_idx']].getPos(self.render)) - st['torso_rest']).length()
            # Bind a synthetic wound center to the same head branch without
            # detaching glyphs; the later left swivel must carry it with the head.
            head_world = _v3(self.glyph_nodes[st['head_idx']].getPos(self.render))
            live_hit = self._find_shot_hit(head_world + Vec3(0,-0.5,0), head_world + Vec3(0,0.5,0), .055)
            st['live_head_hit'] = bool(live_hit is not None and self.body_bindings[live_hit[1]] in ('head_base','neck'))
            head_joint = self.rig_joints['head_base']
            wound_local = head_joint.getRelativePoint(self.render, head_world)
            test_wound = Wound(wound_local, WOUND_RADIUS, 'head_base'); test_wound.age = WOUND_BLOOM_TIME
            self.wounds.append(test_wound); st['test_wound'] = test_wound
            self.player_pos = Vec3(-2.2, -3.0, 0.72)
        elif self.frame_count == 34 and self.head_track_state:
            st = self.head_track_state
            st['left_h'] = self.head_track_h
            st['up_p'] = self.head_track_p
            head_left_world = _v3(self.glyph_nodes[st['head_idx']].getPos(self.render))
            st['head_left_move'] = (head_left_world - st['head_rest']).length()
            st['torso_left_move'] = (_v3(self.glyph_nodes[st['torso_idx']].getPos(self.render)) - st['torso_rest']).length()
            wound_world = self._wound_center_world(st['test_wound'])
            st['bound_wound_error'] = (wound_world - head_left_world).length()
            self.wounds.remove(st['test_wound'])
            self.player_pos = Vec3(0.0, -3.0, -0.65)
        elif self.frame_count == 50 and self.head_track_state:
            st = self.head_track_state
            st['center_h'] = self.head_track_h
            st['down_p'] = self.head_track_p
            st['torso_final_move'] = (_v3(self.glyph_nodes[st['torso_idx']].getPos(self.render)) - st['torso_rest']).length()
            ok = (
                st['right_h'] > 15.0 and st['left_h'] < -15.0
                and st['up_p'] < -3.0 and st['down_p'] > 3.0
                and abs(st['center_h']) < 6.0
                and st['head_right_move'] > 0.002 and st['brain_right_move'] > 0.001
                and st['head_left_move'] > 0.002 and st['bound_wound_error'] < 0.0005 and st['live_head_hit']
                and st['torso_right_move'] < 0.0005 and st['torso_left_move'] < 0.0005 and st['torso_final_move'] < 0.0005
                and abs(self.head_track_h) <= HEAD_TRACK_YAW_LIMIT + 1e-4
                and -HEAD_TRACK_PITCH_UP_LIMIT - 1e-4 <= self.head_track_p <= HEAD_TRACK_PITCH_DOWN_LIMIT + 1e-4
            )
            print(
                "ASCII_MATTER_HEAD_TRACK_SMOKE=" + ('PASS' if ok else 'FAIL')
                + f" right_h={st['right_h']:.3f} left_h={st['left_h']:.3f} up_p={st['up_p']:.3f} down_p={st['down_p']:.3f}"
                + f" center_h={st['center_h']:.3f} head_move={st['head_right_move']:.6f} brain_move={st['brain_right_move']:.6f}"
                + f" torso_move={max(st['torso_right_move'],st['torso_left_move'],st['torso_final_move']):.6f} wound_bind_error={st['bound_wound_error']:.6f} live_head_hit={int(st['live_head_hit'])}"
            )
            if not ok:
                raise RuntimeError('HEAD_TRACK_PARENT_SMOKE_FAILED')


    def _fps_control_smoke_step(self):
        if not ARGS.fps_control_smoke or self.frame_count != 0:
            return
        dt = 1.0 / 60.0
        spawn_dot = float(self.spawn_facing_dot)

        # Panda3D movement-basis regression.  Positive Heading turns left, so
        # every cardinal camera heading must agree with Panda's own quaternion
        # basis and W movement must never rotate/rewrite yaw or pitch.
        basis_dots = []
        direction_dots = []
        yaw_pitch_drift = 0.0
        for heading in (0.0, 90.0, 180.0, 270.0):
            expected_forward, expected_right = self._movement_basis_for_yaw(heading)
            self.camera.setHpr(heading, 0.0, 0.0)
            engine_forward = _v3(self.camera.getQuat(self.render).getForward()); engine_forward.z = 0.0
            engine_right = _v3(self.camera.getQuat(self.render).getRight()); engine_right.z = 0.0
            engine_forward.normalize(); engine_right.normalize()
            basis_dots.extend((float(expected_forward.dot(engine_forward)), float(expected_right.dot(engine_right))))

            self.player_pos = Vec3(8.0, 8.0, 0.0)
            self.player_vel = Vec3(0,0,0); self.player_vel_z = 0.0
            self.on_ground = True; self.crouching = False; self.current_eye_height = STAND_EYE
            self.yaw = heading; self.pitch = 17.0; yaw_before = self.yaw; pitch_before = self.pitch
            self.keys = {'w'}
            start = _v3(self.player_pos)
            for _ in range(12):
                self._update_player(dt)
            delta = _v3(self.player_pos - start); delta.z = 0.0
            if delta.lengthSquared() > 1e-10:
                delta.normalize()
                direction_dots.append(float(delta.dot(expected_forward)))
            else:
                direction_dots.append(-1.0)
            yaw_pitch_drift = max(yaw_pitch_drift, abs(float(self.yaw-yaw_before)), abs(float(self.pitch-pitch_before)))
        basis_min_dot = min(basis_dots)
        direction_min_dot = min(direction_dots)

        # Acceleration / sprint / braking are exercised away from the NPC.
        self.player_pos = Vec3(-10.0, -10.0, 0.0)
        self.player_vel = Vec3(0,0,0); self.player_vel_z = 0.0
        self.on_ground = True; self.crouching = False; self.current_eye_height = STAND_EYE
        self.yaw = 0.0; self.pitch = 0.0
        self.keys = {'w'}
        walk_peak = 0.0
        for _ in range(20):
            self._update_player(dt); walk_peak = max(walk_peak, math.hypot(self.player_vel.x, self.player_vel.y))
        self.keys = {'w','shift'}
        sprint_peak = 0.0
        for _ in range(20):
            self._update_player(dt); sprint_peak = max(sprint_peak, math.hypot(self.player_vel.x, self.player_vel.y))
        self.keys.clear()
        for _ in range(20): self._update_player(dt)
        stop_speed = math.hypot(self.player_vel.x, self.player_vel.y)

        # Crouch must transition over several updates rather than snap in one frame.
        self.current_eye_height = STAND_EYE; self.on_ground = True; self.keys = {'control'}
        self._update_player(dt); crouch_first = self.current_eye_height
        for _ in range(3): self._update_player(dt)
        crouch_four = self.current_eye_height

        # Buffered jump request should produce the same established jump apex.
        self.player_pos = Vec3(-10.0,-10.0,0.0); self.player_vel = Vec3(0,0,0); self.player_vel_z=0.0
        self.on_ground=True; self.crouching=False; self.current_eye_height=STAND_EYE; self.keys.clear()
        self.jump(); jump_peak = 0.0
        for _ in range(120):
            self._update_player(dt); jump_peak=max(jump_peak,float(self.player_pos.z))
            if self.on_ground and jump_peak>0.0: break

        # Walking straight into the NPC must stop at the capsule radius without jittering inward.
        self.player_pos = Vec3(0.0,-1.25,0.0); self.player_vel = Vec3(0,0,0); self.player_vel_z=0.0
        self.on_ground=True; self.keys={'w'}; self.yaw=0.0
        collision_min=999.0
        for _ in range(30):
            self._update_player(dt)
            collision_min=min(collision_min,math.hypot(self.player_pos.x,self.player_pos.y))
        expected_stop=BODY_COLLISION_RADIUS+PLAYER_RADIUS

        ok=(spawn_dot>0.999 and basis_min_dot>0.999999 and direction_min_dot>0.999
            and yaw_pitch_drift<1e-9 and walk_peak>3.9 and sprint_peak>6.4 and stop_speed<0.01
            and CROUCH_EYE < crouch_first < STAND_EYE and crouch_four < crouch_first
            and 0.90 < jump_peak < 1.20 and collision_min >= expected_stop-1e-4)
        print('ASCII_MATTER_FPS_CONTROL_SMOKE='+('PASS' if ok else 'FAIL')
              + f' spawn_dot={spawn_dot:.6f} basis_min_dot={basis_min_dot:.6f}'
              + f' direction_min_dot={direction_min_dot:.6f} yaw_pitch_drift={yaw_pitch_drift:.6f}'
              + f' walk={walk_peak:.3f} sprint={sprint_peak:.3f} stop={stop_speed:.4f}'
              + f' crouch1={crouch_first:.3f} crouch4={crouch_four:.3f} jump_peak={jump_peak:.3f}'
              + f' collision_min={collision_min:.3f}')
        if not ok:
            raise RuntimeError('FPS_CONTROL_SMOKE_FAILED')
        self.userExit()

    def _pass37_smoke_step(self):
        if not ARGS.pass37_smoke or self.frame_count != 0: return
        dt=1.0/60.0; fov=float(self.camLens.getFov()[0])
        self.player_pos=Vec3(-12,-12,0); self.player_vel=Vec3(0,0,0); self.player_vel_z=0; self.on_ground=True; self.yaw=0; self.keys={'w','d'}
        diag=0.0
        for _ in range(30): self._update_player(dt); diag=max(diag,math.hypot(self.player_vel.x,self.player_vel.y))
        self.keys={'s'}; rev=0
        for i in range(30):
            self._update_player(dt)
            if self.player_vel.y<-.05: rev=i+1; break
        self.player_pos=Vec3(-12,-12,1); self.player_vel=Vec3(2.5,1,0); self.player_vel_z=0; self.on_ground=False; self.keys.clear(); before=Vec3(self.player_vel)
        for _ in range(8): self._update_player(dt)
        coast=(Vec3(self.player_vel.x,self.player_vel.y,0)-Vec3(before.x,before.y,0)).length()
        self.player_pos=Vec3(-12,-12,0); self.player_vel=Vec3(0,0,0); self.player_vel_z=0; self.on_ground=True; self.keys.clear(); self.jump(); peak=0; air=0
        for _ in range(120):
            self._update_player(dt); air+=dt; peak=max(peak,float(self.player_pos.z))
            if self.on_ground and peak>0: break
        ok=abs(fov-PLAYER_FOV_DEG)<.05 and 3.95<diag<=4.01 and 0<rev<=14 and coast<1e-6 and .98<peak<1.16 and air<.90
        print(f'ANATOMIC_PASS37_MOVEMENT_SMOKE={"PASS" if ok else "FAIL"} fov={fov:.2f} diag={diag:.3f} reverse_frames={rev} coast={coast:.6f} peak={peak:.3f} airtime={air:.3f}')
        if not ok: raise RuntimeError('PASS37_MOVEMENT_SMOKE_FAILED')
        self.userExit()

    def _set_internal_detail_visible(self, visible):
        visible=bool(visible)
        if visible == self.internal_detail_visible: return
        self.internal_detail_visible=visible
        nodes=list(self.skeleton_bones)+list(self.skeleton_joints)+list(self.skeleton_skull_parts)+list(self.organ_nodes)+list(self.neural_nodes)
        cut_nodes={self.skeleton_bone_nodes.get(name) for name in self.severed_bone_names}
        for n in nodes:
            if n is None or n.isEmpty(): continue
            if n in cut_nodes:
                n.hide(); continue
            n.show() if visible else n.hide()

    def _update_render_lod(self, dt, force=False):
        self.lod_clock += max(0.0,float(dt))
        if not force and self.lod_clock < .25: return
        self.lod_clock=0.0
        root=self.body_root.getPos(self.render); dist=math.hypot(self.player_pos.x-root.x,self.player_pos.y-root.y)
        new_tier=0 if dist <= LOD_FULL_DISTANCE else (1 if dist <= LOD_BAL_DISTANCE else 2)
        if new_tier != self.lod_tier or force:
            changed = new_tier != self.lod_tier
            self.lod_tier=new_tier
            if changed: self.perf_counters['lod_changes']+=1
            self._rebuild_all_glyph_batches()
            self._set_internal_detail_visible(new_tier<2)
            self.status_cache=None

    # ---------- FRAME ----------
    def update_embedded(self, dt):
        """Advance one HoloVerse-owned frame without creating an Anatomic task."""
        self._embedded_dt_override = max(0.0, min(float(dt), 1.0 / 20.0))
        try:
            self._update(None)
        finally:
            self._embedded_dt_override = None

    def _update(self, task):
        if self.frame_count == 0:
            _checkpoint('first_frame')
        elif self.frame_count == 3:
            _checkpoint('running')
        dt=min(self._embedded_dt_override if self._embedded_dt_override is not None else globalClock.getDt(), 1/20)
        self._update_audio()
        if ARGS.perf_smoke or ARGS.reverse_perf_smoke or ARGS.impact_smoke or ARGS.combat_smoke or ARGS.melee_smoke or ARGS.sword_smoke or ARGS.pass34_smoke or ARGS.pass34_proof or ARGS.pass37_smoke or ARGS.pass37_proof or ARGS.pass38_smoke or ARGS.pass39_smoke or ARGS.pass39_proof or ARGS.pass44_smoke or ARGS.pass44_proof or ARGS.pass45_smoke or ARGS.pass45_proof:
            dt=1.0/60.0
        if ARGS.fps_control_smoke:
            self._fps_control_smoke_step()
        if ARGS.pass37_smoke:
            self._pass37_smoke_step()
        elif not (ARGS.smoke_test or ARGS.test_shot or ARGS.pass34_smoke or ARGS.pass34_proof or ARGS.pass37_proof or ARGS.pass44_smoke or ARGS.pass44_proof or ARGS.pass45_smoke or ARGS.pass45_proof):
            if not (self.motion_forge_visible or self.combo_composer_visible):
                self._mouse_look()
                self._update_player(dt)
        # The head-track smoke drives player positions deterministically before
        # evaluating the real tracking code.  Fixed dt avoids software-renderer
        # frame rate changing the swivel result.
        self._head_track_smoke_step()
        self._arm_smoke_step()
        self._shoulder_smoke_step()
        self._walk_smoke_step()
        if not (ARGS.walk_smoke or ARGS.pass45_smoke or ARGS.pass45_proof):
            self._update_npc_walk(dt)
        self._update_shoulder_articulation(dt)
        self._update_arm_articulation(dt)
        track_dt = (1.0 / 30.0) if ARGS.head_track_smoke else dt
        self._update_head_tracking(track_dt)
        self._update_impact_reactions(dt)
        self.melee_peak_head_reaction=max(self.melee_peak_head_reaction,abs(self.impact_head_h)+abs(self.impact_head_p)+abs(self.impact_head_r))
        self._update_render_lod(dt)
        self._update_camera()
        self._update_viewmodels(dt)
        self._update_melee(dt)
        self._update_weapon_fire(dt)
        self._update_npc_stagger_and_defense(dt)
        self._update_detached_limbs(dt)
        if ARGS.audio_diagnostic:
            # Audible acceptance deliberately stacks several independent cues on the SAME frame.
            if self.frame_count == 4:
                self._play_weapon_sfx('left_fire')
                self._play_weapon_sfx('right_fire')
            elif self.frame_count == 8:
                self._play_weapon_sfx('left_arm_move')
                self._play_weapon_sfx('right_arm_move')
                self._play_weapon_sfx('sword_move')
            elif self.frame_count == 10:
                self._play_weapon_sfx('left_impact')
                self._play_weapon_sfx('right_impact')
                self._play_weapon_sfx('fist_impact')
                self._play_weapon_sfx('sword_impact')
                self._play_weapon_sfx('sword_move')
            elif self.frame_count == 50:
                print(f'ASCII_MATTER_AUDIO_DIAGNOSTIC=PASS backend={self.weapon_audio_backend} cues={len(self.weapon_sfx)} available={int(self.audio_available)}')
                self.userExit()
        if ARGS.melee_proof and self.frame_count == 2:
            self.player_pos=Vec3(0.0,-1.05,0.0); self._set_spawn_camera_facing_npc(); self._update_camera()
            self._set_combat_mode('melee',announce=False)
            self._begin_melee_charge('left')
            self.melee_hold_time['left']=1.0
            self.melee_cursor['left']=[-.72,-.42]
            self.melee_paths['left']=[(0.0,0.0),(-.18,-.08),(-.38,-.20),(-.58,-.34),(-.72,-.42)]
            self._rebuild_melee_trail('left')
        if ARGS.melee_impact_proof:
            if self.frame_count == 2:
                self.player_pos=Vec3(0.0,-0.92,0.0); self._set_spawn_camera_facing_npc(); self._update_camera()
                self._set_combat_mode('melee',announce=False)
                self.camera.lookAt(Vec3(0.0, 0.0, 1.79))
                impact_hpr=self.camera.getHpr(self.render)
                self.yaw=float(impact_hpr.x)%360.0
                self.pitch=max(-CAMERA_PITCH_LIMIT,min(CAMERA_PITCH_LIMIT,float(impact_hpr.y)))
                self.camera.setR(0.0)
                self._begin_melee_charge('right'); self.melee_hold_time['right']=1.20
                self.melee_cursor['right']=[-.12,-.60]
                self.melee_paths['right']=[(0.0,0.0),(.78,-.18),(.92,-.34),(.55,-.46),(.18,-.54),(-.12,-.60)]
                self._finish_melee_charge('right')
        if ARGS.melee_smoke:
            if self.frame_count == 2:
                self.player_pos=Vec3(0.0,-0.92,0.0); self._set_spawn_camera_facing_npc(); self._update_camera()
                self._set_combat_mode('melee',announce=False)
                if ARGS.melee_smoke:
                    hp=[self._current_glyph_world_pos(i) for i in range(len(self.live)) if self.live[i] and self._impact_region(i)=='head']
                    if hp: print(f'ANATOMIC_HEAD_BOUNDS x=({min(p.x for p in hp):.3f},{max(p.x for p in hp):.3f}) y=({min(p.y for p in hp):.3f},{max(p.y for p in hp):.3f}) z=({min(p.z for p in hp):.3f},{max(p.z for p in hp):.3f}) n={len(hp)}')
                self._begin_melee_charge('left'); self.melee_hold_time['left']=.06; self._finish_melee_charge('left')
            elif self.frame_count == 18:
                # Aim the actual first-person camera at the head before the charged hook.
                # This proves head contact through the same camera-space IK a player uses,
                # rather than manufacturing a world-space hit in the validator.
                self.camera.lookAt(Vec3(0.0, 0.0, 1.79))
                head_hpr=self.camera.getHpr(self.render)
                self.yaw=float(head_hpr.x)%360.0
                self.pitch=max(-CAMERA_PITCH_LIMIT,min(CAMERA_PITCH_LIMIT,float(head_hpr.y)))
                self.camera.setR(0.0)
                self._begin_melee_charge('right'); self.melee_hold_time['right']=1.15
                self.melee_cursor['right']=[-.12,-.60]
                self.melee_paths['right']=[(0.0,0.0),(.78,-.18),(.92,-.34),(.55,-.46),(.18,-.54),(-.12,-.60)]
                self._finish_melee_charge('right')
            elif self.frame_count == 50:
                melee_wounds=[w for w in self.wounds if (w.outer_color-MEMORY_WOUND_RED).lengthSquared()>1e-5]
                left_digits=self.melee_root.findAllMatches('**/left_finger_*').getNumPaths() if self.melee_root is not None else 0
                right_digits=self.melee_root.findAllMatches('**/right_finger_*').getNumPaths() if self.melee_root is not None else 0
                left_thumb=self.melee_root.findAllMatches('**/left_thumb*').getNumPaths() if self.melee_root is not None else 0
                right_thumb=self.melee_root.findAllMatches('**/right_thumb*').getNumPaths() if self.melee_root is not None else 0
                detail_ok=(left_digits>=16 and right_digits>=16 and left_thumb>=3 and right_thumb>=3)
                ok=(self.combat_mode=='melee' and bool(self.melee_arms) and detail_ok and len(self.fragments)>0 and len(melee_wounds)>0
                    and (self.npc_stagger_velocity.length()>0.001 or self.npc_defense_timer>0.0)
                    and abs(self.impact_body_p)+abs(self.impact_head_p)>0.05 and self.melee_head_hits>=1 and self.melee_peak_head_reaction>0.25)
                print(f'ANATOMIC_MELEE_SMOKE={"PASS" if ok else "FAIL"} fragments={len(self.fragments)} melee_wounds={len(melee_wounds)} stagger={self.npc_stagger_velocity.length():.3f} defense={self.npc_defense_timer:.3f} body={self.impact_body_p:.3f} head_now={self.impact_head_p:.3f} head_hits={self.melee_head_hits} body_hits={self.melee_body_hits} head_peak={self.melee_peak_head_reaction:.3f} left_digits={left_digits} right_digits={right_digits} left_thumb={left_thumb} right_thumb={right_thumb}')
                if not ok: raise RuntimeError('MELEE_SMOKE_FAILED')
                self.userExit()
        if ARGS.sword_smoke:
            if self.frame_count == 2:
                # More distant than a reliable punch, but inside the sword's combined arm+blade reach.
                self.player_pos=Vec3(0.0,-1.15,0.0); self._set_spawn_camera_facing_npc(); self._update_camera()
                self._set_combat_mode('melee',announce=False)
                target=_v3(self.rig_joints['left_elbow'].getPos(self.render)); self.camera.lookAt(target)
                hpr=self.camera.getHpr(self.render); self.yaw=float(hpr.x)%360.0; self.pitch=max(-CAMERA_PITCH_LIMIT,min(CAMERA_PITCH_LIMIT,float(hpr.y))); self.camera.setR(0)
                # Search a tiny deterministic set of legal IK poses for the one whose physical
                # blade segment best intersects the authored elbow target. This is validation only.
                best=None
                for tx in (-.34,-.18,.0,.18,.34,.46):
                    for ty in (.54,.64,.74,.80):
                        for tz in (-.34,-.22,-.10,.02,.14):
                            pose=Vec3(tx,ty,tz); self._update_melee_pose('right',pose); bb,tt=self._sword_blade_world()
                            dd=self._point_segment_distance(target,bb,tt)
                            if best is None or dd<best[0]: best=(dd,pose,bb,tt)
                _,best_pose,b1,t1=best
                pre=Vec3(min(.48,best_pose.x+.28),best_pose.y,max(-.36,min(.18,best_pose.z+.18))); self._update_melee_pose('right',pre); b0,t0=self._sword_blade_world()
                self._update_melee_pose('right',best_pose); b1,t1=self._sword_blade_world(); fist1=_v3(self.melee_arms['right']['strike_tip'].getPos(self.render))
                sword_extra=(t1-fist1).length()
                print(f'ANATOMIC_SWORD_GEOM target=({target.x:.3f},{target.y:.3f},{target.z:.3f}) best={best[0]:.3f} pose=({best_pose.x:.2f},{best_pose.y:.2f},{best_pose.z:.2f}) b1=({b1.x:.3f},{b1.y:.3f},{b1.z:.3f}) t1=({t1.x:.3f},{t1.y:.3f},{t1.z:.3f})')
                hit=self._apply_sword_hit(b0,t0,b1,t1,.86,.72)
                limb=self.detached_limbs[0] if self.detached_limbs else None
                connected=[i for i,b in enumerate(self.body_bindings) if limb is not None and b in limb.descendants and self.live[i]]
                connected_idx=connected[0] if connected else None
                self.sword_test_state={'hit':bool(hit),'sword_extra':sword_extra,'cut':self.sword_last_cut_bone,'limbs':len(self.detached_limbs),
                                       'cut_count':self.sword_cut_count,'connected_count':len(connected),'connected_idx':connected_idx,
                                       'connected_origin':_v3(self.glyph_nodes[connected_idx].getPos(self.render)) if connected_idx is not None else Vec3(0,0,0),
                                       'cut_origin':_v3(limb.root.getPos(self.render)) if limb is not None else Vec3(0,0,0)}
            elif self.frame_count == 28 and self.sword_test_state:
                st=self.sword_test_state
                st['fall_distance']=(_v3(self.detached_limbs[0].root.getPos(self.render))-st['cut_origin']).length() if self.detached_limbs else 0.0
                ci=st.get('connected_idx'); st['ascii_fall']=(_v3(self.glyph_nodes[ci].getPos(self.render))-st['connected_origin']).length() if ci is not None else 0.0
                self.keys.add('r')
            elif self.frame_count == 62 and self.sword_test_state:
                st=self.sword_test_state
                reattached=(not self.detached_limbs and not self.severed_bone_names and not self.detached_joint_names)
                restored=(not self.fragments and not self.wounds)
                ok=(st['hit'] and st['sword_extra']>.70 and st['cut_count']>=1 and st['limbs']>=1 and st.get('connected_count',0)>0
                    and st.get('fall_distance',0)>.01 and st.get('ascii_fall',0)>.01 and reattached and restored)
                print(f'ANATOMIC_SWORD_SMOKE={"PASS" if ok else "FAIL"} hit={int(st["hit"])} extra_reach={st["sword_extra"]:.3f} cut={st["cut"]} cut_count={st["cut_count"]} limbs={st["limbs"]} connected_ascii={st.get("connected_count",0)} fall={st.get("fall_distance",0):.3f} ascii_fall={st.get("ascii_fall",0):.3f} reattached={int(reattached)} restored={int(restored)}')
                if not ok: raise RuntimeError('SWORD_DISMEMBER_SMOKE_FAILED')
                self.userExit()
        if ARGS.pass34_smoke and self.frame_count == 2:
            # Pass 34 acceptance runs through the live Panda3D camera-space arm solver.
            self.player_pos=Vec3(0.0,-1.18,0.0); self._set_spawn_camera_facing_npc(); self._update_camera()
            self._set_combat_mode('melee',announce=False)
            side='right'
            self._begin_melee_charge(side)
            self.melee_cursor[side]=[.42,-.24]
            self.melee_paths[side]=[(0.0,0.0),(.16,-.05),(.31,-.12),(.42,-.24)]
            self.melee_hold_time[side]=0.0
            neutral=_v3(self._melee_target_from_cursor(side))
            self.melee_hold_time[side]=MELEE_FULL_CHARGE_TIME
            extended=_v3(self._melee_target_from_cursor(side))
            reach_gain=extended.y-neutral.y
            # Compare the final committed segment against the live NPC target in camera space.
            sign=1.0
            outward=Vec3(sign*max(MELEE_OUTWARD_ARC_X,abs(extended.x)),min(.76,extended.y+.08),extended.z)
            enemy_local=_v3(self.camera.getRelativePoint(self.render,self.body_root.getPos(self.render)+Vec3(0,0,1.22)))
            commit=_v3(self._melee_enemy_commit_target(side,outward,1.0))
            fallback_distance=(outward-enemy_local).length(); commit_distance=(commit-enemy_local).length()
            # Same held target, with and without sword-hold wrist treatment.
            self.melee_hold[side]=False; self._update_melee_pose(side,extended); unheld_p=float(self.melee_arms[side]['fist'].getP())
            self.melee_hold[side]=True; self._update_melee_pose(side,extended); held_p=float(self.melee_arms[side]['fist'].getP())
            wrist_delta=((held_p-unheld_p+180.0)%360.0)-180.0
            hfov=float(self.camLens.getHfov())
            ok=(abs(hfov-PLAYER_FOV_DEG)<.05 and reach_gain>.14 and commit.y>outward.y+.03
                and commit_distance+0.05<fallback_distance and wrist_delta<-3.5)
            print(f'ANATOMIC_PASS34_SMOKE={"PASS" if ok else "FAIL"} fov={hfov:.2f} reach_gain={reach_gain:.3f} outward_y={outward.y:.3f} commit_y={commit.y:.3f} fallback_dist={fallback_distance:.3f} commit_dist={commit_distance:.3f} wrist_delta={wrist_delta:.2f}')
            if not ok: raise RuntimeError('PASS34_ASSISTED_REACH_SMOKE_FAILED')
            self.userExit()
        if ARGS.pass38_smoke and self.frame_count == 2:
            self.player_pos=Vec3(0.0,-1.30,0.0); self._set_spawn_camera_facing_npc(); self._update_camera(); self._set_combat_mode('melee',announce=False)
            side='right'; self._begin_melee_charge(side); self.melee_hold_time[side]=MELEE_FULL_CHARGE_TIME
            self.melee_cursor[side]=[.48,-.30]; self.melee_paths[side]=[(0.0,0.0),(.14,-.04),(.31,-.14),(.48,-.30)]
            release=_v3(self._melee_target_from_cursor(side)); self._update_melee_pose(side,release); release_hpr=_v3(self.melee_arms[side]['fist'].getHpr())
            self._finish_melee_charge(side); pb=self.melee_playback[side]
            origin_error=(_v3(pb['targets'][0])-release).length(); first_jump=(_v3(pb['targets'][0])-release).length()
            old_hpr=_v3(self.melee_arms[side]['fist'].getHpr()); self._update_melee_pose(side,pb['targets'][1]); self._preserve_melee_release_orientation(side,pb,.42); env=self._apply_sword_flurry_rotation(side,pb,.32); spun_hpr=_v3(self.melee_arms[side]['fist'].getHpr())
            orientation_delta=(spun_hpr-old_hpr).length(); reset_distance=(_v3(pb['targets'][0])-Vec3(MELEE_NEUTRAL_X,MELEE_NEUTRAL_Y,-.18)).length()
            commit=_v3(pb['targets'][3]); outward=_v3(pb['targets'][2])
            ok=(origin_error<1e-5 and first_jump<1e-5 and reset_distance>.12 and len(pb['targets'])>=6 and env>.45 and orientation_delta>12.0 and commit.y>=outward.y-.02 )
            print(f'ANATOMIC_PASS38_SMOKE={"PASS" if ok else "FAIL"} origin_error={origin_error:.6f} release_from_neutral={reset_distance:.3f} targets={len(pb["targets"])} flurry_env={env:.3f} wrist_delta={orientation_delta:.2f} outward_y={outward.y:.3f} commit_y={commit.y:.3f}')
            if not ok: raise RuntimeError('PASS38_RELEASE_ORIGIN_FLURRY_SMOKE_FAILED')
            self.userExit()
        if ARGS.pass42_smoke and self.frame_count == 2:
            self.player_pos=Vec3(0.0,-1.28,0.0); self._set_spawn_camera_facing_npc(); self._update_camera(); self._set_combat_mode('melee',announce=False)
            # Synthetic local blade sweeps prove that velocity, edge alignment, flat alignment and leverage
            # independently affect the bounded dynamic factors before the live collision path is exercised.
            self._update_melee_pose('right',Vec3(.25,.66,-.16)); b1,t1=self._sword_blade_world()
            edge_axis=_v3(self.render.getRelativeVector(self.sword_root,Vec3(1,0,0))); edge_axis.normalize()
            flat_axis=_v3(self.render.getRelativeVector(self.sword_root,Vec3(0,0,1))); flat_axis.normalize()
            blade_dir=_v3(t1-b1); blade_dir.normalize()
            dtp=1.0/60.0
            fast_delta=edge_axis*.105; slow_delta=edge_axis*.012; flat_delta=flat_axis*.105; thrust_delta=blade_dir*.105
            fast=self._sword_motion_dynamics(b1-fast_delta,t1-fast_delta,b1,t1,dtp,t1-blade_dir*.10)
            slow=self._sword_motion_dynamics(b1-slow_delta,t1-slow_delta,b1,t1,dtp,t1-blade_dir*.10)
            flat=self._sword_motion_dynamics(b1-flat_delta,t1-flat_delta,b1,t1,dtp,t1-blade_dir*.10)
            thrust=self._sword_motion_dynamics(b1-thrust_delta,t1-thrust_delta,b1,t1,dtp,t1-blade_dir*.08)
            root_contact=self._sword_motion_dynamics(b1-fast_delta,t1-fast_delta,b1,t1,dtp,b1+blade_dir*.10)
            tip_contact=self._sword_motion_dynamics(b1-fast_delta,t1-fast_delta,b1,t1,dtp,t1-blade_dir*.05)
            # Real body contact path: choose a torso glyph and sweep the blade through it along its true edge axis.
            idx=next(i for i,b in enumerate(self.body_bindings) if b in ('chest','spine_high','spine_mid') and self.live[i])
            point=self._current_glyph_world_pos(idx); blade_center=(b1+t1)*.5; shift=point-blade_center
            cb1=b1+shift; ct1=t1+shift; cb0=cb1-edge_axis*.090; ct0=ct1-edge_axis*.090
            before=self.npc_stagger_velocity.length(); hit=self._apply_sword_hit(cb0,ct0,cb1,ct1,.92,.80,dtp); after=self.npc_stagger_velocity.length(); live=dict(self.sword_last_dynamics)
            ok=(fast['speed']>slow['speed']*3.0 and fast['impact']>slow['impact']+.45 and fast['cut']>flat['cut']+.35
                and thrust['type']=='THRUST' and tip_contact['lever']>root_contact['lever']+.55 and tip_contact['impact']>root_contact['impact']+.18
                and hit and after>before and live['speed']>2.5 and live['impact']>.75)
            print(f"ANATOMIC_PASS42_SMOKE={'PASS' if ok else 'FAIL'} fast={fast['speed']:.2f}/{fast['impact']:.2f}/{fast['cut']:.2f} slow={slow['speed']:.2f}/{slow['impact']:.2f}/{slow['cut']:.2f} flat_cut={flat['cut']:.2f} thrust={thrust['type']} lever={root_contact['lever']:.2f}->{tip_contact['lever']:.2f} live={live['type']}:{live['speed']:.2f}:{live['impact']:.2f} stagger={after-before:.3f}")
            if not ok: raise RuntimeError('PASS42_MOTION_DYNAMICS_SMOKE_FAILED')
            self.userExit()
        if ARGS.pass41_smoke and self.frame_count == 2:
            self.player_pos=Vec3(0.0,-1.45,0.0); self._set_spawn_camera_facing_npc(); self._update_camera(); self._set_combat_mode('melee',announce=False)
            side='right'; self._begin_melee_charge(side)
            for i in range(82):
                t=i/60.0; u=i/81.0
                self.melee_hold_time[side]=t; self.melee_cursor[side]=[-.58+.98*u,.22*math.sin(u*math.pi*1.35)]
                target=self._melee_target_from_cursor(side); self._update_melee_pose(side,target); self._capture_melee_motion_sample(side,t,True); self.melee_recordings[side].append((t,*self.melee_cursor[side]))
            self.melee_hold_time[side]=81/60.0; self._finish_melee_charge(side); pb=self.melee_playback[side]
            probe_t=.43; pb['elapsed']=probe_t/max(1e-6,pb['speed'])
            for _ in range(4): self._update_melee_body_solver(1.0/60.0)
            sample=self._sample_recorded_motion(pb['samples'],probe_t); target,hpr,_=sample
            hand_target_before=_v3(target); self._update_melee_pose(side,target); self.melee_arms[side]['fist'].setHpr(hpr); hand_target_after=_v3(self.melee_arms[side]['fist'].getPos(self.melee_root))
            left_sh=self._body_solver_shoulder('left'); right_sh=self._body_solver_shoulder('right'); base_l=_v3(self.melee_arms['left']['base_shoulder']); base_r=_v3(self.melee_arms['right']['base_shoulder'])
            shoulder_motion=max((left_sh-base_l).length(),(right_sh-base_r).length()); torso_raw=self.melee_body_solver['torso_h']; torso=abs(torso_raw); hip=self.melee_body_solver['hip_h']; elbow_support=abs(self.melee_body_solver['elbow_x'])+abs(self.melee_body_solver['elbow_z']); exact=(hand_target_after-hand_target_before).length()
            self.melee_playback[side]=None
            for _ in range(40): self._update_melee_body_solver(1.0/60.0)
            rest=max(abs(float(v)) for k,v in self.melee_body_solver.items() if k!='intensity'); opposite=(torso_raw*hip)<=0.0
            ok=(exact<1e-6 and shoulder_motion>.012 and torso>1.0 and abs(hip)>.5 and opposite and elbow_support>.006 and rest<.04)
            print(f'ANATOMIC_PASS41_SMOKE={"PASS" if ok else "FAIL"} hand_error={exact:.7f} shoulder={shoulder_motion:.4f} torso_h={torso:.2f} hip_h={hip:.2f} elbow_support={elbow_support:.3f} rest={rest:.4f}')
            if not ok: raise RuntimeError('PASS41_BODY_SOLVER_SMOKE_FAILED')
            self.userExit()
        if ARGS.pass40_smoke and self.frame_count == 2:
            self.player_pos=Vec3(0.0,-1.30,0.0); self._set_spawn_camera_facing_npc(); self._update_camera(); self._set_combat_mode('melee',announce=False)
            side='right'; self._begin_melee_charge(side)
            # Deliberate multi-direction gesture with enough duration to prove source timing.
            for i in range(91):
                self.melee_hold_time[side]=i/60.0
                a=i/90.0*math.pi*2.1
                self.melee_cursor[side]=[.42*math.sin(a),.30*math.sin(a*1.7)]
                target=self._melee_target_from_cursor(side); self._update_melee_pose(side,target); self._capture_melee_motion_sample(side,i/60.0,True)
                self.melee_recordings[side].append((i/60.0,*self.melee_cursor[side]))
            self.melee_hold_time[side]=1.50; self._finish_melee_charge(side); rec=self.melee_last_recording['right']; pb=self.melee_playback['right']
            original_duration=rec['duration']; replay_duration=pb['duration']/pb['speed']
            start_target=_v3(rec['samples'][0]['target']); playback_start=_v3(pb['samples'][0]['target'])
            # Save, then replay through the same context-aware number path.
            prior_slot=self._copy_melee_recording(self.melee_slots.get(4)) if self.melee_slots.get(4) else None
            prior_file=MELEE_SLOT_PATH.read_bytes() if MELEE_SLOT_PATH.exists() else None
            try:
                self._number_key(4); saved=(4 in self.melee_slots and not self.melee_pending_slot_save)
                self.melee_playback['right']=None
                # Move/turn before slot playback. Stored motion must remain camera-local and identical.
                self.player_pos=Vec3(3.5,-2.0,0.0); self.yaw=137.0; self._update_camera(); self._number_key(4)
                slot_pb=self.melee_playback['right']; slot_ok=bool(slot_pb and slot_pb.get('source')=='slot_4')
                slot_local_ok=slot_ok and (_v3(slot_pb['samples'][37]['target'])-_v3(rec['samples'][37]['target'])).length()<1e-6 and (_v3(slot_pb['samples'][37]['hpr'])-_v3(rec['samples'][37]['hpr'])).length()<1e-6
            finally:
                if prior_slot is None: self.melee_slots.pop(4,None)
                else: self.melee_slots[4]=prior_slot
                if prior_file is None:
                    try: MELEE_SLOT_PATH.unlink(missing_ok=True)
                    except Exception: pass
                else:
                    MELEE_SLOT_PATH.parent.mkdir(parents=True,exist_ok=True); MELEE_SLOT_PATH.write_bytes(prior_file)
            # Build an actual swept blade field and verify the render node exists.
            self.sword_distortion_history=[
                (self.melee_time-.030,Vec3(.20,.28,-.20),Vec3(.20,1.00,-.20),4.0),
                (self.melee_time-.015,Vec3(.24,.31,-.17),Vec3(.31,1.04,-.08),5.4),
                (self.melee_time,Vec3(.29,.34,-.13),Vec3(.43,1.08,.05),6.1),
            ]
            self._rebuild_sword_distortion(); distortion_ok=self.sword_distortion_node is not None and not self.sword_distortion_node.isEmpty()
            # Apply one deterministic sword reaction and compare it with the old Pass39 base constants.
            before=self.npc_stagger_velocity.length(); idx=next(i for i,b in enumerate(self.body_bindings) if b in ('chest','spine_high','spine_mid'))
            self._apply_impact_reaction(idx,Vec3(0,1,0),'SWORD'); after=self.npc_stagger_velocity.length()
            impact_ok=(after-before)>=1.60
            ok=(len(rec['samples'])>=80 and abs(replay_duration-original_duration/1.5)<.01 and (start_target-playback_start).length()<1e-6 and saved and slot_ok and slot_local_ok and distortion_ok and impact_ok and SWORD_IMPACT_MULTIPLIER==2.0)
            print(f'ANATOMIC_PASS40_SMOKE={"PASS" if ok else "FAIL"} samples={len(rec["samples"])} recorded={original_duration:.3f} replay={replay_duration:.3f} speed={pb["speed"]:.2f} slot4={int(saved and slot_ok)} local={int(slot_local_ok)} distortion={int(distortion_ok)} impact_delta={after-before:.3f}')
            if not ok: raise RuntimeError('PASS40_RECORDED_SLOT_DISTORTION_SMOKE_FAILED')
            self.userExit()
        if ARGS.pass39_smoke and self.frame_count == 2:
            self.player_pos=Vec3(0.0,-1.28,0.0); self._set_spawn_camera_facing_npc(); self._update_camera(); self._set_combat_mode('melee',announce=False)
            side='left'; self._begin_melee_charge(side)
            # Record a long multi-turn hold path that exceeds the historical 28-point limit.
            for i in range(96):
                self.melee_hold_time[side]=i/60.0
                dx=math.sin(i*.31)*4.2; dy=math.cos(i*.23)*3.6
                self._record_melee_delta(dx,dy)
            self.melee_hold_time[side]=1.62
            release=_v3(self._melee_target_from_cursor(side)); self._finish_melee_charge(side); pb=self.melee_playback[side]
            rec=pb.get('recorded_path',()); full_ok=(len(rec)>28 and abs(rec[0][1])<1e-6 and abs(rec[0][2])<1e-6 and pb.get('recorded_duration',0)>=1.6)
            fov=float(self.camLens.getHfov())
            # Direct deterministic melee wound proves spill and dramatic reaction without depending on frame-rate contact timing.
            hit_idx=next(i for i,b in enumerate(self.body_bindings) if b in ('chest','spine_high','spine_mid'))
            hit_point=self._current_glyph_world_pos(hit_idx); self.damage_at(hit_point,.22,8,hit_index=hit_idx,wound_outer=MELEE_OUTER_PURPLE,wound_core=MELEE_CORE_RED,impulse_scale=1.0,incoming_world=Vec3(0,1,.05),mode='MELEE_CHARGED')
            self._apply_impact_reaction(hit_idx,Vec3(0,1,.05),'MELEE_CHARGED'); self._advance_wound_memory(.20)
            spill_ok=(len(self.wound_ascii)>=5 and all(p.glyph in WOUND_ASCII_GLYPHS for p in self.wound_ascii))
            impact_speed=self.npc_stagger_velocity.length()
            ok=(abs(fov-88.0)<.05 and full_ok and (_v3(pb['targets'][0])-release).length()<1e-5 and spill_ok and impact_speed>.75 and MELEE_PUNCH_RADIUS>=.17 and SWORD_CUT_RADIUS>=.07)
            print(f'ANATOMIC_PASS39_SMOKE={"PASS" if ok else "FAIL"} fov={fov:.2f} recorded={len(rec)} duration={pb.get("recorded_duration",0):.3f} travel={pb.get("recorded_travel",0):.3f} release_error={(_v3(pb["targets"][0])-release).length():.6f} spill={len(self.wound_ascii)} stagger={impact_speed:.3f} punch_radius={MELEE_PUNCH_RADIUS:.3f} sword_radius={SWORD_CUT_RADIUS:.3f}')
            if not ok: raise RuntimeError('PASS39_FULL_PATH_IMPACT_SPILL_SMOKE_FAILED')
            self.userExit()
        if ARGS.pass43_smoke and self.frame_count == 2:
            self._set_combat_mode('melee',announce=False); samples=[]
            for i in range(61):
                t=i/60.0; u=i/60.0; samples.append({'t':t,'target':Vec3(MELEE_NEUTRAL_X+.25*math.sin(u*math.tau),MELEE_NEUTRAL_Y+.20*u,-.18+.18*math.sin(u*math.pi)),'hpr':Vec3(18*math.sin(u*math.tau),-8+16*u,35*math.sin(u*math.tau))})
            rec={'side':'right','duration':1.0,'travel':1.74,'samples':samples,'name':'ARC CUT','playback_speed':1.5,'trim_start':0.0,'trim_end':0.0,'mirrored':False}
            self.melee_slots[4]=self._copy_melee_recording(rec); raw_before=self._serialize_melee_recording(self.melee_slots[4])['samples']; self.motion_forge_slot=4; self.motion_forge_visible=True
            self._forge_trim_start(); self._forge_trim_end(); self._forge_speed_delta(.30); self._forge_mirror(); self._forge_commit_name('ARC CUT PRIME')
            eff=self._effective_melee_recording(self.melee_slots[4]); raw_after=self._serialize_melee_recording(self.melee_slots[4])['samples']
            ok=bool(eff and raw_before==raw_after and abs(eff['duration']-.90)<.011 and abs(eff['playback_speed']-1.80)<.001 and eff['mirrored'] and self.melee_slots[4]['name']=='ARC CUT PRIME')
            started=self._start_recorded_melee_playback(self.melee_slots[4],source='forge_smoke'); forge_pb=self.melee_playback.get('right')
            playback_ok=bool(started and forge_pb and abs(float(forge_pb.get('speed',0))-1.80)<.001 and abs(float(forge_pb.get('duration',0))-.90)<.011 and (_v3(forge_pb['samples'][0]['target'])-_v3(eff['samples'][0]['target'])).length()<1e-7)
            ok=ok and playback_ok
            self._forge_reset_edits(); reset=self.melee_slots[4]; ok=ok and abs(reset['trim_start'])<1e-9 and abs(reset['trim_end'])<1e-9 and not reset['mirrored'] and abs(reset['playback_speed']-1.5)<1e-9
            print(f"ANATOMIC_PASS43_SMOKE={'PASS' if ok else 'FAIL'} samples={len(raw_before)} immutable={int(raw_before==raw_after)} effective={eff['duration'] if eff else -1:.3f} speed={eff['playback_speed'] if eff else -1:.2f} mirror={int(bool(eff and eff['mirrored']))} playback={int(playback_ok)} name={self.melee_slots[4]['name']}")
            if not ok: raise RuntimeError('PASS43_MOTION_FORGE_SMOKE_FAILED')
            self.motion_forge_visible=False
            self.userExit()
        if ARGS.pass45_smoke and self.frame_count == 2:
            required=('left_hip','right_hip','left_knee','right_knee','left_ankle','right_ankle','left_foot','right_foot')
            if not self.rig_joints or not all(n in self.rig_joints for n in required): raise RuntimeError('PASS45_REQUIRES_LEG_RIG')
            # Establish authored contact planes in neutral stance.
            self.body_root.setPos(0,0,self.npc_walk_base_z); self.body_root.setH(0)
            for n in required: self.rig_joints[n].setHpr(0,0,0)
            self.npc_walk_contact_z={'left':float(self.rig_joints['left_foot'].getZ(self.render)),'right':float(self.rig_joints['right_foot'].getZ(self.render))}
            # Left early/mid swing: thigh is forward, knee must bend opposite the elbow sign, foot may droop slightly.
            self.npc_walk_blend=1.0; self.npc_walk_phase=math.pi*(1.0+NPC_KNEE_PEAK_SWING); self._apply_walk_gait(0.0,True)
            l=self.npc_walk_debug['left']; r=self.npc_walk_debug['right'];
            left_knee=float(self.rig_joints['left_knee'].getP()); left_knee_h=float(self.rig_joints['left_knee'].getH()); left_knee_r=float(self.rig_joints['left_knee'].getR())
            left_foot_pitch=float(self.rig_joints['left_foot'].getP(self.render)); right_contact_err=abs(float(self.rig_joints['right_foot'].getZ(self.render))-float(self.npc_walk_contact_z['right']))
            # Terminal left swing must extend and flatten before plant.
            self.npc_walk_phase=math.pi*(1.0+.92); self._apply_walk_gait(0.0,True)
            terminal_knee=abs(float(self.rig_joints['left_knee'].getP())); terminal_pitch=abs(float(self.rig_joints['left_foot'].getP(self.render)))
            # Mirror check on right leg.
            self.npc_walk_phase=math.pi*NPC_KNEE_PEAK_SWING; self._apply_walk_gait(0.0,True)
            right_knee=float(self.rig_joints['right_knee'].getP()); right_knee_h=float(self.rig_joints['right_knee'].getH()); right_knee_r=float(self.rig_joints['right_knee'].getR())
            right_foot_pitch=float(self.rig_joints['right_foot'].getP(self.render)); left_contact_err=abs(float(self.rig_joints['left_foot'].getZ(self.render))-float(self.npc_walk_contact_z['left']))
            hierarchy_ok=(self.rig_parent_names.get('left_knee')=='left_hip' and self.rig_parent_names.get('left_ankle')=='left_knee' and self.rig_parent_names.get('left_foot')=='left_ankle' and self.rig_parent_names.get('left_elbow')=='left_shoulder' and self.rig_parent_names.get('left_wrist')=='left_elbow')
            ok=(left_knee>30.0 and right_knee>30.0 and abs(left_knee_h)<1e-6 and abs(left_knee_r)<1e-6 and abs(right_knee_h)<1e-6 and abs(right_knee_r)<1e-6 and 1.0<abs(left_foot_pitch)<=NPC_ANKLE_DROOP_DEG+1.0 and 1.0<abs(right_foot_pitch)<=NPC_ANKLE_DROOP_DEG+1.0 and terminal_knee<8.0 and terminal_pitch<0.35 and right_contact_err<0.001 and left_contact_err<0.001 and hierarchy_ok)
            print(f"ANATOMIC_PASS45_GAIT_SMOKE={'PASS' if ok else 'FAIL'} left_knee={left_knee:.2f} right_knee={right_knee:.2f} left_droop={left_foot_pitch:.2f} right_droop={right_foot_pitch:.2f} terminal_knee={terminal_knee:.2f} terminal_foot={terminal_pitch:.3f} contact={max(left_contact_err,right_contact_err):.6f} hierarchy={int(hierarchy_ok)}")
            if not ok: raise RuntimeError('PASS45_GROUNDED_GAIT_SMOKE_FAILED')
            self.userExit()
        if ARGS.pass45_proof and self.frame_count == 2:
            # Freeze the NPC in a readable left-leg swing from the side.  Camera is placed
            # perpendicular to the authored -Y forward axis so knee direction and foot pitch
            # can be judged without perspective ambiguity.
            self.npc_walk_blend=1.0; self.npc_walk_phase=math.pi*(1.0+NPC_KNEE_PEAK_SWING); self._apply_walk_gait(0.0,True)
            self.player_pos=Vec3(2.35,0.0,0.0); self.camera.setPos(2.35,-.02,1.04); self.camera.lookAt(Vec3(0,0,0.88)); hpr=self.camera.getHpr(self.render); self.yaw=float(hpr.x)%360.0; self.pitch=float(hpr.y); self.camera.setR(0)
            self.cross.hide(); self.status.hide(); self.hint.hide()
            if self.weapon_root is not None: self.weapon_root.hide()
            if self.melee_root is not None: self.melee_root.hide()
            self._set_internal_detail_visible(True); self.pass45_proof_state=True
        if ARGS.pass44_smoke and self.frame_count == 2:
            self._set_combat_mode('melee',announce=False)
            def mk(slot,phase,name,speed):
                samples=[]
                for i in range(61):
                    t=i/60.0; u=i/60.0
                    samples.append({'t':t,'target':Vec3(MELEE_NEUTRAL_X+.20*math.sin(u*math.tau+phase),MELEE_NEUTRAL_Y+.12*u+.035*slot,-.18+.15*math.sin(u*math.pi+phase*.35)),'hpr':Vec3(20*math.sin(u*math.tau+phase),-10+18*u,32*math.sin(u*math.tau+phase*.65))})
                self.melee_slots[slot]={'side':'right','duration':1.0,'travel':1.4+.1*slot,'samples':samples,'name':name,'playback_speed':speed,'trim_start':0.0,'trim_end':0.0,'mirrored':False}
            mk(1,0.0,'ARC CUT',1.50); mk(2,.85,'RISING CUT',1.70); mk(3,1.55,'THRUST LOOP',1.35)
            before={k:self._serialize_melee_recording(v)['samples'] for k,v in self.melee_slots.items() if k in (1,2,3)}
            combo={'name':'TRINITY FLOW','sequence':[1,2,3]}; self.melee_combos[2]=combo; self.active_combo_slot=2
            compiled=self._compile_melee_combo(combo); after={k:self._serialize_melee_recording(v)['samples'] for k,v in self.melee_slots.items() if k in (1,2,3)}
            immutable=(before==after); windows=list(compiled.get('combo_windows',())) if compiled else []; bridges=list(compiled.get('transition_ranges',())) if compiled else []
            bridge_gate=True
            for a,b in bridges:
                mid=(a+b)*.5
                if any(float(w['start'])<=mid<=float(w['end']) for w in windows): bridge_gate=False
            local_before=[(_v3(q['target']),_v3(q['hpr'])) for q in compiled['samples']] if compiled else []
            self.player_pos=Vec3(7.0,-4.0,0.0); self.yaw=123.0
            compiled_again=self._compile_melee_combo(combo); local_after=[(_v3(q['target']),_v3(q['hpr'])) for q in compiled_again['samples']] if compiled_again else []
            local_ok=(len(local_before)==len(local_after) and all((a[0]-b[0]).length()<1e-8 and (a[1]-b[1]).length()<1e-8 for a,b in zip(local_before,local_after)))
            started=self._start_combo_playback(2,source='pass44_smoke'); pb=self.melee_playback.get('right'); playback_ok=bool(started and pb and len(pb.get('combo_windows',()))==3 and len(pb.get('transition_ranges',()))==2 and abs(float(pb.get('speed',0))-1.0)<1e-9)
            first_bridge_mid=sum(bridges[0])*.5 if bridges else -1.0; first_move_mid=(windows[0]['start']+windows[0]['end'])*.5 if windows else -1.0
            gate_ok=bool(pb and self._combo_window_at(pb,first_bridge_mid,first_bridge_mid-.01) is None and self._combo_window_at(pb,first_move_mid,first_move_mid-.01) is not None)
            serialized=self._serialize_melee_combo(combo); persist_ok=bool(serialized and self._deserialize_melee_combo(serialized)==self._combo_meta_defaults(combo))
            trans_ok=bool(bridges and all(COMBO_TRANSITION_MIN-1e-6<=b-a<=COMBO_TRANSITION_MAX+1e-6 for a,b in bridges))
            ok=bool(compiled and immutable and len(windows)==3 and len(bridges)==2 and bridge_gate and local_ok and playback_ok and gate_ok and persist_ok and trans_ok and compiled['duration']>sum((w['end']-w['start']) for w in windows))
            # Advance the actual Panda3D melee playback through every move and bridge without rendering frames.
            # Player is deliberately far from the NPC, so completion can be checked without damage noise.
            for _ in range(int(math.ceil((compiled['duration'] if compiled else 0.0)*60.0))+12):
                self._update_melee(1.0/60.0)
            completed=(self.melee_playback.get('right') is None)
            ok=ok and completed
            print(f"ANATOMIC_PASS44_SMOKE={'PASS' if ok else 'FAIL'} moves={len(windows)} bridges={len(bridges)} duration={compiled['duration'] if compiled else -1:.3f} immutable={int(immutable)} local={int(local_ok)} transition_damage={int(not bridge_gate)} playback={int(playback_ok)} complete={int(completed)} gate={int(gate_ok)}")
            if not ok: raise RuntimeError('PASS44_COMBO_COMPOSER_SMOKE_FAILED')
            self.userExit()
        if ARGS.pass44_proof and self.frame_count == 2:
            self._set_combat_mode('melee',announce=False)
            def mkproof(slot,phase,name,speed):
                samples=[]
                for i in range(76):
                    t=i/60.0; u=i/75.0
                    samples.append({'t':t,'target':Vec3(MELEE_NEUTRAL_X+.27*math.sin(u*math.tau+phase),MELEE_NEUTRAL_Y+.16*u+.025*slot,-.18+.18*math.sin(u*math.pi+phase*.3)),'hpr':Vec3(26*math.sin(u*math.tau+phase),-12+21*u,46*math.sin(u*math.tau+phase*.6))})
                self.melee_slots[slot]={'side':'right','duration':75/60.0,'travel':1.8+.16*slot,'samples':samples,'name':name,'playback_speed':speed,'trim_start':0.0,'trim_end':0.0,'mirrored':False}
            mkproof(1,0.0,'CYCLONE CUT',1.75); mkproof(4,.95,'RISING ARC',1.55); mkproof(7,1.7,'NEEDLE THRUST',1.90)
            self.melee_combos[3]={'name':'VIOLET TEMPEST','sequence':[1,4,7]}; self.active_combo_slot=3; self.combo_composer_slot=3; self.combo_composer_visible=True; self.combo_composer_mouse_was_captured=False
            self._set_mouse_capture(False); self.combo_composer.show(); self.melee_root.hide(); self.cross.hide(); self.status.hide(); self.hint.hide(); self._combo_update_ui()
        if ARGS.pass43_proof and self.frame_count == 2:
            self._set_combat_mode('melee',announce=False); samples=[]
            for i in range(91):
                t=i/60.0; u=i/90.0; samples.append({'t':t,'target':Vec3(MELEE_NEUTRAL_X+.30*math.sin(u*math.tau*1.25),MELEE_NEUTRAL_Y+.23*u,-.18+.21*math.sin(u*math.pi)),'hpr':Vec3(24*math.sin(u*math.tau),-12+22*u,48*math.sin(u*math.tau*1.25))})
            self.melee_slots[4]={'side':'right','duration':1.5,'travel':2.66,'samples':samples,'name':'CYCLONE CUT','playback_speed':1.80,'trim_start':.10,'trim_end':.15,'mirrored':True}
            self.motion_forge_slot=4; self.motion_forge_visible=True; self.motion_forge_mouse_was_captured=False; self._set_mouse_capture(False); self.motion_forge.show(); self.melee_root.hide(); self.cross.hide(); self.status.hide(); self.hint.hide(); self._forge_update_ui()
        if ARGS.pass42_proof and self.frame_count == 2:
            self.player_pos=Vec3(0.0,-1.38,0.0); self._set_spawn_camera_facing_npc(); self._update_camera(); self._set_combat_mode('melee',announce=False)
            # Author a broad fast edge-leading performance, then freeze just after its strongest impact.
            side='right'; self._begin_melee_charge(side)
            for i in range(76):
                t=i/60.0; u=i/75.0; a=u*math.pi
                self.melee_hold_time[side]=t; self.melee_cursor[side]=[-.66+1.22*u,.28*math.sin(a)-.12*u]
                target=self._melee_target_from_cursor(side); self._update_melee_pose(side,target); self._capture_melee_motion_sample(side,t,True); self.melee_recordings[side].append((t,*self.melee_cursor[side]))
            self.melee_hold_time[side]=75/60.0; self._finish_melee_charge(side)
            # Seed a real dynamic wound at the torso using an edge-leading sweep, then leave the
            # recorded blade in a dramatic follow-through with its velocity distortion visible.
            self._update_melee_pose('right',Vec3(.20,.72,-.18)); b1,t1=self._sword_blade_world(); edge=_v3(self.render.getRelativeVector(self.sword_root,Vec3(1,0,0))); edge.normalize()
            idx=next(i for i,b in enumerate(self.body_bindings) if b in ('chest','spine_high','spine_mid') and self.live[i]); point=self._current_glyph_world_pos(idx)
            shift=point-(b1+t1)*.5; b1+=shift; t1+=shift; b0=b1-edge*.105; t0=t1-edge*.105
            self._apply_sword_hit(b0,t0,b1,t1,.95,.90,1.0/60.0); self._advance_wound_memory(.16); self._update_wound_ascii(1.0/60.0)
            # Visual sweep stays attached to current weapon space; no permanent HUD/debug overlay.
            lb=_v3(self.melee_root.getRelativePoint(self.render,b1)); lt=_v3(self.melee_root.getRelativePoint(self.render,t1)); self.sword_distortion_history=[]
            for j in range(18):
                q=j/17.0; ofs=Vec3(-.30*(1-q),-.09*(1-q),.11*math.sin(q*math.pi)); self.sword_distortion_history.append((self.melee_time-(17-j)*.010,lb+ofs,lt+ofs,6.0+2.0*q))
            self._rebuild_sword_distortion(); self.pass42_proof_state=True
        if ARGS.pass41_proof and self.frame_count == 2:
            self.player_pos=Vec3(0.0,-1.52,0.0); self._set_spawn_camera_facing_npc(); self._update_camera(); self._set_combat_mode('melee',announce=False)
            side='right'; self._begin_melee_charge(side)
            for i in range(92):
                t=i/60.0; u=i/91.0
                self.melee_hold_time[side]=t; self.melee_cursor[side]=[-.70+1.24*u,.34*math.sin(u*math.pi*1.22)]
                target=self._melee_target_from_cursor(side); self._update_melee_pose(side,target); self._capture_melee_motion_sample(side,t,True); self.melee_recordings[side].append((t,*self.melee_cursor[side]))
            self.melee_hold_time[side]=91/60.0; self._finish_melee_charge(side); pb=self.melee_playback[side]; pb['elapsed']=.90/max(1e-6,pb['speed']); self._update_melee_body_solver(1.0/24.0)
            sample=self._sample_recorded_motion(pb['samples'],.90)
            if sample:
                target,hpr,_=sample; self._update_melee_pose(side,target); self.melee_arms[side]['fist'].setHpr(hpr); other=self.melee_arms['left']; self._update_melee_pose('left',_v3(other.get('last_target',Vec3(-MELEE_NEUTRAL_X,MELEE_NEUTRAL_Y,-.18))))
                blade=self._sword_blade_world()
                if blade:
                    base,tip=blade; lb=_v3(self.melee_root.getRelativePoint(self.render,base)); lt=_v3(self.melee_root.getRelativePoint(self.render,tip)); self.sword_distortion_history=[]
                    for j in range(14):
                        q=j/13.0; ofs=Vec3(-.24*(1-q),-.07*(1-q),.12*math.sin(q*math.pi)); self.sword_distortion_history.append((self.melee_time-(13-j)*.011,lb+ofs,lt+ofs,5.0+1.5*q))
                    self._rebuild_sword_distortion()
            self.pass41_proof_state={'pb':pb}
        elif ARGS.pass41_proof and self.frame_count>2 and getattr(self,'pass41_proof_state',None):
            pb=self.pass41_proof_state['pb']; pb['elapsed']=.90/max(1e-6,pb['speed']); self._update_melee_body_solver(1.0/60.0); sample=self._sample_recorded_motion(pb['samples'],.90)
            if sample:
                target,hpr,_=sample; self._update_melee_pose('right',target); self.melee_arms['right']['fist'].setHpr(hpr); other=self.melee_arms['left']; self._update_melee_pose('left',_v3(other.get('last_target',Vec3(-MELEE_NEUTRAL_X,MELEE_NEUTRAL_Y,-.18)))); self._rebuild_sword_distortion()
        if ARGS.pass40_proof and self.frame_count == 2:
            self.player_pos=Vec3(0.0,-1.50,0.0); self._set_spawn_camera_facing_npc(); self._update_camera(); self._set_combat_mode('melee',announce=False)
            side='right'; self._begin_melee_charge(side)
            for i in range(72):
                t=i/60.0; a=i/71.0*math.pi*1.85
                self.melee_hold_time[side]=t; self.melee_cursor[side]=[.44*math.sin(a),.31*math.sin(a*1.55)]
                target=self._melee_target_from_cursor(side); self._update_melee_pose(side,target); self._capture_melee_motion_sample(side,t,True); self.melee_recordings[side].append((t,*self.melee_cursor[side]))
            self.melee_hold_time[side]=1.20; self._finish_melee_charge(side)
            pb=self.melee_playback[side]; pb['elapsed']=.42
            sample=self._sample_recorded_motion(pb['samples'],pb['elapsed']*pb['speed'])
            if sample:
                target,hpr,_=sample; self._update_melee_pose(side,target); self.melee_arms[side]['fist'].setHpr(hpr)
                blade=self._sword_blade_world()
                if blade:
                    base,tip=blade; lb=_v3(self.melee_root.getRelativePoint(self.render,base)); lt=_v3(self.melee_root.getRelativePoint(self.render,tip))
                    # Seed a visible sweep field behind the current blade for deterministic visual QA.
                    self.sword_distortion_history=[]
                    for j in range(12):
                        u=j/11.0; ofs=Vec3(-.20*(1-u),-.10*(1-u),.09*math.sin(u*math.pi))
                        self.sword_distortion_history.append((self.melee_time-(11-j)*.012,lb+ofs,lt+ofs,4.8+1.2*u))
                    self._rebuild_sword_distortion()
            self.pass40_proof_state={'pb':pb}
        elif ARGS.pass40_proof and self.frame_count>2 and getattr(self,'pass40_proof_state',None):
            pb=self.pass40_proof_state['pb']; sample=self._sample_recorded_motion(pb['samples'],min(pb['duration'],.63))
            if sample:
                target,hpr,_=sample; self._update_melee_pose('right',target); self.melee_arms['right']['fist'].setHpr(hpr); self._rebuild_sword_distortion()
        if ARGS.pass39_proof and self.frame_count == 2:
            self.player_pos=Vec3(0.0,-1.48,0.0); self._set_spawn_camera_facing_npc(); self._update_camera(); self._set_combat_mode('melee',announce=False)
            self._begin_melee_charge('right'); self.melee_hold_time['right']=1.45
            # Visible looping hold path; release still starts from its final live point.
            for i in range(54):
                a=i/53.0*math.pi*1.65
                self.melee_cursor['right']=[.31*math.sin(a)+.14,.24*math.cos(a)-.08]
                self.melee_paths['right'].append(tuple(self.melee_cursor['right']))
                self.melee_recordings['right'].append((i/60.0,*self.melee_cursor['right']))
            self._rebuild_melee_trail('right'); self._update_melee_pose('right',self._melee_target_from_cursor('right')); self._finish_melee_charge('right')
            hit_idx=next(i for i,b in enumerate(self.body_bindings) if b in ('chest','spine_high','spine_mid'))
            hit_point=self._current_glyph_world_pos(hit_idx); self.damage_at(hit_point,.24,10,hit_index=hit_idx,wound_outer=MELEE_MID_RED,wound_core=MELEE_CORE_RED,impulse_scale=1.15,incoming_world=Vec3(.08,1,.03),mode='SWORD')
            self._apply_impact_reaction(hit_idx,Vec3(.08,1,.03),'SWORD'); self._advance_wound_memory(.30)
            pb=self.melee_playback['right']; pb['index']=1; pb['segment_t']=.34
            a=pb['targets'][1]; b=pb['targets'][2]; target=a+(b-a)*.27
            self._seed_sword_flurry_trail(pb); self._update_melee_pose('right',target); self._apply_sword_flurry_rotation('right',pb,.42)
            self.pass39_proof_state={'pb':pb,'target':Vec3(target)}
        elif ARGS.pass39_proof and self.frame_count > 2 and getattr(self,'pass39_proof_state',None):
            st=self.pass39_proof_state; pb=st['pb']; self.melee_playback['right']=None; self.melee_hold['right']=False
            self._seed_sword_flurry_trail(pb); self._update_melee_pose('right',st['target']); self._apply_sword_flurry_rotation('right',pb,.42); self._update_wound_ascii(1.0/60.0)
        if ARGS.pass38_proof and self.frame_count == 2:
            self.player_pos=Vec3(0.0,-1.48,0.0); self._set_spawn_camera_facing_npc(); self._update_camera(); self._set_combat_mode('melee',announce=False)
            self._begin_melee_charge('right'); self.melee_hold_time['right']=MELEE_FULL_CHARGE_TIME
            self.melee_cursor['right']=[.44,-.26]; self.melee_paths['right']=[(0.0,0.0),(.14,-.04),(.29,-.12),(.44,-.26)]
            self._update_melee_pose('right',self._melee_target_from_cursor('right')); self._finish_melee_charge('right')
            pb=self.melee_playback['right']; pb['index']=1; pb['segment_t']=.30
            a=pb['targets'][1]; b=pb['targets'][2]; tt=.216; target=a+(b-a)*tt
            self._seed_sword_flurry_trail(pb)
            self._update_melee_pose('right',target); self._apply_sword_flurry_rotation('right',pb,.38)
            self._update_melee_pose('left',Vec3(-MELEE_NEUTRAL_X,.49,-.23))
            self.pass38_proof_state={'pb':pb,'target':Vec3(target)}
        elif ARGS.pass38_proof and self.frame_count > 2 and getattr(self,'pass38_proof_state',None):
            st=self.pass38_proof_state; pb=st['pb']; self.melee_playback['right']=None; self.melee_hold['right']=False
            self._seed_sword_flurry_trail(pb)
            self._update_melee_pose('right',st['target']); self._apply_sword_flurry_rotation('right',pb,.38)
            self._update_melee_pose('left',Vec3(-MELEE_NEUTRAL_X,.49,-.23))
        if (ARGS.pass34_proof or ARGS.pass37_proof) and self.frame_count == 2:
            self.player_pos=Vec3(0.0,-1.48,0.0); self._set_spawn_camera_facing_npc(); self._update_camera(); self._set_combat_mode('melee',announce=False)
            self._begin_melee_charge('right'); self.melee_hold_time['right']=1.18
            self.melee_cursor['right']=[.36,-.18]
            self.melee_paths['right']=[(0.0,0.0),(.12,-.03),(.24,-.08),(.36,-.18)]
            self._rebuild_melee_trail('right')
            self._update_melee_pose('right',self._melee_target_from_cursor('right'))
            self._update_melee_pose('left',Vec3(-MELEE_NEUTRAL_X,.48,-.23))
        if ARGS.sword_proof and self.frame_count == 2:
            self.player_pos=Vec3(0.0,-1.65,0.0); self._set_spawn_camera_facing_npc(); self._update_camera(); self._set_combat_mode('melee',announce=False)
            self._update_melee_pose('left',Vec3(-MELEE_NEUTRAL_X,.56,-.20)); self._update_melee_pose('right',Vec3(MELEE_NEUTRAL_X,.56,-.20))
        if ARGS.dismember_proof and self.frame_count == 2:
            self.player_pos=Vec3(0.0,-1.35,0.0); self._set_spawn_camera_facing_npc(); self._update_camera(); self._set_combat_mode('melee',announce=False)
            # Visual acceptance intentionally demonstrates a large distal branch: cutting the
            # humerus detaches elbow -> wrist -> hand -> fingers plus their bound ASCII shell.
            a=_v3(self.rig_joints['left_shoulder'].getPos(self.render)); b=_v3(self.rig_joints['left_elbow'].getPos(self.render)); cp=(a+b)*.55
            idx=min((i for i in range(len(self.surface)) if self.live[i]),key=lambda i:(self._current_glyph_world_pos(i)-cp).lengthSquared())
            incoming=Vec3(-.72,.62,.20); self.damage_at(cp,.23,18,hit_index=idx,wound_outer=MELEE_MID_RED,wound_core=MELEE_CORE_RED,impulse_scale=.76,incoming_world=incoming,mode='SWORD')
            self._spawn_sword_sparks(cp,incoming); self._sever_bone('left_humerus',cp,incoming,.92)
            # Keep the sword readable but move it off the severed limb for the screenshot.
            self._update_melee_pose('right',Vec3(.36,.55,-.08))
        if ARGS.rig_smoke:
            if self.frame_count == 2:
                if not self.rig_joints:
                    raise RuntimeError('RIG_SMOKE_REQUIRES_ACTIVE_SKELETON')
                left_idx=next(i for i,b in enumerate(self.body_bindings) if b=='left_hand')
                foot_idx=next(i for i,b in enumerate(self.body_bindings) if b=='right_foot')
                brain_idx=next(i for i,b in enumerate(self.organ_bindings) if b=='head_base')
                neural_group=self.body_root.find('**/neural_group_left_elbow')
                self.rig_test_state={
                    'left_idx':left_idx,'foot_idx':foot_idx,'brain_idx':brain_idx,
                    'left_before':_v3(self.glyph_nodes[left_idx].getPos(self.render)),
                    'foot_before':_v3(self.glyph_nodes[foot_idx].getPos(self.render)),
                    'brain_before':_v3(self.organ_nodes[brain_idx].getPos(self.render)),
                    'neural_group':neural_group,
                    'neural_before':_v3(neural_group.getPos(self.render)) if not neural_group.isEmpty() else Vec3(0,0,0),
                }
                self.rig_joints['left_shoulder'].setH(24.0)
                self.rig_joints['left_elbow'].setP(-22.0)
                self.rig_joints['head_base'].setH(14.0)
            elif self.frame_count == 6 and self.rig_test_state:
                st=self.rig_test_state
                left_after=_v3(self.glyph_nodes[st['left_idx']].getPos(self.render))
                foot_after=_v3(self.glyph_nodes[st['foot_idx']].getPos(self.render))
                brain_after=_v3(self.organ_nodes[st['brain_idx']].getPos(self.render))
                neural_after=_v3(st['neural_group'].getPos(self.render)) if not st['neural_group'].isEmpty() else st['neural_before']
                st['left_displacement']=(left_after-st['left_before']).length()
                st['foot_displacement']=(foot_after-st['foot_before']).length()
                st['brain_displacement']=(brain_after-st['brain_before']).length()
                st['neural_displacement']=(neural_after-st['neural_before']).length()
                self.rig_joints['left_shoulder'].setHpr(0,0,0)
                self.rig_joints['left_elbow'].setHpr(0,0,0)
                self.rig_joints['head_base'].setHpr(0,0,0)
            elif self.frame_count == 10 and self.rig_test_state:
                st=self.rig_test_state
                left_rest=_v3(self.glyph_nodes[st['left_idx']].getPos(self.render))
                st['restore_error']=(left_rest-st['left_before']).length()
                ok=(st['left_displacement'] > 0.015 and st['foot_displacement'] < 0.001 and st['brain_displacement'] > 0.001 and st['neural_displacement'] > 0.001 and st['restore_error'] < 0.001)
                print(f"ASCII_MATTER_RIG_SMOKE={'PASS' if ok else 'FAIL'} hand_move={st['left_displacement']:.6f} brain_move={st['brain_displacement']:.6f} neural_move={st['neural_displacement']:.6f} foot_move={st['foot_displacement']:.6f} restore_error={st['restore_error']:.6f} bindings={len(self.body_bindings)} joints={len(self.rig_joints)}")
                if not ok: raise RuntimeError('RIG_PARENT_BINDING_SMOKE_FAILED')
        if ARGS.impact_smoke and self.frame_count == 2:
            head_idx=next((i for i,b in enumerate(self.body_bindings) if b=='head_base'),0)
            self._apply_impact_reaction(head_idx, Vec3(0,1,0), 'SNIPER')
        if ARGS.impact_smoke and self.frame_count == 18:
            reaction=abs(self.impact_head_p)+abs(self.impact_body_p)
            ok=(reaction > 0.35 and abs(self.impact_head_p) > abs(self.impact_body_p))
            print(f'ASCII_MATTER_IMPACT_SMOKE={"PASS" if ok else "FAIL"} reaction={reaction:.3f} body_p={self.impact_body_p:.3f} head_p={self.impact_head_p:.3f}')
            if not ok: raise RuntimeError('IMPACT_REACTION_SMOKE_FAILED')
        if ARGS.perf_smoke and self.frame_count == 2:
            self._update_render_lod(1.0,force=True)
        if ARGS.perf_smoke and self.frame_count == 18:
            batch_nodes,batch_geoms=self._glyph_batch_stats()
            ok=(self.body_count>=2000 and self.lod_tier in (0,1,2) and 0 < self.lod_visible_count <= self.body_count and batch_geoms < 320 and self.perf_counters['projectile_builds'] == 0)
            print('ASCII_MATTER_PERF_SMOKE='+('PASS' if ok else 'FAIL')+' '+json.dumps({**self.perf_counters,'lod_tier':self.lod_tier,'lod_visible':self.lod_visible_count,'glyphs':self.body_count,'glyph_batch_nodes':batch_nodes,'glyph_batch_geoms':batch_geoms},sort_keys=True))
            if not ok: raise RuntimeError('PERFORMANCE_SMOKE_FAILED')
        if ARGS.reverse_perf_smoke:
            if self.frame_count == 2:
                self.damage_at(Vec3(0.12, 0.0, 1.18), WOUND_RADIUS, 30)
            elif self.frame_count == 10:
                self.keys.add('r')
            elif self.frame_count == 30:
                self.keys.discard('r')
            elif self.frame_count == 34:
                self.damage_at(Vec3(0.12, 0.0, 1.18), WOUND_RADIUS, 30)
            elif self.frame_count == 42:
                self.keys.add('r')
            elif self.frame_count == 68:
                ok=(not self.fragments and not self.wounds and self.perf_counters['fragment_pool_hits'] >= 20 and self.perf_counters['glyph_color_updates'] > 0)
                print('ASCII_MATTER_REVERSE_PERF_SMOKE='+('PASS' if ok else 'FAIL')+' '+json.dumps(self.perf_counters,sort_keys=True))
                if not ok: raise RuntimeError('REVERSE_PERFORMANCE_SMOKE_FAILED')
        if ARGS.combat_smoke:
            if self.frame_count == 2:
                self.set_weapon_mode('AUTO'); self.fire_side('rifle')
            elif self.frame_count == 6:
                self.set_weapon_mode('SHOTGUN'); self.fire_side('rifle')
            elif self.frame_count == 10:
                self.set_weapon_mode('SNIPER'); self.fire_side('rifle')
            elif self.frame_count == 14:
                # deterministic direct body hit exercises Wound + Fragment construction
                self.damage_at(Vec3(0.12, 0.0, 1.18), WOUND_RADIUS, 12)
            elif self.frame_count == 26:
                self.keys.add('r')
        if ARGS.test_shot and self.frame_count == 5 and ARGS.proof in ('damaged', 'rewind'):
            self.damage_at(Vec3(0.12, 0.0, 1.18), WOUND_RADIUS, 30)
        if ARGS.test_shot and self.frame_count == 35 and ARGS.proof == 'rewind':
            self.keys.add('r')
        if 'r' in self.keys and (self.fragments or self.wounds or self.detached_limbs or self.wound_ascii):
            # Rewind only the recorded wound memory; player/camera remain responsive for inspection.
            for shot in self.shots:
                shot.node.removeNode()
            self.shots.clear()
            self._rewind_memory(dt)
        else:
            self.rewinding = False
            self._update_shots(dt)
            self._update_fragments(dt)
            self._advance_wound_memory(dt)
        self.frame_count += 1
        self._status()

        if ARGS.melee_impact_proof and not self.proof_done and self.frame_count >= 20:
            out=ROOT/'verification/pass32_hands/pass32_melee_impact_1080p.png'; out.parent.mkdir(parents=True,exist_ok=True)
            self.win.saveScreenshot(str(out)); self.proof_done=True
            print(f'ANATOMIC_MELEE_IMPACT_SCREENSHOT={out}')
            self.doMethodLater(.05,lambda t:(self.userExit(),t.done)[1],'melee-impact-proof-exit')
        if ARGS.melee_proof and not self.proof_done and self.frame_count >= 12:
            out=ROOT/'verification/pass32_hands/pass32_holo_hands_1080p.png'; out.parent.mkdir(parents=True,exist_ok=True)
            self.win.saveScreenshot(str(out)); self.proof_done=True
            print(f'ANATOMIC_MELEE_SCREENSHOT={out}')
            self.doMethodLater(.05,lambda t:(self.userExit(),t.done)[1],'melee-proof-exit')
        if ARGS.pass42_proof and not self.proof_done and self.frame_count >= 5:
            out=ROOT/f'verification/pass42_motion_dynamics/pass42_motion_dynamics_{ARGS.width}x{ARGS.height}.png'; out.parent.mkdir(parents=True,exist_ok=True)
            self.win.saveScreenshot(str(out)); self.proof_done=True
            print(f'ANATOMIC_PASS42_SCREENSHOT={out}')
            self.doMethodLater(.05,lambda t:(self.userExit(),t.done)[1],'pass42-proof-exit')
        if ARGS.pass45_proof and not self.proof_done and self.frame_count >= 5:
            out=ROOT/f'verification/pass45_jointmap_gait/pass45_jointmap_gait_{ARGS.width}x{ARGS.height}.png'; out.parent.mkdir(parents=True,exist_ok=True)
            image = self.win.getScreenshot()
            ok = bool(image and image.write(str(out)))
            actual = out
            if not ok:
                try:
                    if out.exists() and out.stat().st_size == 0:
                        out.unlink()
                except OSError:
                    pass
                actual = out.with_suffix('.bmp')
                ok = bool(image and image.write(str(actual)))
            self.proof_done=True
            print(f'ANATOMIC_PASS45_SCREENSHOT={actual} write={int(ok)} bytes={actual.stat().st_size if actual.exists() else 0}')
            self.doMethodLater(.05,lambda t:(self.userExit(),t.done)[1],'pass45-proof-exit')
        if ARGS.pass44_proof and not self.proof_done and self.frame_count >= 5:
            out=ROOT/f'verification/pass44_combo_composer/pass44_combo_composer_{ARGS.width}x{ARGS.height}.png'; out.parent.mkdir(parents=True,exist_ok=True)
            self.win.saveScreenshot(str(out)); self.proof_done=True
            print(f'ANATOMIC_PASS44_SCREENSHOT={out}')
            self.doMethodLater(.05,lambda t:(self.userExit(),t.done)[1],'pass44-proof-exit')
        if ARGS.pass43_proof and not self.proof_done and self.frame_count >= 5:
            out=ROOT/f'verification/pass43_motion_forge/pass43_motion_forge_{ARGS.width}x{ARGS.height}.png'; out.parent.mkdir(parents=True,exist_ok=True)
            self.win.saveScreenshot(str(out)); self.proof_done=True
            print(f'ANATOMIC_PASS43_SCREENSHOT={out}')
            self.doMethodLater(.05,lambda t:(self.userExit(),t.done)[1],'pass43-proof-exit')
        if ARGS.pass41_proof and not self.proof_done and self.frame_count >= 5:
            suffix='disabled' if ARGS.no_body_solver else 'enabled'
            out=ROOT/f'verification/pass41_body_solver/pass41_body_solver_{suffix}_{ARGS.width}x{ARGS.height}.png'; out.parent.mkdir(parents=True,exist_ok=True)
            self.win.saveScreenshot(str(out)); self.proof_done=True
            print(f'ANATOMIC_PASS41_SCREENSHOT={out}')
            self.doMethodLater(.05,lambda t:(self.userExit(),t.done)[1],'pass41-proof-exit')
        if ARGS.pass40_proof and not self.proof_done and self.frame_count >= 4:
            out=ROOT/f'verification/pass40_recorded_slots/pass40_saved_sword_distortion_{ARGS.width}x{ARGS.height}.png'; out.parent.mkdir(parents=True,exist_ok=True)
            self.win.saveScreenshot(str(out)); self.proof_done=True
            print(f'ANATOMIC_PASS40_SCREENSHOT={out}')
            self.doMethodLater(.05,lambda t:(self.userExit(),t.done)[1],'pass40-proof-exit')
        if ARGS.pass39_proof and not self.proof_done and self.frame_count >= 4:
            out=ROOT/f'verification/pass39_full_path_impact/pass39_melee_impact_ascii_spill_{ARGS.width}x{ARGS.height}.png'; out.parent.mkdir(parents=True,exist_ok=True)
            self.win.saveScreenshot(str(out)); self.proof_done=True
            print(f'ANATOMIC_PASS39_SCREENSHOT={out}')
            self.doMethodLater(.05,lambda t:(self.userExit(),t.done)[1],'pass39-proof-exit')
        if ARGS.pass38_proof and not self.proof_done and self.frame_count >= 8:
            out=ROOT/f'verification/pass38_release_flurry/pass38_release_origin_sword_flurry_{ARGS.width}x{ARGS.height}.png'; out.parent.mkdir(parents=True,exist_ok=True)
            self.win.saveScreenshot(str(out)); self.proof_done=True
            print(f'ANATOMIC_PASS38_SCREENSHOT={out}')
            self.doMethodLater(.05,lambda t:(self.userExit(),t.done)[1],'pass38-proof-exit')
        if (ARGS.pass34_proof or ARGS.pass37_proof) and not self.proof_done and self.frame_count >= 10:
            out=(ROOT/'verification/pass37_movement/pass37_wider_fov_movement_1080p.png') if ARGS.pass37_proof else (ROOT/'verification/pass34_assisted_reach/pass34_wider_fov_extended_sword_1080p.png')
            out.parent.mkdir(parents=True,exist_ok=True)
            self.win.saveScreenshot(str(out)); self.proof_done=True
            print(f'ANATOMIC_PASS37_SCREENSHOT={out}' if ARGS.pass37_proof else f'ANATOMIC_PASS34_SCREENSHOT={out}')
            self.doMethodLater(.05,lambda t:(self.userExit(),t.done)[1],'pass37-proof-exit' if ARGS.pass37_proof else 'pass34-proof-exit')
        if ARGS.sword_proof and not self.proof_done and self.frame_count >= 10:
            out=ROOT/'verification/pass33_sword/pass33_spaced_arms_laser_sword_1080p.png'; out.parent.mkdir(parents=True,exist_ok=True)
            self.win.saveScreenshot(str(out)); self.proof_done=True; print(f'ANATOMIC_SWORD_SCREENSHOT={out}')
            self.doMethodLater(.05,lambda t:(self.userExit(),t.done)[1],'sword-proof-exit')
        if ARGS.dismember_proof and not self.proof_done and self.frame_count >= 18:
            out=ROOT/'verification/pass33_sword/pass33_dismemberment_1080p.png'; out.parent.mkdir(parents=True,exist_ok=True)
            self.win.saveScreenshot(str(out)); self.proof_done=True; print(f'ANATOMIC_DISMEMBER_SCREENSHOT={out}')
            self.doMethodLater(.05,lambda t:(self.userExit(),t.done)[1],'dismember-proof-exit')
        proof_frame = 3 if ARGS.proof == 'intact' else (18 if ARGS.proof == 'damaged' else 48)
        if ARGS.test_shot and not self.proof_done and self.frame_count >= proof_frame:
            out=Path(ARGS.test_shot); out.parent.mkdir(parents=True,exist_ok=True)
            self.win.saveScreenshot(str(out)); self.proof_done=True
            print(f'ASCII_MATTER_FPS_SCREENSHOT={out}')
            self.doMethodLater(.05,lambda t:(self.userExit(),t.done)[1],'proof-exit')
        smoke_limit = 90 if ARGS.combat_smoke else (56 if ARGS.melee_smoke else (72 if ARGS.reverse_perf_smoke else (20 if (ARGS.impact_smoke or ARGS.perf_smoke) else (56 if ARGS.head_track_smoke else (3 if ARGS.walk_smoke else (5 if (ARGS.arm_smoke or ARGS.shoulder_smoke) else (14 if ARGS.rig_smoke else 2)))))))
        if ARGS.smoke_test and not ARGS.test_shot and self.frame_count>=smoke_limit:
            if ARGS.combat_smoke:
                label='ASCII_MATTER_COMBAT_SMOKE'
            elif ARGS.melee_smoke:
                label='ANATOMIC_MELEE_PARENT_SMOKE'
            elif ARGS.impact_smoke:
                label='ASCII_MATTER_IMPACT_PARENT_SMOKE'
            elif ARGS.reverse_perf_smoke:
                label='ASCII_MATTER_REVERSE_PERF_PARENT_SMOKE'
            elif ARGS.perf_smoke:
                label='ASCII_MATTER_PERF_PARENT_SMOKE'
            elif ARGS.walk_smoke:
                label='ASCII_MATTER_WALK_PARENT_SMOKE'
            elif ARGS.shoulder_smoke:
                label='ASCII_MATTER_SHOULDER_PARENT_SMOKE'
            elif ARGS.arm_smoke:
                label='ASCII_MATTER_ARM_PARENT_SMOKE'
            elif ARGS.head_track_smoke:
                label='ASCII_MATTER_HEAD_TRACK_PARENT_SMOKE'
            elif ARGS.rig_smoke:
                label='ASCII_MATTER_RIG_PARENT_SMOKE'
            else:
                label='ASCII_MATTER_MEMORY_REWIND_SMOKE'
            batch_nodes,batch_geoms=self._glyph_batch_stats()
            print(f'{label}=PASS glyphs={self.body_count} visible={self.lod_visible_count} glyph_batch_geoms={batch_geoms} organs={len(self.organ_nodes)} neural={getattr(self, "neural_count", len(self.neural_nodes))} bones={self.skeleton_segment_count} joints={self.skeleton_joint_count} skull={self.skeleton_skull_count} fragments={len(self.fragments)} wounds={len(self.wounds)} resolution={ARGS.width}x{ARGS.height} shot_queries={self.perf_counters["shot_queries"]} shot_candidates={self.perf_counters["shot_query_candidates"]} shot_checks={self.perf_counters["shot_query_checks"]} damage_bindings={self.perf_counters["damage_binding_checks"]} damage_checks={self.perf_counters["damage_checks"]} batch_rebuilds={self.perf_counters["glyph_batch_rebuilds"]} color_updates={self.perf_counters["glyph_color_updates"]} fragment_pool_hits={self.perf_counters["fragment_pool_hits"]} fragment_pool_misses={self.perf_counters["fragment_pool_misses"]} projectile_builds={self.perf_counters["projectile_builds"]}')
            self.userExit()
        return None if task is None else task.cont



    def shutdown_embedded(self):
        """Release dimension-owned transient state without exiting HoloVerse."""
        try:
            self.ignoreAll()
        except Exception:
            pass
        try:
            self.removeAllTasks()
        except Exception:
            pass
        try:
            self.keys.clear()
            self.melee_hold = {'left': False, 'right': False}
            self.fire_button_down = False
            self.rewinding = False
        except Exception:
            pass
        try:
            self._set_mouse_capture(False)
        except Exception:
            pass
        try:
            if self.sword_hum is not None:
                self.sword_hum.stop()
        except Exception:
            pass
        for voices in list(getattr(self, 'weapon_sfx', {}).values()):
            for snd in list(voices or []):
                try:
                    snd.stop()
                except Exception:
                    pass
        for name in ('help','motion_forge','combo_composer','cross','status','hint'):
            obj = getattr(self, name, None)
            try:
                if obj is not None:
                    obj.destroy()
            except Exception:
                pass
        _checkpoint('holoverse_host_detach')


if __name__=='__main__':
    try:
        app = ASCIIMatterLab()
        app.run()
        _checkpoint('clean_exit')
    except SystemExit as exc:
        if getattr(exc, 'code', 0) not in (0, None):
            _write_crash_report(exc, 'system_exit')
        raise
    except BaseException as exc:
        _write_crash_report(exc, 'runtime')
        raise
    finally:
        try:
            if _FAULT_HANDLE is not None:
                _FAULT_HANDLE.flush()
        except Exception:
            pass

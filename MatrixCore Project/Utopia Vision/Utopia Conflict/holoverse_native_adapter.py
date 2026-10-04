"""Full-source HoloVerse native adapter for Utopia Conflict.

This adapter is intentionally source-preserving.  It does not implement a
replacement arena, player, enemy, weapon, health system, city-capture system,
or editor.  Instead, it loads the linked project's real ``main.py`` and its
project-local module stack under HoloVerse's existing Panda3D lifecycle.

The Pass39 line is a multi-module ShowBase application (CombatWorkbenchApp
built on prev_main/base_workbench).  Native mode therefore has to intercept
ShowBase *before* those project-local modules import, capture their tasks and
Messenger bindings, and prevent source-side window changes from mutating the
HoloVerse host window.
"""
from __future__ import annotations

import importlib
import importlib.util
import contextlib
import os
import sys
import time
import types
from pathlib import Path

MODE_ID = "utopia_conflict"
MODE_TITLE = "Utopia Conflict // Source Vector Arena"
ADAPTER_VERSION = "1.2-pass42-runtime-source-discovery"


def _safe_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception:
        return None


class _CapturedTask:
    def __init__(self, name: str, callback=None, delay: float = 0.0):
        self.name = str(name or "captured-task")
        self.callback = callback
        self.removed = False
        self.time = 0.0
        self.frame = 0
        self.delayTime = max(0.0, float(delay or 0.0))
        self.next_run = self.delayTime
        self._last_run = 0.0
        try:
            from direct.task import Task
            self.cont = Task.cont
            self.done = Task.done
            self.again = Task.again
        except Exception:
            self.cont = "cont"
            self.done = "done"
            self.again = "again"

    def remove(self):
        self.removed = True


class _TaskCaptureProxy:
    """Capture source tasks so HoloVerse remains the only frame-loop owner."""

    def __init__(self, real_task_mgr, owner):
        self._real = real_task_mgr
        self._owner = owner
        self._tasks: dict[str, dict] = {}
        self._seq = 0

    def add(self, callback, name=None, *args, **kwargs):
        task_name = str(name or getattr(callback, "__name__", "captured-task"))
        self._seq += 1
        handle = _CapturedTask(task_name, callback)
        item = {
            "callback": callback,
            "handle": handle,
            "extraArgs": list(kwargs.get("extraArgs") or []),
            "appendTask": bool(kwargs.get("appendTask", False)),
            "sort": int(kwargs.get("sort") or 0),
            "sequence": self._seq,
            "delayed": False,
        }
        self._tasks[task_name] = item
        self._owner._captured_tasks[task_name] = item
        return handle

    def doMethodLater(self, delay, callback, name, *args, **kwargs):
        handle = self.add(callback, name, *args, **kwargs)
        handle.delayTime = max(0.0, float(delay or 0.0))
        handle.next_run = handle.delayTime
        self._tasks[str(handle.name)]["delayed"] = True
        return handle

    def remove(self, task_or_name):
        name = str(getattr(task_or_name, "name", task_or_name))
        item = self._tasks.pop(name, None)
        self._owner._captured_tasks.pop(name, None)
        if item and item.get("handle"):
            item["handle"].removed = True
        return bool(item)

    def hasTaskNamed(self, name):
        return str(name) in self._tasks

    def getTasksNamed(self, name):
        item = self._tasks.get(str(name))
        return [item["handle"]] if item else []

    def __getattr__(self, name):
        return getattr(self._real, name)


class _WindowProxy:
    """Read-only-ish view of the HoloVerse GraphicsWindow for source code.

    Linked games may query the real window and take screenshots, but requests
    to resize, reposition, retitle, minimize, fullscreen, undecorate, or close
    it are intentionally swallowed while mounted.  HoloVerse is the Windows
    display authority.
    """

    def __init__(self, real_window, owner):
        self._real = real_window
        self._owner = owner

    def requestProperties(self, properties):
        self._owner._window_mutation_requests += 1
        return None

    request_properties = requestProperties

    def __getattr__(self, name):
        return getattr(self._real, name)


class _MessengerCaptureProxy:
    """Dimension-local messenger facade.

    Utopia Conflict's older workbench helpers may import the global Panda
    messenger directly instead of using ``self.accept``.  Keep those bindings
    inside the dimension instead of registering them on HoloVerse.
    """

    def __init__(self, real_messenger, context):
        self._real = real_messenger
        self._context = context

    def accept(self, event, obj, method, extraArgs=None, persistent=1):
        return self._context.capture_accept(event, method, extraArgs=extraArgs, persistent=persistent)

    def acceptOnce(self, event, obj, method, extraArgs=None):
        return self._context.capture_accept(event, method, extraArgs=extraArgs, persistent=0)

    def ignore(self, event, obj=None):
        return self._context.capture_ignore(event)

    def ignoreAll(self, obj=None):
        return self._context.capture_ignore_all()

    def send(self, event, sentArgs=None, taskChain=None):
        # First offer source-owned events back to the mounted game.  Unknown
        # engine/system events may still flow through Panda's real messenger.
        if self._context.dispatch_event(str(event)):
            return None
        try:
            return self._real.send(event, sentArgs or [], taskChain=taskChain)
        except TypeError:
            try:
                return self._real.send(event, sentArgs or [])
            except Exception:
                return None
        except Exception:
            return None

    def __getattr__(self, name):
        return getattr(self._real, name)


class _HostedBaseProxy:
    """Global ``base`` facade for project modules that import ShowBaseGlobal.base."""

    def __init__(self, adapter, context):
        self._adapter = adapter
        self._context = context

    def __getattr__(self, name):
        delegate = getattr(self._adapter, "delegate", None)
        if delegate is not None and hasattr(delegate, name):
            return getattr(delegate, name)
        host = self._adapter.host
        if name == "render": return self._context.scene_root
        if name == "camera": return getattr(host, "camera", None)
        if name == "cam": return getattr(host, "cam", None)
        if name == "camNode": return getattr(host, "camNode", None)
        if name == "camLens": return getattr(host, "camLens", None)
        if name == "taskMgr": return self._context.task_proxy
        if name == "win": return self._context.window_proxy
        if name == "messenger": return self._context.messenger_proxy
        if name == "accept": return self._context.capture_accept
        if name == "ignore": return self._context.capture_ignore
        if name == "ignoreAll": return self._context.capture_ignore_all
        if name == "userExit": return self._context.request_return
        return getattr(host, name)


class _BridgeContext:
    def __init__(self, adapter):
        self.adapter = adapter
        self.host = adapter.host
        self.scene_root = None
        self.task_proxy = None
        self.window_proxy = None
        self.messenger_proxy = None
        self.base_proxy = None
        self.events: dict[str, tuple] = {}
        self.ui_before = set()
        self.saved_sfx_volumes = []
        self.saved_music_volume = None

    def capture_accept(self, event, method, extraArgs=None, persistent=1):
        self.events[str(event)] = (method, list(extraArgs or []))
        return None

    def capture_ignore(self, event):
        self.events.pop(str(event), None)

    def capture_ignore_all(self):
        self.events.clear()

    def request_return(self, *args, **kwargs):
        _safe_call(self.host.return_from_native_mode, reason="utopia_conflict_source_exit")

    def dispatch_event(self, event, *sent_args):
        item = self.events.get(str(event))
        if not item:
            return False
        method, extra = item
        try:
            # Panda appends event parameters (eg. window-event sends the window) after
            # the handler's extraArgs, exactly like Messenger.__dispatch.
            method(*(list(extra) + list(sent_args)))
            return True
        except SystemExit:
            self.request_return()
            return True
        except Exception as exc:
            print(f"utopia_conflict_event_error event={event} err={exc.__class__.__name__}:{exc}")
            return False


def _host_runtime_settings(host) -> dict:
    cfg = getattr(host, "cfg", None)
    def read(name, default):
        try:
            return getattr(cfg, name)
        except Exception:
            return default
    width = int(read("launch_width", 1920) or 1920)
    height = int(read("launch_height", 1080) or 1080)
    origin = {"x": None, "y": None}
    try:
        props = host.win.getProperties()
        pt = props.getOrigin()
        origin = {"x": int(pt.x), "y": int(pt.y)}
    except Exception:
        pass
    return {
        "schema": "holoverse_native_runtime_bridge_v2",
        "source": "HoloVerse",
        "display_mode": "same_window_native",
        "resolution": {"width": width, "height": height},
        "width": width,
        "height": height,
        "window_origin": origin,
        "fullscreen": bool(read("launch_fullscreen", False)),
        "borderless": bool(read("launch_borderless", False)),
        "bordered_fullscreen": bool(read("launch_bordered_fullscreen", True)),
        "vsync": bool(read("launch_vsync", True)),
        "fps_cap": int(read("launch_fps_cap", 60) or 60),
        "ui_scale": float(read("launch_ui_scale", 1.0) or 1.0),
        "render_scale": float(read("launch_render_scale", 1.0) or 1.0),
        "hud_visible": True,  # dimension-owned HUD; host preference is not propagated
        "graphics_quality": str(read("graphics_quality", "high") or "high"),
        "mouse_sensitivity": float(read("launch_game_mouse_sensitivity", 0.16) or 0.16),
        "invert_y": bool(read("launch_invert_y", False)),
        "controller_deadzone": float(read("launch_controller_deadzone", 0.15) or 0.15),
        "master_volume": float(read("master_volume", 0.82) or 0.0),
        "music_volume": float(read("music_volume", 0.42) or 0.0),
        "sfx_volume": float(read("sfx_volume", 0.82) or 0.0),
        "ambience_volume": float(read("ambience_volume", 0.58) or 0.0),
    }


def _runtime_stub(settings: dict):
    mod = types.ModuleType("holoverse_mode_runtime")
    mod.embedded_mode = lambda: False
    mod.load_settings = lambda: dict(settings)
    mod.should_return_to_core = lambda: False
    mod.acknowledge_return_request = lambda: None
    return mod


def _module_path(module):
    raw = getattr(module, "__file__", None)
    if not raw:
        return None
    try:
        return Path(raw).resolve()
    except Exception:
        return None


def _is_under(path: Path | None, root: Path) -> bool:
    if path is None:
        return False
    try:
        path.relative_to(root)
        return True
    except Exception:
        return False


class HoloVerseNativeMode:
    def __init__(self, host, mode=None, entry_path=None, label=MODE_TITLE):
        self.host = host
        self.mode = dict(mode or {})
        self.entry_path = Path(entry_path).resolve() if entry_path else Path(__file__).resolve().with_name("main.py")
        self.label = str(label or MODE_TITLE)
        self.delegate = None
        self._module = None
        self._module_name = None
        self._context = None
        self._entered = False
        self._started_at = 0.0
        self._frame_index = 0
        self._captured_tasks: dict[str, dict] = {}
        self._ui_nodes = []
        self._scene_root = None
        self._runtime_settings = _host_runtime_settings(host)
        self._prior_local_modules: dict[str, object] = {}
        self._loaded_local_module_names: set[str] = set()
        self._window_mutation_requests = 0
        self._source_features = {}
        self._runtime_patch_state = {}
        self._runtime_path_added = False
        self._runtime_stub_module = None
        self._runtime_env_prior = {}
        self._host_input_bound = False
        self._diagnostics = {
            "adapter_version": ADAPTER_VERSION,
            "full_source_game": True,
            "same_window": True,
            "second_showbase": False,
            "second_window": False,
            "second_frame_task": False,
            "placeholder_scene": False,
            "host_camera_isolated": True,
            "host_player_state_frozen": True,
            "source_window_mutation_blocked": True,
            "persistent_link_identity": True,
            "runtime_context_persistent_for_visit": True,
            "task_manager_global_isolated": True,
            "showbase_global_base_isolated": True,
            "messenger_global_isolated": True,
            "direct_object_messenger_isolated": True,
            "project_sys_path_retained_for_visit": True,
            "project_cwd_scoped_for_callbacks": True,
        }

    # Host roots the source may attach to through base.camera / base.aspect2d / etc.
    # Everything the visit adds under them is removed on exit (cockpit, weapons, sky dome,
    # HUD). Anything that existed before entry is never touched.
    HOST_ROOTS = ("aspect2d", "render2d", "pixel2d", "camera", "cam",
                  "a2dTopLeft", "a2dTopRight", "a2dBottomLeft", "a2dBottomRight",
                  "a2dTopCenter", "a2dBottomCenter")

    def _snapshot_ui(self):
        before = set()
        for attr in self.HOST_ROOTS:
            root = getattr(self.host, attr, None)
            if root is None:
                continue
            try:
                before.update(child.node() for child in root.getChildren())
            except Exception:
                pass
        return before

    def _collect_new_ui(self, before):
        out = []
        for attr in self.HOST_ROOTS:
            root = getattr(self.host, attr, None)
            if root is None:
                continue
            try:
                for child in root.getChildren():
                    try:
                        if child.node() not in before and child not in out:
                            out.append(child)
                    except Exception:
                        pass
            except Exception:
                pass
        return out

    def _source_compatibility_preflight(self, source: Path):
        """Inventory the linked project without rejecting wrapper-style entry files.

        Pass41 incorrectly required all authority markers to be literal text in
        the selected ``main.py``.  The real linked project may use a thin
        launcher/wrapper while the CombatWorkbenchApp lives in another local
        module.  Native compatibility is therefore decided *after import* from
        real runtime classes, not by a brittle string gate.
        """
        project_root = source.parent
        if not source.exists():
            raise FileNotFoundError(f"Utopia Conflict source missing: {source}")
        texts = []
        scanned = []
        # Keep discovery bounded and source-only.  Top-level files are preferred
        # because the accepted workbench family uses main.py/prev_main.py/
        # base_workbench.py, but wrappers in one shallow package are supported.
        candidates = [source]
        for py in sorted(project_root.glob("*.py")):
            if py not in candidates and py.name not in {"holoverse_native_adapter.py"}:
                candidates.append(py)
        for sub in sorted(project_root.iterdir() if project_root.exists() else []):
            if not sub.is_dir() or sub.name.startswith((".", "__")) or sub.name in {"tools", "verification", "saves"}:
                continue
            for py in sorted(sub.glob("*.py")):
                if py.name != "holoverse_native_adapter.py":
                    candidates.append(py)
        seen = set()
        for py in candidates[:96]:
            try:
                rp = py.resolve()
            except Exception:
                rp = py
            if rp in seen:
                continue
            seen.add(rp)
            try:
                text = py.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if len(text) > 2_500_000:
                text = text[:2_500_000]
            texts.append(text)
            try:
                scanned.append(str(py.relative_to(project_root)))
            except Exception:
                scanned.append(py.name)
        combined = "\n".join(texts)
        lower = combined.lower()
        try:
            entry_lower = source.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            entry_lower = ""
        marker_map = {
            "combat_workbench": "combatworkbenchapp" in lower,
            "battle_mode": "enter_battle_mode" in lower or "battle_ground" in lower or "battle_air" in lower,
            "weapon_library": "weapon_library" in lower or "weapon_profile" in lower,
            "playtest_update": "update_playtest" in lower or ("runtime_mode" in lower and "def update(" in lower),
        }
        self._source_features = {
            **marker_map,
            "source_vector_arena_family": any(("source vector" in lower, "source_vector" in lower, "combatworkbenchapp" in lower)),
            "wireframe_health_tokens": any(tok in lower for tok in ("health_color", "health palette", "wireframe")),
            "armor_tokens": "armor" in lower,
            "armor_upgrade_i": ('accept("i"' in lower or "accept('i'" in lower or "armor" in lower),
            "city_capture_tokens": "city" in lower and "capture" in lower,
            "scanned_python_files": scanned,
            "entry_is_wrapper": "combatworkbenchapp" not in entry_lower,
        }
        print(
            "utopia_conflict_source_inventory "
            f"entry={source} files={len(scanned)} markers="
            + ",".join(k for k,v in marker_map.items() if v)
        )
        return True

    def _discover_game_class(self, entry_module, hosted_showbase, project_root: Path):
        """Find the real most-derived Utopia Conflict application class.

        Supports direct game entry files, import-only wrappers, and launchers
        that defer importing the real workbench until ``main()``.  Only strong
        Utopia Conflict source candidates inside the linked project are imported
        by the fallback discovery pass.
        """
        def collect_candidates():
            modules = [entry_module]
            for name in sorted(self._loaded_local_module_names):
                mod = sys.modules.get(name)
                if mod is not None and mod not in modules:
                    modules.append(mod)
            found = []
            seen = set()
            for mod in modules:
                mpath = _module_path(mod)
                if mod is not entry_module and not _is_under(mpath, project_root):
                    continue
                for attr_name, obj in list(getattr(mod, "__dict__", {}).items()):
                    if not isinstance(obj, type) or id(obj) in seen:
                        continue
                    seen.add(id(obj))
                    try:
                        if obj is hosted_showbase or not issubclass(obj, hosted_showbase):
                            continue
                    except Exception:
                        continue
                    score = 0
                    name_low = str(getattr(obj, "__name__", attr_name)).lower()
                    if name_low == "combatworkbenchapp": score += 1000
                    if "combat" in name_low: score += 180
                    if "workbench" in name_low: score += 120
                    if mod is entry_module: score += 100
                    for method, pts in (("enter_battle_mode",160),("update",120),("enter_playtest_mode",80),("refresh_ui",40),("toggle_hud",30)):
                        if callable(getattr(obj, method, None)): score += pts
                    try: score += min(80, len(obj.mro()) * 8)
                    except Exception: pass
                    found.append((score, obj, getattr(mod, "__name__", "?")))
            return found

        candidates = collect_candidates()
        fallback_imports = []
        if not candidates:
            for rel in list(self._source_features.get("scanned_python_files", [])):
                py = project_root / rel
                try:
                    if py.resolve() == self.entry_path.resolve() or not py.is_file():
                        continue
                except Exception:
                    continue
                try:
                    text = py.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                strong = (
                    "class CombatWorkbenchApp" in text
                    or ("enter_battle_mode" in text and ("WEAPON_LIBRARY" in text or "weapon_profile" in text))
                )
                if not strong:
                    continue
                try:
                    relmod = py.relative_to(project_root).with_suffix("")
                    module_name = ".".join(relmod.parts)
                    with self._project_runtime_cwd():
                        importlib.import_module(module_name)
                    fallback_imports.append(module_name)
                except Exception as exc:
                    print(f"utopia_conflict_discovery_import_failed module={py} err={exc.__class__.__name__}:{exc}")
            self._track_project_modules(project_root)
            candidates = collect_candidates()
        if not candidates:
            loaded = sorted(self._loaded_local_module_names)
            raise RuntimeError(
                "Utopia Conflict runtime class not found after import; "
                f"entry={self.entry_path.name} loaded_local_modules={loaded[:24]} "
                f"fallback_imports={fallback_imports}"
            )
        candidates.sort(key=lambda item: item[0], reverse=True)
        score, game_class, module_name = candidates[0]
        self._source_features["runtime_class"] = getattr(game_class, "__name__", str(game_class))
        self._source_features["runtime_class_module"] = module_name
        self._source_features["runtime_class_score"] = int(score)
        self._source_features["fallback_imports"] = fallback_imports
        print(
            "utopia_conflict_runtime_class "
            f"class={self._source_features['runtime_class']} module={module_name} score={score} "
            f"fallback_imports={fallback_imports}"
        )
        return game_class

    def _park_project_modules(self, project_root: Path):
        parked = {}
        for name, module in list(sys.modules.items()):
            if module is None:
                continue
            if _is_under(_module_path(module), project_root):
                parked[name] = module
                sys.modules.pop(name, None)
        # Also protect simple top-level module names in this project (eg.
        # base_workbench / prev_main) from stale imports belonging to another
        # prototype with the same generic filename.
        for py in project_root.glob("*.py"):
            if py.name == self.entry_path.name:
                continue
            name = py.stem
            if name in sys.modules and name not in parked:
                parked[name] = sys.modules.pop(name)
        self._prior_local_modules = parked

    def _track_project_modules(self, project_root: Path):
        self._loaded_local_module_names = {
            name for name, module in list(sys.modules.items())
            if module is not None and _is_under(_module_path(module), project_root)
        }

    def _restore_project_modules(self):
        for name in list(self._loaded_local_module_names):
            module = sys.modules.get(name)
            if module is not None and _is_under(_module_path(module), self.entry_path.parent):
                sys.modules.pop(name, None)
        for name, module in self._prior_local_modules.items():
            sys.modules[name] = module
        self._loaded_local_module_names.clear()
        self._prior_local_modules.clear()

    def _make_hosted_showbase_class(self, real_showbase, context):
        host = self.host

        class HostedShowBase(real_showbase):
            def __init__(self, *args, **kwargs):
                # Share services but do not invoke the real ShowBase constructor.
                # HoloVerse remains the only application/window/audio lifecycle.
                self.__dict__.update(host.__dict__)
                self.render = context.scene_root
                self.camera = getattr(host, "camera", None)
                self.cam = getattr(host, "cam", None)
                self.camNode = getattr(host, "camNode", None)
                self.camLens = getattr(host, "camLens", None)
                self.win = context.window_proxy
                self.loader = getattr(host, "loader", None)
                self.graphicsEngine = getattr(host, "graphicsEngine", None)
                self.pipe = getattr(host, "pipe", None)
                self.mouseWatcherNode = getattr(host, "mouseWatcherNode", None)
                self.aspect2d = getattr(host, "aspect2d", None)
                self.render2d = getattr(host, "render2d", None)
                self.pixel2d = getattr(host, "pixel2d", None)
                for anchor in ("a2dTopLeft", "a2dTopRight", "a2dBottomLeft", "a2dBottomRight", "a2dTopCenter", "a2dBottomCenter"):
                    if hasattr(host, anchor):
                        setattr(self, anchor, getattr(host, anchor))
                self.sfxManagerList = getattr(host, "sfxManagerList", [])
                self.musicManager = getattr(host, "musicManager", None)
                self.taskMgr = context.task_proxy
                self.messenger = context.messenger_proxy
                self.accept = context.capture_accept
                self.ignore = context.capture_ignore
                self.ignoreAll = context.capture_ignore_all
                self.userExit = context.request_return
                # Built-in mouse/interface tasks are already owned by HoloVerse.
                self.disableMouse = lambda: None
                self.enableMouse = lambda: None
                self.openDefaultWindow = lambda *a, **k: getattr(host, "win", None)
                self.openWindow = lambda *a, **k: getattr(host, "win", None)
                self.closeWindow = lambda *a, **k: None

        HostedShowBase.__name__ = "HoloVerseHostedUtopiaConflictShowBase"
        return HostedShowBase

    def _rebind_project_globals(self, project_root: Path):
        # Rebind every common Panda global that project-local modules may have
        # imported by value.  This is required for the real multi-module
        # base_workbench/prev_main stack, not just the top-level main.py.
        for name in self._loaded_local_module_names:
            module = sys.modules.get(name)
            if module is None:
                continue
            namespace = getattr(module, "__dict__", {})
            replacements = {
                "render": self._scene_root,
                "camera": getattr(self.host, "camera", None),
                "cam": getattr(self.host, "cam", None),
                "taskMgr": self._context.task_proxy,
                "loader": getattr(self.host, "loader", None),
                "base": self.delegate or self._context.base_proxy,
                "messenger": self._context.messenger_proxy,
            }
            for key, value in replacements.items():
                if key in namespace:
                    namespace[key] = value

    @contextlib.contextmanager
    def _project_runtime_cwd(self):
        old = Path.cwd()
        try:
            os.chdir(self.entry_path.parent)
            yield
        finally:
            try:
                os.chdir(old)
            except Exception:
                pass

    def _install_runtime_context(self, hosted_showbase, responder):
        """Keep the source's expected Panda globals isolated for the WHOLE visit.

        Pass40 restored these immediately after import.  That works for a tiny
        mock, but a real workbench may perform deferred imports, add tasks, load
        relative assets, or reference ShowBaseGlobal/TaskManagerGlobal later.
        """
        showbase_module = importlib.import_module("direct.showbase.ShowBase")
        showbase_global = importlib.import_module("direct.showbase.ShowBaseGlobal")
        task_global = importlib.import_module("direct.task.TaskManagerGlobal")
        messenger_global = importlib.import_module("direct.showbase.MessengerGlobal")
        direct_object_module = importlib.import_module("direct.showbase.DirectObject")
        panda_core = importlib.import_module("panda3d.core")
        state = self._runtime_patch_state = {
            "showbase_module": showbase_module,
            "showbase_class": showbase_module.ShowBase,
            "showbase_global": showbase_global,
            "task_global": task_global,
            "messenger_global": messenger_global,
            "direct_object_module": direct_object_module,
            "direct_object_messenger": getattr(direct_object_module, "messenger", None),
            "panda_core": panda_core,
            "loadPrcFileData": panda_core.loadPrcFileData,
            "holoverse_mode_runtime": sys.modules.get("holoverse_mode_runtime"),
            "holoverse_mode_runtime_present": "holoverse_mode_runtime" in sys.modules,
            "globals": {},
        }
        for attr in ("base", "render", "camera", "cam", "taskMgr", "loader", "messenger"):
            state["globals"][("showbase", attr)] = getattr(showbase_global, attr, None)
        state["globals"][("task", "taskMgr")] = getattr(task_global, "taskMgr", None)
        state["globals"][("messenger", "messenger")] = getattr(messenger_global, "messenger", None)

        showbase_module.ShowBase = hosted_showbase
        panda_core.loadPrcFileData = lambda *a, **k: None
        showbase_global.base = self._context.base_proxy
        showbase_global.render = self._scene_root
        showbase_global.camera = getattr(self.host, "camera", None)
        showbase_global.cam = getattr(self.host, "cam", None)
        showbase_global.taskMgr = self._context.task_proxy
        showbase_global.loader = getattr(self.host, "loader", None)
        showbase_global.messenger = self._context.messenger_proxy
        task_global.taskMgr = self._context.task_proxy
        messenger_global.messenger = self._context.messenger_proxy
        # DirectObject imports MessengerGlobal.messenger by value at module load
        # time, so patch its retained reference too. This prevents helper
        # DirectObject instances from registering handlers on HoloVerse.
        direct_object_module.messenger = self._context.messenger_proxy
        sys.modules["holoverse_mode_runtime"] = responder
        self._runtime_stub_module = responder

        root_text = str(self.entry_path.parent)
        if root_text not in sys.path:
            sys.path.insert(0, root_text)
            self._runtime_path_added = True
        self._runtime_env_prior = {
            "HOLOVERSE_NATIVE_INPROCESS": os.environ.get("HOLOVERSE_NATIVE_INPROCESS"),
            "HOLOVERSE_DIMENSION_ID": os.environ.get("HOLOVERSE_DIMENSION_ID"),
        }
        os.environ["HOLOVERSE_NATIVE_INPROCESS"] = "1"
        os.environ["HOLOVERSE_DIMENSION_ID"] = str((self.mode.get("manifest") or {}).get("dimension_id") or (self.mode.get("manifest") or {}).get("id") or self.mode.get("id") or MODE_ID)

    def _restore_runtime_context(self):
        state = dict(self._runtime_patch_state or {})
        if not state:
            return
        try:
            state["showbase_module"].ShowBase = state["showbase_class"]
        except Exception:
            pass
        try:
            state["panda_core"].loadPrcFileData = state["loadPrcFileData"]
        except Exception:
            pass
        sg = state.get("showbase_global")
        tg = state.get("task_global")
        mg = state.get("messenger_global")
        dom = state.get("direct_object_module")
        for (group, attr), value in state.get("globals", {}).items():
            obj = sg if group == "showbase" else tg if group == "task" else mg
            try:
                setattr(obj, attr, value)
            except Exception:
                pass
        try:
            if dom is not None:
                dom.messenger = state.get("direct_object_messenger")
        except Exception:
            pass
        if state.get("holoverse_mode_runtime_present"):
            sys.modules["holoverse_mode_runtime"] = state.get("holoverse_mode_runtime")
        else:
            sys.modules.pop("holoverse_mode_runtime", None)
        if self._runtime_path_added:
            try:
                sys.path.remove(str(self.entry_path.parent))
            except ValueError:
                pass
        self._runtime_path_added = False
        for key, old in self._runtime_env_prior.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old
        self._runtime_env_prior.clear()
        self._runtime_patch_state.clear()

    def _load_source_module(self):
        source = self.entry_path
        if not source.exists():
            raise FileNotFoundError(f"Utopia Conflict source missing: {source}")
        self._source_compatibility_preflight(source)
        project_root = source.parent
        self._park_project_modules(project_root)

        showbase_module = importlib.import_module("direct.showbase.ShowBase")
        messenger_global = importlib.import_module("direct.showbase.MessengerGlobal")
        real_showbase = showbase_module.ShowBase

        context = _BridgeContext(self)
        context.scene_root = self.host.render.attachNewNode("utopia-conflict-native-scene")
        context.task_proxy = _TaskCaptureProxy(getattr(self.host, "taskMgr"), self)
        context.window_proxy = _WindowProxy(getattr(self.host, "win", None), self)
        context.ui_before = self._snapshot_ui()
        self._context = context
        self._scene_root = context.scene_root
        context.messenger_proxy = _MessengerCaptureProxy(getattr(messenger_global, "messenger", None), context)
        context.base_proxy = _HostedBaseProxy(self, context)
        hosted_showbase = self._make_hosted_showbase_class(real_showbase, context)

        settings = dict(self._runtime_settings)
        responder = _runtime_stub(settings)
        self._install_runtime_context(hosted_showbase, responder)

        module_name = f"utopia_conflict_full_source_{int(time.time() * 1000)}"
        spec = importlib.util.spec_from_file_location(module_name, source)
        if spec is None or spec.loader is None:
            self._restore_runtime_context()
            raise ImportError(f"Unable to load Utopia Conflict source spec: {source}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        self._module_name = module_name
        try:
            with self._project_runtime_cwd():
                spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(module_name, None)
            self._restore_project_modules()
            self._restore_runtime_context()
            raise

        self._track_project_modules(project_root)
        try:
            game_class = self._discover_game_class(module, hosted_showbase, project_root)
        except Exception:
            self._restore_project_modules()
            self._restore_runtime_context()
            raise
        self._module = module
        return game_class

    def _apply_audio_mix(self):
        master = max(0.0, min(1.0, float(self._runtime_settings.get("master_volume", 1.0))))
        sfx = max(0.0, min(1.0, float(self._runtime_settings.get("sfx_volume", 1.0))))
        music = max(0.0, min(1.0, float(self._runtime_settings.get("music_volume", 1.0))))
        self._context.saved_sfx_volumes = []
        for mgr in list(getattr(self.host, "sfxManagerList", []) or []):
            old = _safe_call(mgr.getVolume)
            self._context.saved_sfx_volumes.append((mgr, old))
            _safe_call(mgr.setVolume, master * sfx)
        mgr = getattr(self.host, "musicManager", None)
        if mgr is not None:
            self._context.saved_music_volume = _safe_call(mgr.getVolume)
            _safe_call(mgr.setVolume, master * music)
        # Real source audio owns this visit; generic HoloVerse native beds do not stack.
        audio = getattr(self.host, "audio", None)
        if audio is not None:
            _safe_call(audio.stop_loop, "native_dimension_music")
            _safe_call(audio.stop_loop, "native_dimension_air")

    def _restore_audio_mix(self):
        if self._context is None:
            return
        for mgr, old in self._context.saved_sfx_volumes:
            if old is not None:
                _safe_call(mgr.setVolume, old)
        mgr = getattr(self.host, "musicManager", None)
        if mgr is not None and self._context.saved_music_volume is not None:
            _safe_call(mgr.setVolume, self._context.saved_music_volume)

    def _original_host_messenger(self):
        state = dict(self._runtime_patch_state or {})
        try:
            return state.get("globals", {}).get(("messenger", "messenger"))
        except Exception:
            return None

    def _bind_source_events_to_host_messenger(self):
        """Mirror captured source bindings onto the real Panda messenger.

        Utopia Conflict is constructed behind an isolated messenger proxy so its
        imports cannot trample HoloVerse. Once construction is complete, the
        source event names are exposed directly to the physical input stream.
        TAB is the sole event intentionally withheld for HoloVerse return.
        """
        messenger = self._original_host_messenger()
        if messenger is None or self._context is None:
            return 0
        count = 0
        for event in sorted(self._context.events):
            if str(event).strip().lower() == "tab":
                continue
            try:
                messenger.accept(str(event), self, self._dispatch, [str(event)], 1)
                count += 1
            except Exception:
                pass
        self._host_input_bound = bool(count)
        return count

    def _unbind_source_events_from_host_messenger(self):
        messenger = self._original_host_messenger()
        if messenger is not None:
            try:
                messenger.ignoreAll(self)
            except Exception:
                pass
        self._host_input_bound = False

    def enter(self):
        if self._entered:
            return
        try:
            game_class = self._load_source_module()
        except Exception as exc:
            print(f"utopia_conflict_native_enter_failed stage=source_load err={exc.__class__.__name__}:{exc}")
            raise
        try:
            with self._project_runtime_cwd():
                self._apply_audio_mix()
                self.delegate = game_class()
        except Exception as exc:
            print(f"utopia_conflict_native_enter_failed stage=game_construct err={exc.__class__.__name__}:{exc}")
            self._restore_runtime_context()
            self._restore_project_modules()
            raise
        self._track_project_modules(self.entry_path.parent)
        self._rebind_project_globals(self.entry_path.parent)
        self._ui_nodes = self._collect_new_ui(self._context.ui_before)
        direct_input_count = self._bind_source_events_to_host_messenger()
        # Source HUD and buttons are authoritative for the visit. HoloVerse keeps
        # only TAB and does not force its HUD preference into the dimension.
        self._entered = True
        self._started_at = time.monotonic()
        print(
            "utopia_conflict_native_enter "
            f"captured_tasks={len(self._captured_tasks)} events={len(self._context.events)} direct_inputs={direct_input_count} "
            f"pass39_features={self._source_features} second_showbase=0 second_window=0"
        )

    def _run_captured_tasks(self, dt: float):
        elapsed = max(0.0, time.monotonic() - self._started_at)
        # Stable sort mirrors Panda's basic sort ordering for the source tasks.
        items = sorted(list(self._captured_tasks.items()), key=lambda kv: (int(kv[1].get("sort") or 0), int(kv[1].get("sequence") or 0)))
        for name, item in items:
            handle = item.get("handle")
            callback = item.get("callback")
            if handle is None or handle.removed or not callable(callback):
                continue
            if item.get("delayed") and elapsed < float(handle.next_run or 0.0):
                continue
            handle.time = elapsed
            handle.frame = self._frame_index
            extra = list(item.get("extraArgs") or [])
            append_task = bool(item.get("appendTask", False))
            try:
                with self._project_runtime_cwd():
                    if extra:
                        args = extra + ([handle] if append_task else [])
                        result = callback(*args)
                    else:
                        result = callback(handle)
            except TypeError:
                # Some project helpers register a zero-argument callback.
                with self._project_runtime_cwd():
                    result = callback()
            except SystemExit:
                _safe_call(self.host.return_from_native_mode, reason="utopia_conflict_source_exit")
                return
            except Exception as exc:
                print(f"utopia_conflict_task_error task={name} err={exc.__class__.__name__}:{exc}")
                _safe_call(self.host.return_from_native_mode, reason="utopia_conflict_runtime_error")
                return
            done = result in (getattr(handle, "done", object()), "done")
            again = result in (getattr(handle, "again", object()), "again")
            if done:
                self._context.task_proxy.remove(name)
            elif item.get("delayed"):
                if again:
                    handle.next_run = elapsed + max(0.0, float(handle.delayTime or 0.0))
                else:
                    item["delayed"] = False

    def update(self, dt: float):
        if not self._entered or self.delegate is None:
            return
        self._frame_index += 1
        self._run_captured_tasks(float(dt or 0.0))

    def _dispatch(self, event: str, *sent_args) -> bool:
        if self._context is None:
            return False
        with self._project_runtime_cwd():
            return self._context.dispatch_event(event, *sent_args)

    def on_host_action(self, action: str) -> bool:
        action = str(action or "").strip().lower()
        if action in {"escape", "pause", "menu", "return", "return_to_core", "tab"}:
            return False
        if action == "toggle_dimension_ui":
            return self._dispatch("h")
        if action.startswith("number_"):
            return self._dispatch(action.split("_", 1)[1])
        # The host sends held inputs as key/key_up and discrete inputs literally.
        event_map = {
            "w":"w", "w_up":"w-up", "a":"a", "a_up":"a-up",
            "s":"s", "s_up":"s-up", "d":"d", "d_up":"d-up",
            "shift":"shift", "shift_up":"shift-up", "space":"space", "space_up":"space-up",
            "control":"control", "control_up":"control-up",
            "arrow_left":"arrow_left", "arrow_left_up":"arrow_left-up",
            "arrow_right":"arrow_right", "arrow_right_up":"arrow_right-up",
            "arrow_up":"arrow_up", "arrow_up_up":"arrow_up-up",
            "arrow_down":"arrow_down", "arrow_down_up":"arrow_down-up",
            "q":"q", "q_down":"q", "q_up":"q-up", "e":"e", "e_down":"e", "e_up":"e-up",
            "mouse1":"mouse1", "mouse1_up":"mouse1-up", "mouse3":"mouse3", "mouse3_up":"mouse3-up",
            "h":"h", "m":"m", "f":"f", "enter":"enter",
            "r":"r", "t":"t", "v":"v", "g":"g", "i":"i", "j":"j", "k":"k", "l":"l", "u":"u", "o":"o",
            "y":"y", "p":"p", "b":"b", "c":"c", "n":"n",
            "f1":"f1", "f3":"f3", "f4":"f4", "f5":"f5", "f6":"f6", "f7":"f7", "f8":"f8", "f9":"f9", "f10":"f10", "f11":"f11", "f12":"f12",
            "shift-f8":"shift-f8", "shift-t":"shift-t", "shift-y":"shift-y", "shift-v":"shift-v", "shift-p":"shift-p", "shift-r":"shift-r",
            "wheel_up":"wheel_up", "wheel_down":"wheel_down", "z":"z", "x":"x",
        }
        event = event_map.get(action)
        return self._dispatch(event) if event else False

    def toggle_dimension_ui(self) -> bool:
        return self._dispatch("h")

    def _stop_dimension_audio(self):
        d = self.delegate
        if d is None:
            return
        for snd in list((getattr(d, "sfx", {}) or {}).values()):
            _safe_call(getattr(snd, "stop", lambda: None))
        for attr in ("music", "battle_music", "ambience", "ambient_sound"):
            snd = getattr(d, attr, None)
            if snd is not None:
                _safe_call(getattr(snd, "stop", lambda: None))

    def get_diagnostics(self) -> dict:
        data = dict(self._diagnostics)
        data.update({
            "entered": self._entered,
            "elapsed": max(0.0, time.monotonic() - self._started_at) if self._started_at else 0.0,
            "captured_tasks": sorted(self._captured_tasks),
            "captured_events": sorted(self._context.events) if self._context else [],
            "window_mutation_requests_blocked": self._window_mutation_requests,
            "source_features": dict(self._source_features),
            "runtime_settings": dict(self._runtime_settings),
        })
        if self.delegate is not None:
            for attr in ("runtime_mode", "battle_wave", "player_health", "player_max_health", "player_armor", "player_max_armor", "armor_hits"):
                if hasattr(self.delegate, attr): data[attr] = getattr(self.delegate, attr)
        return data

    def get_holoverse_result(self) -> dict:
        if self.delegate is None:
            return {"completed": False, "reason": "not_entered"}
        # Preserve Utopia Conflict's own mission/result authority.  This bridge
        # reports useful state but never invents completion/capture outcomes.
        result = {
            "completed": False,
            "world": "Utopia Conflict",
            "runtime_mode": str(getattr(self.delegate, "runtime_mode", "")),
            "battle_wave": int(getattr(self.delegate, "battle_wave", 0) or 0),
        }
        for name in ("player_health", "player_max_health", "player_armor", "player_max_armor", "armor_hits"):
            if hasattr(self.delegate, name):
                try: result[name] = float(getattr(self.delegate, name))
                except Exception: result[name] = str(getattr(self.delegate, name))
        return result

    def exit(self):
        if not self._entered and self.delegate is None and self._scene_root is None:
            return
        self._stop_dimension_audio()
        self._unbind_source_events_from_host_messenger()
        if self._context is not None:
            self._context.capture_ignore_all()
        leftovers = list(self._ui_nodes)
        if self._context is not None:
            leftovers += [n for n in self._collect_new_ui(self._context.ui_before) if n not in leftovers]
        for node in leftovers:
            try:
                if node is not None and not node.isEmpty(): node.removeNode()
            except Exception:
                pass
        self._ui_nodes.clear()
        if self._scene_root is not None:
            try:
                if not self._scene_root.isEmpty():
                    self._scene_root.clearFog(); self._scene_root.clearLight(); self._scene_root.removeNode()
            except Exception:
                pass
        self._scene_root = None
        self._restore_audio_mix()
        self.delegate = None
        self._captured_tasks.clear()
        self._entered = False
        if self._module_name:
            sys.modules.pop(self._module_name, None)
        self._module = None
        self._restore_project_modules()
        self._restore_runtime_context()
        print("utopia_conflict_native_exit clean=1")

    def destroy(self): self.exit()
    def cleanup(self): self.exit()


def create_mode(host, mode=None, entry_path=None, label=MODE_TITLE):
    return HoloVerseNativeMode(host, mode=mode, entry_path=entry_path, label=label)


def create_native_adapter(host, mode=None, entry_path=None, label=MODE_TITLE):
    return create_mode(host, mode=mode, entry_path=entry_path, label=label)

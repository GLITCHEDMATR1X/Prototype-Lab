"""Full-source HoloVerse native adapter for HoloUtopia.

This adapter mounts the real linked HoloUtopia / Holo-Utopia Civic Ring
Panda3D project under HoloVerse's existing ShowBase lifecycle.  It does not
rebuild, approximate, or replace HoloUtopia's streamed worlds, building tools,
weapons, actors, HUD, or internal modes.

The linked source may be a direct CommandHubApp entry or a thin launcher.
Runtime discovery is therefore wrapper-safe: project-local modules are loaded
inside a visit-long isolated Panda3D context and the real most-derived
CommandHubApp-style application class is selected after import.
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

MODE_ID = "holoutopia"
MODE_TITLE = "HoloUtopia // Holo-Utopia Civic Ring"
ADAPTER_VERSION = "1.2-pass03-authority-scoring"


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

    HoloUtopia's older workbench helpers may import the global Panda
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
        self.constructed_instances = []

    def capture_accept(self, event, method, extraArgs=None, persistent=1):
        self.events[str(event)] = (method, list(extraArgs or []))
        return None

    def capture_ignore(self, event):
        self.events.pop(str(event), None)

    def capture_ignore_all(self):
        self.events.clear()

    def request_return(self, *args, **kwargs):
        _safe_call(self.host.return_from_native_mode, reason="holoutopia_source_exit")

    def dispatch_event(self, event):
        item = self.events.get(str(event))
        if not item:
            return False
        method, extra = item
        try:
            method(*extra)
            return True
        except SystemExit:
            self.request_return()
            return True
        except Exception as exc:
            print(f"holoutopia_event_error event={event} err={exc.__class__.__name__}:{exc}")
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
        "hud_visible": bool(read("launch_hud_visible", True)),
        "graphics_quality": str(read("graphics_quality", "high") or "high"),
        "mouse_sensitivity": float(read("launch_game_mouse_sensitivity", 0.16) or 0.16),
        "invert_y": bool(read("launch_invert_y", False)),
        "controller_deadzone": float(read("launch_controller_deadzone", 0.15) or 0.15),
        "fov": float(read("fov", 82.0) or 82.0),
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
        self._host_clear_color = None
        self._source_cfg_original = {}
        self._source_save_config = None
        self._source_config_module = None
        self._prior_local_modules: dict[str, object] = {}
        self._loaded_local_module_names: set[str] = set()
        self._window_mutation_requests = 0
        self._source_features = {}
        self._runtime_patch_state = {}
        self._runtime_path_added = False
        self._runtime_stub_module = None
        self._runtime_env_prior = {}
        self._preconstructed_delegate = None
        self._audio_mix_applied = False
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

    def _snapshot_ui(self):
        root = getattr(self.host, "aspect2d", None)
        if root is None:
            return set()
        try:
            return {child.node() for child in root.getChildren()}
        except Exception:
            return set()

    def _collect_new_ui(self, before):
        root = getattr(self.host, "aspect2d", None)
        if root is None:
            return []
        out = []
        try:
            for child in root.getChildren():
                try:
                    if child.node() not in before:
                        out.append(child)
                except Exception:
                    pass
        except Exception:
            pass
        return out

    def _source_compatibility_preflight(self, source: Path):
        """Inventory HoloUtopia without brittle entry-file rejection.

        HoloUtopia may be linked through a wrapper ``main.py`` while the real
        ``CommandHubApp`` lives in another project-local module.  Compatibility
        is decided from project-local runtime classes after import, not by
        demanding tokens in the selected entry file.
        """
        project_root = source.parent
        if not source.exists():
            raise FileNotFoundError(f"HoloUtopia source missing: {source}")
        candidates = [source]
        excluded_parts = {"tools", "verification", "saves", "logs", "__pycache__", ".git", ".venv", "venv", "dist", "build"}
        for py in sorted(project_root.rglob("*.py")):
            try:
                rel = py.relative_to(project_root)
            except Exception:
                rel = Path(py.name)
            if any(part in excluded_parts or part.startswith(".") for part in rel.parts[:-1]):
                continue
            if py.name in {"holoverse_native_adapter.py"} or py.name.startswith(("validate_", "smoke_", "test_")):
                continue
            if py not in candidates:
                candidates.append(py)
        texts=[]; scanned=[]; seen=set()
        for py in candidates[:96]:
            try: rp=py.resolve()
            except Exception: rp=py
            if rp in seen: continue
            seen.add(rp)
            try: text=py.read_text(encoding="utf-8",errors="ignore")
            except Exception: continue
            texts.append(text[:2_500_000])
            try: scanned.append(str(py.relative_to(project_root)))
            except Exception: scanned.append(py.name)
        lower="\n".join(texts).lower()
        try: entry_lower=source.read_text(encoding="utf-8",errors="ignore").lower()
        except Exception: entry_lower=""
        marker_map={
            "command_hub_app":"commandhubapp" in lower,
            "utopia_civic_ring":"holo-utopia civic ring" in lower or "world_specs" in lower and "utopia" in lower,
            "streamed_worlds":"update_world_chunks" in lower,
            "player_update":"update_player" in lower,
            "weapon_system":"setup_weapon_system" in lower or "update_weapon_viewmodels" in lower,
            "building_system":"user_buildings" in lower or "build_cell_under_reticle" in lower,
        }
        self._source_features={
            **marker_map,
            "internal_modes":"activate_internal_mode" in lower or "internalmodestate" in lower,
            "underwater_region":"aqua abyss" in lower or "underwater_vehicle" in lower,
            "space_region":"void fleet" in lower or "kind\": \"space" in lower,
            "gamepad_support":"setup_gamepad" in lower,
            "scanned_python_files":scanned,
            "entry_is_wrapper":"commandhubapp" not in entry_lower,
        }
        print("holoutopia_source_inventory entry="+str(source)+" files="+str(len(scanned))+" markers="+",".join(k for k,v in marker_map.items() if v))
        return True

    def _discover_game_class(self, entry_module, hosted_showbase, project_root: Path):
        """Find the real gameplay authority, not merely the first ShowBase.

        Pass02 could accept an empty bootstrap ``main()`` because any captured
        ShowBase instance received an effectively unbeatable score.  Pass03
        ranks project files/classes structurally first and scores constructed
        instances by actual runtime ownership (tasks, events, scene content,
        gameplay/update methods and source complexity).  Thin/bootstrap apps
        are rejected and discovery continues until a credible game authority
        is found.
        """
        import ast

        excluded_parts = {"tools", "verification", "saves", "logs", "__pycache__", ".git", ".venv", "venv", "dist", "build"}
        source_inventory = {}

        def module_name_for_path(py: Path):
            rel=py.relative_to(project_root).with_suffix("")
            parts=list(rel.parts)
            if len(parts)==1:
                return parts[0],True
            parent=project_root
            for part in parts[:-1]:
                parent=parent/part
                if not (parent/"__init__.py").exists():
                    return "_holoutopia_probe_"+"_".join(parts),False
            return ".".join(parts),True

        def static_score(py: Path):
            try:
                text=py.read_text(encoding="utf-8",errors="ignore")
            except Exception:
                return 0, {"bytes":0,"lines":0,"classes":0,"functions":0,"signals":[]}
            low=text.lower()
            try:
                tree=ast.parse(text, filename=str(py))
                classes=sum(isinstance(n,ast.ClassDef) for n in ast.walk(tree))
                functions=sum(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) for n in ast.walk(tree))
            except Exception:
                classes=text.count("class ")
                functions=text.count("def ")
            score=0
            signals=[]
            # Runtime/Panda structure.
            for token,pts,label in (
                ("showbase",500,"showbase"),("panda3d",240,"panda3d"),
                ("taskmgr",180,"tasks"),("directgui",100,"directgui"),
                ("globalclock",80,"clock"),("collision",80,"collision"),
                ("loader.load",70,"assets"),("attachnewnode",70,"scene"),
                ("setbackgroundcolor",30,"background"),
            ):
                if token in low:
                    score+=pts; signals.append(label)
            # Generic gameplay authority; no HoloUtopia-specific names required.
            for token,pts,label in (
                ("def update",240,"update"),("def update_task",320,"update_task"),
                ("def update_player",220,"player"),("def setup_scene",170,"scene_setup"),
                ("def setup_ui",120,"ui_setup"),("def setup_input",120,"input_setup"),
                ("def setup_controls",100,"controls"),("def refresh_ui",70,"ui_refresh"),
                ("def rebuild",60,"rebuild"),("def save",30,"save"),
                ("self.accept(",100,"events"),("self.taskmgr.add",140,"task_add"),
                ("world",35,"world"),("player",35,"player_state"),("camera",30,"camera"),
            ):
                if token in low:
                    score+=pts; signals.append(label)
            # Rich source is more likely to be the actual game than a 20-line launcher.
            lines=text.count("\n")+1
            score += min(360, lines//12)
            score += min(180, functions*5)
            score += min(120, classes*15)
            rel=str(py.relative_to(project_root)).replace("\\","/")
            name=py.name.lower()
            if name=="main.py":
                # main.py is only a slight preference, never authority by itself.
                score+=20
            if any(x in name for x in ("adapter","validate","smoke","test_")):
                score-=1000
            info={"bytes":len(text.encode("utf-8",errors="ignore")),"lines":lines,"classes":classes,"functions":functions,"signals":sorted(set(signals)),"static_score":score,"rel":rel}
            source_inventory[rel]=info
            return score,info

        all_files=[]
        for rel in list(self._source_features.get("scanned_python_files",[])):
            py=(project_root/rel)
            try:
                relative=py.relative_to(project_root)
            except Exception:
                continue
            if not py.is_file() or any(part in excluded_parts or part.startswith(".") for part in relative.parts[:-1]):
                continue
            score,info=static_score(py)
            all_files.append((score,info.get("lines",0),str(relative),py))
        all_files.sort(key=lambda item:(item[0],item[1]),reverse=True)
        self._source_features["authority_inventory"]=[
            {"file":rel,"score":score,"lines":lines,"signals":source_inventory.get(rel,{}).get("signals",[])}
            for score,lines,rel,_ in all_files[:24]
        ]
        print("holoutopia_authority_inventory "+" | ".join(
            f"{rel}:score={score}:lines={lines}" for score,lines,rel,_ in all_files[:12]
        ))

        def import_project_file(py: Path):
            module_name,use_regular=module_name_for_path(py)
            if module_name in sys.modules:
                return module_name
            with self._project_runtime_cwd():
                if use_regular:
                    importlib.import_module(module_name)
                else:
                    spec=importlib.util.spec_from_file_location(module_name,py)
                    if spec is None or spec.loader is None:
                        raise ImportError(f"Unable to create module spec for {py}")
                    module=importlib.util.module_from_spec(spec)
                    sys.modules[module_name]=module
                    try:
                        spec.loader.exec_module(module)
                    except Exception:
                        sys.modules.pop(module_name,None)
                        raise
            return module_name

        def class_score(obj, mod, static_hint=0):
            score=100 + int(static_hint*0.35)
            name_low=str(getattr(obj,"__name__","")).lower()
            if name_low in ("showbase","holoversehostedholoutopiashowbase"):
                return -10000
            if any(tok in name_low for tok in ("app","game","world","hub","simulation","observatory","utopia")):
                score+=120
            for method,pts in (
                ("update_task",320),("update",240),("update_player",220),
                ("setup_scene",170),("setup_ui",120),("setup_input",120),
                ("setup_controls",100),("refresh_ui",70),("save_settings",30),
            ):
                if callable(getattr(obj,method,None)): score+=pts
            # Rich class bodies decisively beat a nearly empty launcher subclass.
            try:
                own=sum(1 for k,v in obj.__dict__.items() if callable(v) and not k.startswith("__"))
                score+=min(500,own*9)
            except Exception:
                own=0
            return score

        def collect_candidates():
            modules=[entry_module]
            for name in sorted(self._loaded_local_module_names):
                mod=sys.modules.get(name)
                if mod is not None and mod not in modules:
                    modules.append(mod)
            found=[]; seen=set()
            for mod in modules:
                mpath=_module_path(mod)
                if mod is not entry_module and not _is_under(mpath,project_root):
                    continue
                hint=0
                try:
                    rel=str(Path(mpath).resolve().relative_to(project_root)).replace("\\","/")
                    hint=int(source_inventory.get(rel,{}).get("static_score",0))
                except Exception:
                    rel="?"
                for attr_name,obj in list(getattr(mod,"__dict__",{}).items()):
                    if not isinstance(obj,type) or id(obj) in seen:
                        continue
                    seen.add(id(obj))
                    try:
                        if obj is hosted_showbase or not issubclass(obj,hosted_showbase):
                            continue
                    except Exception:
                        continue
                    score=class_score(obj,mod,hint)
                    found.append((score,obj,getattr(mod,"__name__","?"),rel))
            return found

        def runtime_instance_score(inst, origin="unknown"):
            cls=inst.__class__
            score=class_score(cls,sys.modules.get(cls.__module__),0)
            # Runtime evidence: a real game normally creates tasks/events/scene nodes.
            task_count=len(self._captured_tasks)
            event_count=len(self._context.events)
            scene_count=0
            try:
                scene_count=int(self._scene_root.getNumChildren())
            except Exception:
                try: scene_count=len(list(self._scene_root.getChildren()))
                except Exception: scene_count=0
            ui_count=0
            try: ui_count=len(self._collect_new_ui(self._context.ui_before))
            except Exception: pass
            score += min(700,task_count*180)
            score += min(360,event_count*18)
            score += min(520,scene_count*55)
            score += min(240,ui_count*30)
            # Attribute richness distinguishes an initialized world from an empty shell.
            try:
                attr_count=len(getattr(inst,"__dict__",{}))
            except Exception:
                attr_count=0
            score += min(360,attr_count*4)
            evidence={"origin":origin,"class":cls.__name__,"module":cls.__module__,"score":int(score),"tasks":task_count,"events":event_count,"scene_children":scene_count,"ui_nodes":ui_count,"attributes":attr_count}
            print("holoutopia_runtime_authority "+" ".join(f"{k}={v}" for k,v in evidence.items()))
            return score,evidence

        def cleanup_rejected_instance(inst, checkpoint):
            # Remove tasks/events/nodes created by a rejected bootstrap so the real
            # authority starts from a clean dimension scene.
            prior_tasks,prior_events,prior_instances,prior_scene_children=checkpoint
            for name in list(self._captured_tasks):
                if name not in prior_tasks:
                    self._context.task_proxy.remove(name)
            for name in list(self._context.events):
                if name not in prior_events:
                    self._context.events.pop(name,None)
            try:
                children=list(self._scene_root.getChildren())
                for child in children[prior_scene_children:]:
                    _safe_call(child.removeNode)
            except Exception:
                pass
            while len(self._context.constructed_instances)>prior_instances:
                self._context.constructed_instances.pop()
            # Best-effort source cleanup, but never userExit()/sys.exit().
            for method in ("cleanup","destroy","shutdown","stop"):
                fn=getattr(inst,method,None)
                if callable(fn):
                    _safe_call(fn)
                    break

        def checkpoint():
            try: scene_children=int(self._scene_root.getNumChildren())
            except Exception:
                try: scene_children=len(list(self._scene_root.getChildren()))
                except Exception: scene_children=0
            return set(self._captured_tasks),set(self._context.events),len(self._context.constructed_instances),scene_children

        AUTHORITY_THRESHOLD=650
        fallback_imports=[]

        # 1) Import high-authority project modules BEFORE trusting wrapper main().
        # This specifically prevents an empty main.py bootstrap from winning.
        for score,_,rel,py in all_files:
            if py.resolve()==self.entry_path.resolve():
                continue
            # Low-information helpers are still attempted later if necessary.
            if score < 180:
                continue
            try:
                module_name=import_project_file(py)
                fallback_imports.append(module_name)
                self._track_project_modules(project_root)
            except SystemExit as exc:
                print(f"holoutopia_discovery_import_system_exit module={rel} code={getattr(exc,'code',None)}")
            except Exception as exc:
                print(f"holoutopia_discovery_import_failed module={rel} err={exc.__class__.__name__}:{exc}")

        candidates=collect_candidates()
        if candidates:
            candidates.sort(key=lambda item:item[0],reverse=True)
            for score,game_class,module_name,rel in candidates:
                if score < AUTHORITY_THRESHOLD:
                    continue
                self._source_features.update({
                    "runtime_class":getattr(game_class,"__name__",str(game_class)),
                    "runtime_class_module":module_name,
                    "runtime_class_score":int(score),
                    "fallback_imports":fallback_imports,
                    "launch_attempts":[],
                    "discovery_mode":"authority_structural_class",
                    "authority_source":rel,
                })
                print(f"holoutopia_runtime_class class={self._source_features['runtime_class']} module={module_name} score={score} discovery=authority_structural_class source={rel}")
                return game_class

        # 2) Follow wrapper launch paths, but accept a constructed app ONLY when
        # it has real runtime authority. Empty bootstrap apps are discarded.
        launch_attempts=[]
        launch_names=("main","launch","start","run_game","create_app","build_app","make_app")
        for name in launch_names:
            fn=getattr(entry_module,name,None)
            if not callable(fn) or getattr(fn,"__module__",getattr(entry_module,"__name__",None)) != getattr(entry_module,"__name__",None):
                continue
            launch_attempts.append(name)
            cp=checkpoint()
            before=len(self._context.constructed_instances)
            result=None
            try:
                if not self._audio_mix_applied:
                    self._apply_audio_mix(); self._audio_mix_applied=True
                with self._project_runtime_cwd():
                    result=fn()
            except SystemExit as exc:
                print(f"holoutopia_launch_probe_system_exit function={name} code={getattr(exc,'code',None)}")
            except TypeError as exc:
                print(f"holoutopia_launch_probe_skipped function={name} err=TypeError:{exc}")
                continue
            except Exception as exc:
                print(f"holoutopia_launch_probe_failed function={name} err={exc.__class__.__name__}:{exc}")
                continue
            if result is not None:
                try:
                    if isinstance(result,hosted_showbase) and result not in self._context.constructed_instances:
                        self._context.constructed_instances.append(result)
                except Exception:
                    pass
            new_instances=self._context.constructed_instances[before:]
            # Score strongest newly-created instance instead of first/last blindly.
            scored=[]
            for inst in new_instances:
                rscore,evidence=runtime_instance_score(inst,origin=f"entry:{name}")
                scored.append((rscore,inst,evidence))
            scored.sort(key=lambda x:x[0],reverse=True)
            if scored and scored[0][0] >= AUTHORITY_THRESHOLD:
                rscore,inst,evidence=scored[0]
                self._preconstructed_delegate=inst
                cls=inst.__class__
                self._source_features.update({
                    "runtime_class":cls.__name__,"runtime_class_module":cls.__module__,
                    "runtime_class_score":int(rscore),"fallback_imports":fallback_imports,
                    "launch_attempts":launch_attempts,"discovery_mode":"entry_launch_authority",
                    "authority_runtime_evidence":evidence,
                })
                print(f"holoutopia_runtime_instance class={cls.__name__} module={cls.__module__} score={rscore} discovery=entry_launch_authority")
                return cls
            for _,inst,evidence in scored:
                print(f"holoutopia_bootstrap_rejected class={inst.__class__.__name__} score={evidence['score']} tasks={evidence['tasks']} events={evidence['events']} scene_children={evidence['scene_children']}")
                cleanup_rejected_instance(inst,cp)

        # 3) Exhaustively import remaining safe modules, then choose richest class.
        imported=set(fallback_imports)
        for score,_,rel,py in all_files:
            if py.resolve()==self.entry_path.resolve():
                continue
            module_name,_=module_name_for_path(py)
            if module_name in imported:
                continue
            try:
                module_name=import_project_file(py)
                fallback_imports.append(module_name); imported.add(module_name)
                self._track_project_modules(project_root)
            except SystemExit as exc:
                print(f"holoutopia_discovery_import_system_exit module={rel} code={getattr(exc,'code',None)}")
            except Exception as exc:
                print(f"holoutopia_discovery_import_failed module={rel} err={exc.__class__.__name__}:{exc}")

        candidates=collect_candidates()
        candidates.sort(key=lambda item:item[0],reverse=True)
        if candidates:
            score,game_class,module_name,rel=candidates[0]
            if score >= AUTHORITY_THRESHOLD:
                self._source_features.update({
                    "runtime_class":getattr(game_class,"__name__",str(game_class)),
                    "runtime_class_module":module_name,"runtime_class_score":int(score),
                    "fallback_imports":fallback_imports,"launch_attempts":launch_attempts,
                    "discovery_mode":"exhaustive_authority_class","authority_source":rel,
                })
                print(f"holoutopia_runtime_class class={self._source_features['runtime_class']} module={module_name} score={score} discovery=exhaustive_authority_class source={rel}")
                return game_class

        inventory=self._source_features.get("authority_inventory",[])
        raise RuntimeError(
            "No non-bootstrap HoloUtopia game authority found. The linked folder may contain only an empty main.py/adapter files; "
            f"entry={self.entry_path.name} authority_inventory={inventory[:12]} "
            f"loaded_local_modules={sorted(self._loaded_local_module_names)[:32]} launch_attempts={launch_attempts}. "
            "Install the real HoloUtopia game source in this linked folder (for older Observatory builds this is the large CommandHubApp source, often a versioned main_v*.py file)."
        )

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
                # Do not attach/detach physical devices from the host lifecycle.
                # The source may still read already-present gamepad state directly.
                self.attachInputDevice = lambda *a, **k: True
                self.detachInputDevice = lambda *a, **k: True
                # Record real application construction even when a thin wrapper
                # hides the class inside a factory or launch function.
                context.constructed_instances.append(self)

            def run(self, *args, **kwargs):
                # Standalone launchers commonly call app.run().  HoloVerse owns
                # the only frame loop, so native discovery must never block here.
                return None

        HostedShowBase.__name__ = "HoloVerseHostedHoloUtopiaShowBase"
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

        Keep these patched for the entire visit because HoloUtopia may perform
        deferred imports, add tasks, load relative assets, or reference Panda's
        global ShowBase/task/messenger objects after construction.
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
            raise FileNotFoundError(f"HoloUtopia source missing: {source}")
        self._source_compatibility_preflight(source)
        project_root = source.parent
        self._park_project_modules(project_root)

        showbase_module = importlib.import_module("direct.showbase.ShowBase")
        messenger_global = importlib.import_module("direct.showbase.MessengerGlobal")
        real_showbase = showbase_module.ShowBase

        context = _BridgeContext(self)
        context.scene_root = self.host.render.attachNewNode("holoutopia-native-scene")
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

        module_name = f"holoutopia_full_source_{int(time.time() * 1000)}"
        spec = importlib.util.spec_from_file_location(module_name, source)
        if spec is None or spec.loader is None:
            self._restore_runtime_context()
            raise ImportError(f"Unable to load HoloUtopia source spec: {source}")
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

    def _snapshot_host_presentation(self):
        self._host_clear_color = None
        try:
            win=getattr(self.host,"win",None)
            if win is not None and hasattr(win,"getClearColor"):
                self._host_clear_color=win.getClearColor()
        except Exception:
            self._host_clear_color=None

    def _restore_host_presentation(self):
        if self._host_clear_color is None: return
        try:
            win=getattr(self.host,"win",None)
            if win is not None and hasattr(win,"setClearColor"):
                win.setClearColor(self._host_clear_color)
        except Exception:
            pass

    def _sync_host_settings_to_delegate(self):
        """Borrow HoloVerse presentation/audio preferences without rewriting source defaults."""
        d=self.delegate
        if d is None: return
        cfg=getattr(d,"cfg",None)
        self._source_cfg_original={}
        self._source_save_config=None
        self._source_config_module=None
        if cfg is None: return
        owner_mod=sys.modules.get(getattr(d.__class__,"__module__",""))
        if owner_mod is not None and callable(getattr(owner_mod,"save_config",None)):
            self._source_save_config=getattr(owner_mod,"save_config")
            self._source_config_module=owner_mod
        mapping={
            "mouse_sensitivity":self._runtime_settings.get("mouse_sensitivity"),
            "hud_visible":self._runtime_settings.get("hud_visible"),
            "fov":self._runtime_settings.get("fov"),
            "master_volume":self._runtime_settings.get("master_volume"),
            "music_volume":self._runtime_settings.get("music_volume"),
            "sfx_volume":self._runtime_settings.get("sfx_volume"),
            "ambience_volume":self._runtime_settings.get("ambience_volume"),
            "launch_width":self._runtime_settings.get("width"),
            "launch_height":self._runtime_settings.get("height"),
            "launch_fullscreen":self._runtime_settings.get("fullscreen"),
            "launch_borderless":self._runtime_settings.get("borderless"),
            "launch_game_mouse_sensitivity":self._runtime_settings.get("mouse_sensitivity"),
            "launch_invert_y":self._runtime_settings.get("invert_y"),
            "launch_hud_visible":self._runtime_settings.get("hud_visible"),
            "launch_graphics_quality":self._runtime_settings.get("graphics_quality"),
            "launch_controller_deadzone":self._runtime_settings.get("controller_deadzone"),
        }
        for name,value in mapping.items():
            if value is None or not hasattr(cfg,name): continue
            try:
                self._source_cfg_original[name]=getattr(cfg,name)
                setattr(cfg,name,value)
            except Exception: pass
        # Source actions call module-level save_config().  Keep HoloVerse-owned
        # display/audio fields transient even if the player saves a HoloUtopia-
        # specific option while mounted.  Game-specific values still persist.
        if self._source_config_module is not None and callable(self._source_save_config):
            original_fn=self._source_save_config
            original_values=self._source_cfg_original
            def hosted_safe_save_config(config):
                active={}
                for field,original in original_values.items():
                    try:
                        active[field]=getattr(config,field)
                        setattr(config,field,original)
                    except Exception: pass
                try:
                    return original_fn(config)
                finally:
                    for field,value in active.items():
                        try: setattr(config,field,value)
                        except Exception: pass
            try: self._source_config_module.save_config=hosted_safe_save_config
            except Exception: pass
        try: d.hud_visible=bool(self._runtime_settings.get("hud_visible",True))
        except Exception: pass
        try:
            lens=getattr(d,"camLens",None)
            if lens is not None: lens.setFov(float(self._runtime_settings.get("fov",82.0)))
        except Exception: pass

    def _restore_source_settings(self):
        d=self.delegate
        cfg=getattr(d,"cfg",None) if d is not None else None
        if cfg is None: return
        for name,value in dict(getattr(self,"_source_cfg_original",{})).items():
            try: setattr(cfg,name,value)
            except Exception: pass
        fn=getattr(self,"_source_save_config",None)
        mod=getattr(self,"_source_config_module",None)
        if mod is not None and callable(fn):
            try: mod.save_config=fn
            except Exception: pass
        if callable(fn):
            try:
                with self._project_runtime_cwd(): fn(cfg)
            except Exception: pass

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
        self._audio_mix_applied = False

    def enter(self):
        if self._entered:
            return
        self._snapshot_host_presentation()
        try:
            game_class = self._load_source_module()
        except Exception as exc:
            print(f"holoutopia_native_enter_failed stage=source_load err={exc.__class__.__name__}:{exc}")
            raise
        try:
            with self._project_runtime_cwd():
                if not self._audio_mix_applied:
                    self._apply_audio_mix()
                    self._audio_mix_applied = True
                if self._preconstructed_delegate is not None:
                    self.delegate = self._preconstructed_delegate
                else:
                    self.delegate = game_class()
                self._sync_host_settings_to_delegate()
        except Exception as exc:
            print(f"holoutopia_native_enter_failed stage=game_construct err={exc.__class__.__name__}:{exc}")
            self._restore_runtime_context()
            self._restore_project_modules()
            raise
        self._track_project_modules(self.entry_path.parent)
        self._rebind_project_globals(self.entry_path.parent)
        self._ui_nodes = self._collect_new_ui(self._context.ui_before)
        # The host's HUD preference is authoritative. Use the real source toggle
        # rather than hiding arbitrary DirectGUI nodes so source layout stays intact.
        if not bool(self._runtime_settings.get("hud_visible", True)):
            try:
                if bool(getattr(self.delegate, "hud_visible", True)):
                    fn = getattr(self.delegate, "toggle_hud", None)
                    if callable(fn): fn()
            except Exception:
                pass
        self._entered = True
        self._started_at = time.monotonic()
        print(
            "holoutopia_native_enter "
            f"captured_tasks={len(self._captured_tasks)} events={len(self._context.events)} "
            f"source_features={self._source_features} second_showbase=0 second_window=0"
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
                _safe_call(self.host.return_from_native_mode, reason="holoutopia_source_exit")
                return
            except Exception as exc:
                print(f"holoutopia_task_error task={name} err={exc.__class__.__name__}:{exc}")
                _safe_call(self.host.return_from_native_mode, reason="holoutopia_runtime_error")
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

    def _dispatch(self, event: str) -> bool:
        if self._context is None:
            return False
        with self._project_runtime_cwd():
            return self._context.dispatch_event(event)

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
            for attr in ("active_artifact_id", "world_unlocked", "hud_visible", "player_yaw", "player_pitch"):
                if hasattr(self.delegate, attr): data[attr] = getattr(self.delegate, attr)
            try: data["user_building_count"] = len(getattr(self.delegate, "user_buildings", {}) or {})
            except Exception: pass
            try: data["internal_mode"] = str(getattr(getattr(self.delegate, "internal_mode", None), "mode_key", "") or "")
            except Exception: pass
        return data

    def get_holoverse_result(self) -> dict:
        if self.delegate is None:
            return {"completed":False,"reason":"not_entered"}
        d=self.delegate
        result={"completed":False,"world":"HoloUtopia"}
        try:
            spec=d.current_world_spec() if callable(getattr(d,"current_world_spec",None)) else {}
            result["world_name"]=str((spec or {}).get("name", ""))
            result["world_kind"]=str((spec or {}).get("kind", ""))
        except Exception: pass
        result["active_artifact_id"]=getattr(d,"active_artifact_id",None)
        result["world_unlocked"]=bool(getattr(d,"world_unlocked",False))
        try: result["user_building_count"]=len(getattr(d,"user_buildings",{}) or {})
        except Exception: result["user_building_count"]=0
        mode=getattr(getattr(d,"internal_mode",None),"mode_key","")
        result["internal_mode"]=str(mode or "")
        return result

    def exit(self):
        if not self._entered and self.delegate is None and self._scene_root is None:
            return
        self._stop_dimension_audio()
        if self._context is not None:
            self._context.capture_ignore_all()
        for node in list(self._ui_nodes):
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
        self._restore_source_settings()
        self._restore_audio_mix()
        self._restore_host_presentation()
        self.delegate = None
        self._captured_tasks.clear()
        self._entered = False
        if self._module_name:
            sys.modules.pop(self._module_name, None)
        self._module = None
        self._restore_project_modules()
        self._restore_runtime_context()
        print("holoutopia_native_exit clean=1")

    def destroy(self): self.exit()
    def cleanup(self): self.exit()


def create_mode(host, mode=None, entry_path=None, label=MODE_TITLE):
    return HoloVerseNativeMode(host, mode=mode, entry_path=entry_path, label=label)


def create_native_adapter(host, mode=None, entry_path=None, label=MODE_TITLE):
    return create_mode(host, mode=mode, entry_path=entry_path, label=label)

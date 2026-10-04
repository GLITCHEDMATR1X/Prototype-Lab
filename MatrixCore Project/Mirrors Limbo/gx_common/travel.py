"""Mirror's Limbo world travel: confirmed process takeover between the linked worlds.

Mirror's Limbo, DreamCatcher and Andrew's Nightmare each run as their own Panda3D
process. Travel launches the destination, waits for it to report ready, then the
source exits. This module is the single copy used by all three games; it lives in
the Mirror's Limbo root and the nested worlds mount it through ``gx_common.mount``.

Discovery uses the fixed integrated layout inside Mirror's Limbo first, so stray
copies elsewhere in the Prototype Lab can never be picked up by mistake.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

LIMBO_ROOT = Path(__file__).resolve().parents[1]
IDS = {'mirrors_limbo', 'dreamcatcher_alternate', 'andrews_nightmare'}
# Integrated home of each world, relative to the Mirror's Limbo root.
LAYOUT = {
    'mirrors_limbo': '.',
    'dreamcatcher_alternate': 'DreamCatcher',
    'andrews_nightmare': 'DreamCatcher/modes/andrews_nightmare',
}
SKIP = {'node_modules', '.git', '__pycache__', '.venv', 'venv', 'assets'}
SESSION_KEEP = 8                 # newest travel session folders kept for diagnostics
SESSION_MAX_AGE = 2 * 24 * 3600  # older folders are always removed
READY_TIMEOUT = 120.0


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, data):
    path = Path(path)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2), encoding='utf-8')
    os.replace(tmp, path)


def inside(path, parent):
    return Path(path).resolve().is_relative_to(Path(parent).resolve())


def world_at(directory):
    directory = Path(directory).resolve()
    data = read_json(directory / 'gx_world.json')
    if data.get('schema') != 'gx.world.takeover.v1' or data.get('id') not in IDS:
        raise ValueError('Unsupported GX world manifest')
    entry = (directory / data['entry']).resolve()
    if not inside(entry, directory) or not entry.is_file() or entry.suffix not in ('.py', '.pyw'):
        raise ValueError('GX world has no valid local Python entry')
    if data.get('engine') != 'panda3d' or data.get('panda3d') != '1.10.16':
        raise ValueError('GX world requires a different runtime')
    return dict(data, root=directory, entry_path=entry)


def _scan(root, target):
    found = []
    for count, (folder, dirs, files) in enumerate(os.walk(root, followlinks=False)):
        if count >= 5000:
            break
        dirs[:] = sorted(d for d in dirs if d.lower() not in SKIP
                         and not (Path(folder) / d).is_symlink())
        if 'gx_world.json' not in files:
            continue
        try:
            world = world_at(folder)
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if world['id'] == target:
            found.append(world)
    return found


def discover(target):
    """Return (world, lab_root) for a linked world inside this Mirror's Limbo install."""
    if target not in IDS:
        raise ValueError('Unknown GX world')
    home = LIMBO_ROOT / LAYOUT[target]
    try:
        world = world_at(home)
        if world['id'] == target:
            return world, LIMBO_ROOT
    except (OSError, ValueError, KeyError, TypeError):
        pass
    # The world was moved inside Mirror's Limbo: bounded scan of this install only.
    matches = _scan(LIMBO_ROOT, target)
    if len(matches) > 1:
        names = '; '.join(str(x['root'].relative_to(LIMBO_ROOT)) for x in matches)
        raise RuntimeError(f'Multiple copies found inside Mirror\'s Limbo: {names}. Keep one.')
    if matches:
        return matches[0], LIMBO_ROOT
    raise FileNotFoundError(f'{target} is missing from Mirror\'s Limbo ({LAYOUT[target]}).')


def user_root():
    if os.name == 'nt':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    else:
        base = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share'))
    path = base / 'GLITCHED_MATRIX' / 'GXTravel'
    path.mkdir(parents=True, exist_ok=True)
    return path


def prune_sessions(keep=None):
    """Remove old travel session folders. Folders still in use are skipped silently."""
    keep_set = {Path(p).resolve() for p in (keep or ()) if p}
    try:
        folders = sorted((p for p in user_root().iterdir() if p.is_dir()),
                         key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return 0
    now = time.time()
    removed = 0
    for index, folder in enumerate(folders):
        if folder.resolve() in keep_set:
            continue
        try:
            age = now - folder.stat().st_mtime
        except OSError:
            continue
        if index >= SESSION_KEEP or age > SESSION_MAX_AGE:
            shutil.rmtree(folder, ignore_errors=True)
            removed += 1
    return removed


def process_alive(pid):
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        api = ctypes.WinDLL('kernel32', use_last_error=True)
        api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        api.OpenProcess.restype = wintypes.HANDLE
        api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        api.WaitForSingleObject.restype = wintypes.DWORD
        api.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = api.OpenProcess(0x00100000, False, int(pid))
        if not handle:
            return ctypes.get_last_error() == 5
        try:
            return api.WaitForSingleObject(handle, 0) == 0x00000102
        finally:
            api.CloseHandle(handle)
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


class RuntimeLease:
    """Freeze project callbacks/audio/input while engine events can still run.

    Outgoing travel keeps the window visible behind a loading cover, so the player never
    sees the desktop and the new window is allowed to take focus on Windows. Exclusive
    fullscreen is the exception: it is minimized so two fullscreen windows never fight.
    """
    ENGINE_TASKS = {'resetPrevTransform', 'dataLoop', 'eventManager', 'igLoop',
                    'audioLoop', 'garbageCollectStates'}

    def __init__(self, base, outgoing=False, title=''):
        from panda3d.core import ClockObject, WindowProperties
        self.base, self.tasks, self.managers, self.buttons = base, [], [], []
        self.released = False
        self.cover = None
        clock = ClockObject.getGlobalClock()
        self.normal_clock = clock.getMode() == ClockObject.MNormal
        if self.normal_clock:
            clock.setMode(ClockObject.MLimited)
            clock.setFrameRate(20)
        sleepers = set(base.taskMgr.getDoLaters())
        now = clock.getFrameTime()
        for task in base.taskMgr.getAllTasks():
            if task.getName() in self.ENGINE_TASKS or task.getName().startswith('gx-travel-'):
                continue
            delay = max(0, task.getWakeTime() - now) if task in sleepers else 0
            self.tasks.append((task, delay))
            base.taskMgr.remove(task)
        for manager in [*base.sfxManagerList, base.musicManager]:
            self.managers.append((manager, manager.getActive()))
            manager.setActive(False)
        for thrower in base.buttonThrowers or []:
            node = thrower.node()
            self.buttons.append((node, node.getPrefix()))
            node.setPrefix('gx-blocked-')
        self.window_active = base.win.isActive()
        self.hidden = False
        if hasattr(base.win, 'requestProperties'):
            self.properties = WindowProperties(base.win.getProperties())
            # Startup display/cursor requests may still be waiting for a frame.
            self.properties.addProperties(base.win.getRequestedProperties())
            props = WindowProperties()
            props.setCursorHidden(False)
            props.setMouseMode(WindowProperties.M_absolute)
            if outgoing and self.properties.getFullscreen():
                props.setMinimized(True)
                self.hidden = True
            base.win.requestProperties(props)
        else:
            self.properties = None
        if outgoing and not self.hidden:
            self._show_cover(title)
        if self.hidden:
            base.win.setActive(False)

    def _show_cover(self, title):
        try:
            from panda3d.core import CardMaker, CullBinEnums, CullBinManager, TextNode
            base = self.base
            bins = CullBinManager.getGlobalPtr()
            if bins.findBin('gx-travel-cover') < 0:
                # Drawn after every GUI bin (unsorted=50, gui-popup=60) so pause menus stay hidden.
                bins.addBin('gx-travel-cover', CullBinEnums.BT_fixed, 1000)
            root = base.render2d.attachNewNode('gx-travel-cover')
            root.setBin('gx-travel-cover', 0)
            root.setDepthTest(False)
            root.setDepthWrite(False)
            card = CardMaker('gx-travel-cover-card')
            card.setFrameFullscreenQuad()
            node = root.attachNewNode(card.generate())
            node.setColor(0, 0, 0, 1)
            text = TextNode('gx-travel-cover-text')
            text.setText(f'{title.upper()}  ...' if title else '...')
            text.setAlign(TextNode.ACenter)
            text.setTextColor(0.62, 0.68, 0.66, 1)
            label = base.aspect2d.attachNewNode(text)
            label.setScale(0.045)
            label.setPos(0, 0, -0.02)
            label.setBin('gx-travel-cover', 1)
            label.setDepthTest(False)
            self.cover = (root, label)
        except Exception:
            self.cover = None

    def release(self):
        if self.released:
            return
        from panda3d.core import ClockObject, WindowProperties
        self.released = True
        base = self.base
        if self.cover:
            for node in self.cover:
                node.removeNode()
            self.cover = None
        for task, delay in self.tasks:
            task.setDelay(delay)
            base.taskMgr.add(task)
        for manager, active in self.managers:
            manager.setActive(active)
        for node, prefix in self.buttons:
            node.setPrefix(prefix)
        if self.normal_clock:
            ClockObject.getGlobalClock().setMode(ClockObject.MNormal)
        base.win.setActive(self.window_active)
        if self.properties:
            # Restore only the properties this lease changed. Replaying the
            # startup snapshot can shrink a newly resized borderless window.
            props = WindowProperties()
            props.setCursorHidden(self.properties.getCursorHidden())
            props.setMouseMode(self.properties.getMouseMode())
            props.setMinimized(False)
            props.setForeground(True)
            base.win.requestProperties(props)


class WorldTravel:
    def __init__(self, base, root, world_id, *, before_leave, on_error, activate, retire=None):
        self.base, self.root, self.world_id = base, Path(root).resolve(), world_id
        self.before_leave, self.on_error, self.activate = before_leave, on_error, activate
        self.retire = retire or base.userExit
        self.process = None
        self.lease = None
        self.committed = False
        self.incoming = None
        self.request = None
        self.stack = []
        self.last_error = None
        self.log_stream = None
        self.session = None
        self._closed = False
        directory = os.environ.pop('GX_TRAVEL_SESSION', '')
        if directory:
            self.incoming = Path(directory)
            request = read_json(self.incoming / 'request.json')
            if (request.get('schema') != 1 or request.get('target') != world_id
                    or Path(request.get('entry', '')).resolve() != world_at(self.root)['entry_path']
                    or not request.get('token') or not inside(self.root, request['lab_root'])):
                raise ValueError('Incoming GX travel does not match this game')
            self.request = request
            self.stack = list(request['back_stack'])
            if any(x not in IDS for x in self.stack):
                raise ValueError('Invalid GX return history')
        prune_sessions(keep=[self.incoming])
        self.old_exit = getattr(base, 'exitFunc', None)
        base.exitFunc = self._exit_cleanup
        if os.environ.get('GX_TRAVEL_QA') == '1':
            from gx_common.travel_qa import attach
            attach(self)

    @property
    def busy(self):
        return self.process is not None or self.incoming is not None

    @property
    def return_target(self):
        return self.stack[-1] if self.stack else None

    @property
    def arrived_from(self):
        """World that launched this process, or None for a direct launch."""
        return self.request.get('source') if self.request else None

    def _exit_cleanup(self):
        self.close()
        if callable(self.old_exit):
            self.old_exit()

    def start_receiving(self):
        if not self.incoming:
            return
        self.lease = RuntimeLease(self.base)
        self.started = time.monotonic()
        self.ready_frames = 0
        self.base.taskMgr.add(self._receive, 'gx-travel-receive', sort=100)

    def _receive(self, task):
        self.ready_frames += 1
        if self.ready_frames == 2:
            write_json(self.incoming / 'ready.json', {'token': self.request['token'],
                'pid': os.getpid(), 'world': self.world_id, 'entry': str(world_at(self.root)['entry_path'])})
            print('GX_TRAVEL READY', self.world_id, os.getpid(), flush=True)
        commit = self.incoming / 'commit.json'
        if commit.is_file():
            data = read_json(commit)
            if data.get('token') != self.request['token']:
                raise ValueError('GX travel commit token mismatch')
            self.incoming = None
            self.lease.release()
            self.lease = None
            self.activate()
            print('GX_TRAVEL ACTIVE', self.world_id, os.getpid(), flush=True)
            return task.done
        if time.monotonic() - self.started > READY_TIMEOUT + 5 or not process_alive(self.request['source_pid']):
            # No ownership transfer was committed; this child must not remain orphaned.
            self.base.userExit()
            return task.done
        return task.cont

    def go(self, target, *, returning=False):
        if self.busy:
            return False
        self.last_error = None
        try:
            if target == self.world_id:
                raise ValueError('Already in the requested world')
            world, lab_root = discover(target)
            self.before_leave()
            self.session = user_root() / uuid.uuid4().hex
            self.session.mkdir()
            self.token = uuid.uuid4().hex
            stack = self.stack[:-1] if returning and self.return_target == target else [*self.stack, self.world_id]
            request = {'schema': 1, 'token': self.token, 'source': self.world_id,
                'target': target, 'source_pid': os.getpid(), 'entry': str(world['entry_path']),
                'lab_root': str(lab_root), 'back_stack': stack}
            write_json(self.session / 'request.json', request)
            env = dict(os.environ, GX_TRAVEL_SESSION=str(self.session),
                       PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
            for key in ('HOLOVERSE_EMBEDDED_MODE', 'GX_GENERIC_LAUNCHER', 'GX_GAME_ROOT',
                        'DREAMCATCHER_BRIDGE_DIR', 'MIRRORS_LIMBO_STANDALONE', 'GX_LAB_ROOT'):
                env.pop(key, None)
            command = [sys.executable, str(world['entry_path'])]
            command += getattr(self, '_qa_child_args', [])
            self.log_stream = (self.session / 'destination.log').open('w', encoding='utf-8')
            self.lease = RuntimeLease(self.base, outgoing=True, title=str(world.get('title', '')))
            self.process = subprocess.Popen(command, cwd=str(world['root']), env=env,
                stdin=subprocess.DEVNULL, stdout=self.log_stream, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            self.started = time.monotonic()
            self.base.taskMgr.doMethodLater(.1, self._poll, 'gx-travel-outgoing')
            print('GX_TRAVEL START', self.world_id, target, world['entry_path'], flush=True)
            return True
        except Exception as exc:
            self._fail(str(exc))
            return False

    def back(self):
        if self.return_target:
            return self.go(self.return_target, returning=True)
        return False

    def _poll(self, task):
        code = self.process.poll()
        if code is not None:
            self._fail(f'Destination exited before takeover (code {code}). Logs: {self.session}')
            return task.done
        ready = self.session / 'ready.json'
        if ready.is_file():
            try:
                value = read_json(ready)
                request = read_json(self.session / 'request.json')
                if (value.get('token') != self.token or value.get('pid') != self.process.pid
                        or value.get('world') != request['target'] or value.get('entry') != request['entry']):
                    raise ValueError('Destination readiness does not match this launch')
                write_json(self.session / 'commit.json', {'token': self.token})
            except (OSError, ValueError) as exc:
                self._fail(str(exc))
                return task.done
            self.committed = True
            print('GX_TRAVEL RETIRE', self.world_id, os.getpid(), flush=True)
            self.retire()
            return task.done
        if time.monotonic() - self.started > READY_TIMEOUT:
            self._fail('Destination did not finish starting. Previous game restored.')
            return task.done
        return task.again

    def _stop_pending_child(self):
        if self.process and not self.committed and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)

    def _fail(self, message):
        self.last_error = message
        self._stop_pending_child()
        self.process = None
        if self.log_stream:
            self.log_stream.close()
            self.log_stream = None
        if self.lease:
            self.lease.release()
            self.lease = None
        print('GX_TRAVEL FAILED', message, flush=True)
        self.on_error(message)

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._stop_pending_child()
        if self.log_stream:
            self.log_stream.close()
            self.log_stream = None

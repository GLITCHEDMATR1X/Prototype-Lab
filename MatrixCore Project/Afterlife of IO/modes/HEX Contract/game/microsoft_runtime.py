from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import sys


BRIDGE_FILENAME = "HEXContractGDKBridge.dll"
STAGING_FILENAME = "HEX_CONTRACT_XBOX_SERVICE_STAGING.json"


class MicrosoftRuntime:
    """Optional Windows GDK bridge.

    The portable/source build never requires this DLL. A packaged Microsoft build
    can place HEXContractGDKBridge.dll and the generated staging sidecar beside
    HEXContract.exe. If initialization fails, the game falls back to its normal
    portable behavior instead of blocking launch.
    """

    def __init__(self) -> None:
        self.ready = False
        self.save_root: Path | None = None
        self.status = "PORTABLE / GDK BRIDGE NOT ACTIVE"
        self._dll = None
        self._base_dir: Path | None = None

    @staticmethod
    def _runtime_base(project_root: Path) -> Path:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path(project_root)

    @classmethod
    def autodetect(cls, project_root: Path) -> "MicrosoftRuntime":
        runtime = cls()
        if os.name != "nt":
            runtime.status = "NON-WINDOWS / GDK BRIDGE SKIPPED"
            return runtime

        base = cls._runtime_base(project_root)
        runtime._base_dir = base
        sidecar = base / STAGING_FILENAME
        bridge = base / BRIDGE_FILENAME
        if not sidecar.is_file() or not bridge.is_file():
            runtime.status = "WINDOWS PORTABLE / NO GDK PACKAGE BRIDGE"
            return runtime

        try:
            data = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            runtime.status = "GDK SIDECAR INVALID / PORTABLE FALLBACK"
            return runtime
        if not bool(data.get("native_bridge_enabled", False)):
            runtime.status = "GDK SIDECAR PRESENT / NATIVE BRIDGE DISABLED"
            return runtime
        scid = str(data.get("scid", "")).strip()
        if not scid:
            runtime.status = "GDK SIDECAR MISSING SCID / PORTABLE FALLBACK"
            return runtime

        try:
            dll = ctypes.WinDLL(str(bridge))
            cls._bind(dll)
            rc = int(dll.HC_GDK_Initialize(scid.encode("utf-8")))
            if rc != 1:
                runtime.status = "GDK INITIALIZE FAILED / " + cls._last_error(dll)
                return runtime
            runtime._dll = dll
            runtime.ready = True
            runtime.save_root = runtime._read_save_root(refresh=False)
            runtime.status = "MICROSOFT GDK ONLINE" if runtime.save_root else "GDK ONLINE / SAVE ROOT UNAVAILABLE"
        except Exception as exc:
            runtime.ready = False
            runtime._dll = None
            runtime.status = f"GDK BRIDGE LOAD FAILED / {type(exc).__name__}"
        return runtime

    @staticmethod
    def _bind(dll) -> None:
        dll.HC_GDK_Initialize.argtypes = [ctypes.c_char_p]
        dll.HC_GDK_Initialize.restype = ctypes.c_int32
        dll.HC_GDK_GetSaveRoot.argtypes = [ctypes.c_char_p, ctypes.c_uint32]
        dll.HC_GDK_GetSaveRoot.restype = ctypes.c_int32
        dll.HC_GDK_RefreshSaveRoot.argtypes = [ctypes.c_char_p, ctypes.c_uint32]
        dll.HC_GDK_RefreshSaveRoot.restype = ctypes.c_int32
        dll.HC_GDK_UpdateAchievement.argtypes = [ctypes.c_char_p, ctypes.c_uint32]
        dll.HC_GDK_UpdateAchievement.restype = ctypes.c_int32
        dll.HC_GDK_GetLastError.argtypes = [ctypes.c_char_p, ctypes.c_uint32]
        dll.HC_GDK_GetLastError.restype = ctypes.c_int32
        dll.HC_GDK_Shutdown.argtypes = []
        dll.HC_GDK_Shutdown.restype = None

    @staticmethod
    def _last_error(dll) -> str:
        buf = ctypes.create_string_buffer(1024)
        try:
            dll.HC_GDK_GetLastError(buf, len(buf))
            return buf.value.decode("utf-8", errors="replace") or "UNKNOWN ERROR"
        except Exception:
            return "UNKNOWN ERROR"

    def _read_save_root(self, refresh: bool) -> Path | None:
        if not self.ready or self._dll is None:
            return None
        buf = ctypes.create_string_buffer(1024)
        fn = self._dll.HC_GDK_RefreshSaveRoot if refresh else self._dll.HC_GDK_GetSaveRoot
        rc = int(fn(buf, len(buf)))
        if rc != 1:
            self.status = "GDK SAVE REFRESH FAILED / " + self._last_error(self._dll)
            return None
        text = buf.value.decode("utf-8", errors="replace").strip()
        if not text:
            return None
        return Path(text)

    def refresh_save_root(self) -> Path | None:
        new_root = self._read_save_root(refresh=True)
        if new_root is not None:
            self.save_root = new_root
            self.status = "MICROSOFT GDK ONLINE / SAVE LOCK REFRESHED"
        return new_root

    def update_achievement(self, partner_id: str, percent: int) -> bool:
        if not self.ready or self._dll is None:
            return False
        pct = max(1, min(100, int(percent)))
        try:
            return int(self._dll.HC_GDK_UpdateAchievement(str(partner_id).encode("utf-8"), pct)) == 1
        except Exception:
            return False

    def shutdown(self) -> None:
        if self._dll is not None:
            try:
                self._dll.HC_GDK_Shutdown()
            except Exception:
                pass
        self.ready = False
        self._dll = None

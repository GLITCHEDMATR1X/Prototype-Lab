from __future__ import annotations

import importlib.util
import os
import sys
import time
from pathlib import Path

ADAPTER_ID = "glyphbound_holoverse_native_v1"
HOST_CONTRACT = "holoverse_dimension_v1"


class HoloVerseNativeMode:
    """Mount the real Glyphbound runtime into HoloVerse's existing ShowBase.

    The adapter never creates a ShowBase or a second OS window. HoloVerse owns
    TAB and the lifecycle; Glyphbound owns every other local gameplay binding
    while this mode is active.
    """

    def __init__(self, host, mode=None, entry_path=None, label="Glyphbound", **_kwargs):
        self.host = host
        self.mode = dict(mode or {})
        self.entry_path = Path(entry_path or (Path(__file__).resolve().parent / "main.py")).resolve()
        self.label = str(label or "Glyphbound")
        self.root = self.entry_path.parent
        self.game_module = None
        self.game = None
        self.return_requested = ""
        self.entered_at = 0.0
        self._destroyed = False
        self._host_ui_restore = {}
        self._result = {
            "signal": "GLYPHBOUND_LINKED",
            "completed": False,
            "score_delta": 0,
            "dimension": "glyphbound",
            "adapter_id": ADAPTER_ID,
        }

    def _load_game_module(self):
        module_name = f"glyphbound_native_runtime_{int(time.time() * 1000)}"
        spec = importlib.util.spec_from_file_location(module_name, self.entry_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load Glyphbound runtime: {self.entry_path}")
        module = importlib.util.module_from_spec(spec)
        old = os.environ.get("GLYPHBOUND_HOLOVERSE_NATIVE")
        os.environ["GLYPHBOUND_HOLOVERSE_NATIVE"] = "1"
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(module_name, None)
            raise
        finally:
            if old is None:
                os.environ.pop("GLYPHBOUND_HOLOVERSE_NATIVE", None)
            else:
                os.environ["GLYPHBOUND_HOLOVERSE_NATIVE"] = old
        self._module_name = module_name
        return module

    def _request_return(self, reason="glyphbound-return"):
        # Do not tear the host down from inside Glyphbound's frame function.
        # HoloVerse will process this immediately after the frame returns.
        self.return_requested = str(reason or "glyphbound-return")

    def enter(self):
        if self.game is not None:
            return
        # HoloVerse normally enters dimensions from live gameplay, but keep the
        # adapter safe even if a developer launches it while a title/ending
        # modal is visible.  Record and hide only these pre-existing full-screen
        # host roots so Glyphbound never renders underneath an opaque host UI.
        for attr in ("campaign_title_root", "campaign_ending_root", "campaign_settings_root"):
            node = getattr(self.host, attr, None)
            if node is None:
                continue
            try:
                hidden = bool(node.isHidden())
                self._host_ui_restore[attr] = hidden
                node.hide()
            except Exception:
                pass
        self.game_module = self._load_game_module()
        game_cls = getattr(self.game_module, "Glyphbound")
        self.game = game_cls(host_base=self.host, hosted_return_callback=self._request_return)
        self.entered_at = time.monotonic()
        print(f"glyphbound_native_enter adapter={ADAPTER_ID} root={self.root}")

    def update(self, dt):
        if self._destroyed or self.game is None:
            return
        self.game.hosted_update(dt)
        if self.return_requested:
            reason = self.return_requested
            self.return_requested = ""
            self.host.return_from_native_mode(reason=reason)

    def get_result(self):
        game = self.game
        result = dict(self._result)
        if game is not None:
            result.update({
                "completed": bool(getattr(game, "prototype_complete", False)),
                "sigils": int(getattr(game, "sigils", 0) or 0),
                "currency": int(getattr(game, "currency", 0) or 0),
                "world_seed": int(getattr(game, "world_seed", 0) or 0),
                "biome": str(getattr(game, "current_biome", "") or ""),
            })
            if result["completed"]:
                result["signal"] = "GLYPHBOUND_SHRINE_COMPLETE"
        return result

    def exit(self):
        if self._destroyed:
            return
        self._destroyed = True
        game = self.game
        self.game = None
        if game is not None:
            try:
                game.shutdown_hosted()
            except Exception as exc:
                print(f"glyphbound_native_cleanup_error:{exc.__class__.__name__}:{exc}")
        name = str(getattr(self, "_module_name", "") or "")
        if name:
            sys.modules.pop(name, None)
        self.game_module = None
        for attr, was_hidden in list(self._host_ui_restore.items()):
            node = getattr(self.host, attr, None)
            try:
                if node is not None and not was_hidden:
                    node.show()
            except Exception:
                pass
        self._host_ui_restore.clear()
        print(f"glyphbound_native_exit adapter={ADAPTER_ID}")

    destroy = exit


def create_mode(host, mode=None, entry_path=None, label="Glyphbound", **kwargs):
    return HoloVerseNativeMode(host, mode=mode, entry_path=entry_path, label=label, **kwargs)

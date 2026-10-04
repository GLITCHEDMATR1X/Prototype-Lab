"""In-world HoloSpace Region runtime bridge.

Orbit and MatrixCore do not launch a separate HoloSpace app. This installer adds
a live route that calls the existing HoloVerse Region 8 warp/cockpit system.
"""
from __future__ import annotations

import sys

IN_WORLD_ROUTE = "in_world_region"
HOLOSPACE_REGION_NUMBER = 8


def _main_module(cls):
    return sys.modules.get(cls.__module__) or sys.modules.get("__main__")


def install_holospace_region_runtime(CommandHubApp):
    main = _main_module(CommandHubApp)
    if main is None:
        return

    from holoverse_mode_runtime import install_in_world_route_aliases

    install_in_world_route_aliases(main)

    def _enter_holospace(self, *, source: str = "holospace_region_runtime") -> bool:
        try:
            if getattr(self, "core_console_open", False):
                self.close_core_console()
            self.center_hint["text"] = "MATRIXCORE -> HOLOSPACE // LIVE REGION WARP"
            return bool(self.travel_to_holoverse_region_index(HOLOSPACE_REGION_NUMBER, source=source, force=True))
        except Exception as exc:
            try:
                print(f"holospace_region_runtime_error:{exc.__class__.__name__}:{exc}")
            except Exception:
                pass
            try:
                self.center_hint["text"] = "MATRIXCORE // HOLOSPACE REGION ROUTE FAILED"
            except Exception:
                pass
            return False

    def activate_holospace_region_from_mode(self, mode=None, *, source: str = "core", route: str = IN_WORLD_ROUTE) -> bool:
        try:
            self.record_matrixcore_dimension_signal(
                "dimension_in_world_dispatch",
                "HoloSpace Region",
                label="HoloSpace Region",
                route=str(route or IN_WORLD_ROUTE),
                source=str(source or "core"),
                reason="holospace_live_region",
            )
        except Exception:
            pass
        return bool(_enter_holospace(self, source=str(source or "core")))

    # Install only if the host does not already carry the method; Pass107 keeps a
    # root fallback in main.py so older/runtime-stripped builds still work.
    if not hasattr(CommandHubApp, "enter_holospace_region_from_matrixcore"):
        CommandHubApp.enter_holospace_region_from_matrixcore = _enter_holospace
    CommandHubApp.activate_holospace_region_from_mode = activate_holospace_region_from_mode

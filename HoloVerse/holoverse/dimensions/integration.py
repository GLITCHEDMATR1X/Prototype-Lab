from __future__ import annotations

import math
from pathlib import Path

from .registry import DimensionRegistry


def _resolve_dimensions_root(root: Path) -> Path:
    """Return the host-owned Dimensions directory without assuming OS casing."""
    root = Path(root)
    preferred = root / "Dimensions"
    if preferred.exists():
        return preferred
    legacy = root / "dimensions"
    if legacy.exists():
        return legacy
    return preferred


def install_dimension_integration(
    command_hub_app,
    *,
    root: Path,
    vec3_cls,
    centered_gleebs_helper=None,
) -> None:
    """Install the established Pass264–266 dimension/Gleebs host hooks.

    Pass 271 moves ownership out of the root ``main.py`` while intentionally
    preserving the public behavior of the accepted hooks.  Native dimension
    lifecycle methods remain on ``CommandHubApp`` in this pass; only registry
    bootstrapping, Gleebs archive interception, and archive modal isolation are
    extracted here.
    """
    if bool(getattr(command_hub_app, "_hv271_dimension_integration_installed", False)):
        return
    command_hub_app._hv271_dimension_integration_installed = True

    dimensions_root = _resolve_dimensions_root(Path(root))

    # HV264_DIMENSION_DOCK_BEGIN — moved from main.py in Pass 271.
    original_init = command_hub_app.__init__

    def dimension_registry_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        try:
            self.dimension_registry = DimensionRegistry(self, dimensions_root).start()
        except Exception as exc:
            self.dimension_registry = None
            print(f"dimension_registry_init_failed err={exc}")

    command_hub_app.__init__ = dimension_registry_init
    # HV264_DIMENSION_DOCK_END

    # HV265_GLEEBS_DIMENSION_ARCHIVE_BEGIN — moved from main.py in Pass 271.
    original_interact = command_hub_app.interact

    def gleebs_centered(self):
        helper = centered_gleebs_helper
        if callable(helper):
            try:
                if helper(self, 6.5):
                    return True
            except Exception:
                pass
        try:
            origin = self.head_world_pos()
            forward, _right, _up = self.get_view_basis()
            forward.normalize()
            render = getattr(self, "render", None)
            if render is None:
                return False
            candidates = []
            for attr in ("gleebs", "gleebs_root", "gleebs_node", "gleebs_actor", "companion_gleebs"):
                node = getattr(self, attr, None)
                if node is not None and hasattr(node, "getPos"):
                    candidates.append(node)
            try:
                for node in render.findAllMatches("**/*"):
                    name = str(node.getName() or "").lower()
                    if "gleeb" in name or "gleep" in name:
                        candidates.append(node)
            except Exception:
                pass
            seen = set()
            for node in candidates:
                try:
                    key = int(node.getKey()) if hasattr(node, "getKey") else id(node)
                    if key in seen or (hasattr(node, "isEmpty") and node.isEmpty()):
                        continue
                    seen.add(key)
                    target = node.getPos(render) - origin
                    distance = target.length()
                    if distance <= 0.001 or distance > 6.5:
                        continue
                    direction = vec3_cls(target)
                    direction.normalize()
                    dot = float(forward.dot(direction))
                    cross = math.sqrt(max(0.0, 1.0 - dot * dot)) * distance
                    if dot >= 0.88 and cross <= 1.55:
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        return False

    def interact(self, *args, **kwargs):
        registry = getattr(self, "dimension_registry", None)
        if registry is not None and getattr(registry, "menu_open", False):
            return True
        if registry is not None and getattr(self, "active_native_mode", None) is None and gleebs_centered(self):
            def talk_after_menu():
                return original_interact(self, *args, **kwargs)

            try:
                if registry.open_gleebs_menu(talk_callback=talk_after_menu):
                    return True
            except Exception as exc:
                print(f"gleebs_dimension_menu_failed err={exc}")
        return original_interact(self, *args, **kwargs)

    command_hub_app.interact = interact

    # Pass 282.27: dimension spheres remain the same physical front-end to
    # the same registry launch contract.  Mouse1 checks the aimed sphere before
    # falling through to Core/bot/artifact interaction; E remains unchanged.
    original_primary_click = command_hub_app.primary_click_interact

    def primary_click_interact(self, *args, **kwargs):
        registry = getattr(self, "dimension_registry", None)
        observatory = getattr(registry, "observatory", None) if registry is not None else None
        if observatory is not None and getattr(self, "active_native_mode", None) is None:
            try:
                if observatory.activate_focused():
                    return
            except Exception as exc:
                print(f"dimension_observatory_click_failed err={exc}")
        return original_primary_click(self, *args, **kwargs)

    command_hub_app.primary_click_interact = primary_click_interact
    # HV265_GLEEBS_DIMENSION_ARCHIVE_END

    # HV266_GLEEBS_ARCHIVE_IMMERSION_BEGIN — moved from main.py in Pass 271.
    original_start_escape_hold = command_hub_app.start_escape_hold
    original_toggle_menu = command_hub_app.toggle_menu
    original_toggle_holomap = command_hub_app.toggle_holomap_transition
    original_handle_h = command_hub_app.handle_h_action
    original_toggle_help = command_hub_app.toggle_help_overlay
    original_q_down = command_hub_app.on_q_down
    original_refresh_ui = command_hub_app.refresh_ui

    def archive_open(self):
        registry = getattr(self, "dimension_registry", None)
        return bool(registry is not None and getattr(registry, "menu_open", False))

    def start_escape_hold(self):
        if archive_open(self):
            try:
                self.dimension_registry.close_menu()
            except Exception as exc:
                print(f"dimension_archive_escape_close_failed err={exc}")
            return
        return original_start_escape_hold(self)

    def toggle_menu(self):
        if archive_open(self):
            try:
                self.dimension_registry.close_menu()
            except Exception as exc:
                print(f"dimension_archive_menu_close_failed err={exc}")
            return
        return original_toggle_menu(self)

    def toggle_holomap(self):
        if archive_open(self):
            return
        return original_toggle_holomap(self)

    def handle_h(self):
        if archive_open(self):
            return
        return original_handle_h(self)

    def toggle_help(self):
        if archive_open(self):
            return
        return original_toggle_help(self)

    def q_down(self):
        if archive_open(self):
            try:
                self.set_key("q", True)
            except Exception:
                pass
            return
        return original_q_down(self)

    def refresh_ui(self):
        result = original_refresh_ui(self)
        if archive_open(self):
            for attr in ("hud_root", "crosshair_root", "safety_exit_root"):
                node = getattr(self, attr, None)
                try:
                    if node is not None:
                        node.hide()
                except Exception:
                    pass
        return result

    command_hub_app.start_escape_hold = start_escape_hold
    command_hub_app.toggle_menu = toggle_menu
    command_hub_app.toggle_holomap_transition = toggle_holomap
    command_hub_app.handle_h_action = handle_h
    command_hub_app.toggle_help_overlay = toggle_help
    command_hub_app.on_q_down = q_down
    command_hub_app.refresh_ui = refresh_ui
    # HV266_GLEEBS_ARCHIVE_IMMERSION_END

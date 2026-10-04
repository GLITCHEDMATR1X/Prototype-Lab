"""Movable snap-panel UI for HoloUtopia runtime inspectors.

The panel layer is intentionally small and reusable. It does not own gameplay
state; it only displays read-only payloads from HoloUtopia citizen/building data.

Pass 66 keeps the thin cyberpunk glass style, resizable/narrow focus card,
and adds a performance-conscious inspector content layer.  Panel text is
fitted to the current card size, repeated unchanged writes are skipped, and
secondary panels remain compact so the city view stays visible.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SnapPanelSummary:
    movable: bool = True
    snap_left: bool = True
    snap_right: bool = True
    snap_top: bool = True
    snap_bottom: bool = True
    snap_left_top: bool = True
    snap_bottom_bar: bool = True
    non_overlapping_lanes: bool = True
    close_button: bool = True
    pin_button: bool = True
    keeps_crosshair_clear: bool = True
    bottom_bar_slots: int = 3
    left_top_slots: int = 1
    compact_bottom_bar: bool = True
    single_primary_panel: bool = True
    thin_glass_style: bool = True
    resizable_panels: bool = True
    narrow_focus_card: bool = True
    right_edge_resize: bool = True
    inspector_content_upgrade: bool = True
    performance_guarded_ui: bool = True
    cached_panel_text: bool = True
    fitted_panel_text: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "movable": self.movable,
            "snap_left": self.snap_left,
            "snap_right": self.snap_right,
            "snap_top": self.snap_top,
            "snap_bottom": self.snap_bottom,
            "snap_left_top": self.snap_left_top,
            "snap_bottom_bar": self.snap_bottom_bar,
            "non_overlapping_lanes": self.non_overlapping_lanes,
            "close_button": self.close_button,
            "pin_button": self.pin_button,
            "keeps_crosshair_clear": self.keeps_crosshair_clear,
            "bottom_bar_slots": int(self.bottom_bar_slots),
            "left_top_slots": int(self.left_top_slots),
            "compact_bottom_bar": bool(self.compact_bottom_bar),
            "single_primary_panel": bool(self.single_primary_panel),
            "thin_glass_style": bool(self.thin_glass_style),
            "resizable_panels": bool(self.resizable_panels),
            "narrow_focus_card": bool(self.narrow_focus_card),
            "right_edge_resize": bool(self.right_edge_resize),
            "inspector_content_upgrade": bool(self.inspector_content_upgrade),
            "performance_guarded_ui": bool(self.performance_guarded_ui),
            "cached_panel_text": bool(self.cached_panel_text),
            "fitted_panel_text": bool(self.fitted_panel_text),
            "max_body_lines": int(MovableSnapPanelManager.MAX_PANEL_BODY_LINES),
            "max_compact_lines": int(MovableSnapPanelManager.MAX_COMPACT_LINES),
            "visual_style": "thin_glass_hud_resizable",
            "content_profile": "pass66_readable_inspectors_performance_guard",
            "snap_lane_order": ["left_top", "bottom_bar"],
        }


def build_panel_lane_contract() -> dict[str, Any]:
    """Return a JSON-safe static contract for validators and GPTOOL checks."""
    return {
        "layout_mode": "view_mode_clean_panel_shelf",
        "visual_style": "thin_glass_hud_resizable",
        "resizable_panels": True,
        "resize_policy": "right_edge_and_lower_right_handle_keeps_left_edge_anchored",
        "content_profile": "pass66_readable_inspectors_performance_guard",
        "inspector_content_upgrade": True,
        "performance_guarded_ui": True,
        "cached_panel_text": True,
        "fitted_panel_text": True,
        "max_body_lines": MovableSnapPanelManager.MAX_PANEL_BODY_LINES,
        "max_compact_lines": MovableSnapPanelManager.MAX_COMPACT_LINES,
        "expanded_focus_half_width": 0.42,
        "expanded_focus_min_half_width": 0.34,
        "expanded_focus_max_half_width": 0.54,
        "snap_lanes": ["left_top", "bottom_bar"],
        "legacy_snap_aliases": {
            "left": "left_top",
            "top": "left_top",
            "right": "bottom_bar",
            "bottom": "bottom_bar",
        },
        "non_overlapping_lanes": True,
        "bottom_bar": {
            "orientation": "horizontal",
            "slot_policy": "thin_transparent_tabs_centered_across_safe_16x9_bottom_edge",
            "max_slots": 3,
            "compact_cards": True,
            "thin_glass": True,
        },
        "left_top": {
            "orientation": "vertical",
            "slot_policy": "single_expanded_resizable_thin_glass_focus_card_at_top_left",
            "resize_handle": "lower_right_micro_grip",
            "max_slots": 1,
        },
        "drag_end_policy": "snap_to_nearest_lane_reflow_and_collapse_secondary_panels",
    }


class MovableSnapPanelManager:
    """Runtime-safe DirectGUI panel controller with drag and non-overlap snap lanes."""

    # Thin-glass proportions: the expanded card is narrower and less opaque,
    # while bottom shelf items read as slim tabs rather than bulky panels.
    PANEL_HALF_W = 0.42
    PANEL_HALF_H = 0.39
    MAX_PANEL_BODY_LINES = 13
    MAX_COMPACT_LINES = 2
    MAX_PANEL_TEXT_CHARS = 960
    MIN_PANEL_HALF_W = 0.34
    MAX_PANEL_HALF_W = 0.54
    MIN_PANEL_HALF_H = 0.31
    MAX_PANEL_HALF_H = 0.48
    PANEL_W = PANEL_HALF_W * 2.0
    PANEL_H = PANEL_HALF_H * 2.0
    COMPACT_HALF_W = 0.48
    COMPACT_PANEL_W = COMPACT_HALF_W * 2.0
    COMPACT_PANEL_H = 0.220
    SAFE_MARGIN_X = 0.050
    SAFE_MARGIN_Z = 0.048
    LANE_GAP = 0.040

    def __init__(
        self,
        app: Any,
        *,
        default_snap: str = "left_top",
        max_open_panels: int = 4,
        debug_raw_ids: bool = False,
        on_all_panels_closed: Any = None,
        layout_mode: str = "view_mode_clean_panel_shelf",
        bottom_bar_slots: int = 3,
        left_top_slots: int = 1,
    ) -> None:
        self.app = app
        self.default_snap = self._normalize_snap(default_snap or "left_top")
        self.max_open_panels = max(1, int(max_open_panels or 4))
        self.debug_raw_ids = bool(debug_raw_ids)
        self.on_all_panels_closed = on_all_panels_closed
        self.layout_mode = str(layout_mode or "view_mode_clean_panel_shelf")
        self.bottom_bar_slots = max(1, min(3, int(bottom_bar_slots or 3), self.max_open_panels))
        # Clean view mode keeps one readable primary inspector. Secondary panels
        # become bottom shelf cards instead of stacked glass walls.
        self.left_top_slots = max(1, min(1, int(left_top_slots or 1), self.max_open_panels))
        self.visual_style = "thin_glass_hud_resizable"
        self.content_profile = "pass66_readable_inspectors_performance_guard"
        self.perf_stats: dict[str, int] = {
            "panel_creates": 0,
            "panel_text_writes": 0,
            "panel_text_skips": 0,
            "layout_reflows": 0,
            "resize_updates": 0,
        }
        self.panels: dict[str, dict[str, Any]] = {}
        self.focused_panel_id: str | None = None
        self.dragging_panel_id: str | None = None
        self.resizing_panel_id: str | None = None
        self.resize_origin: dict[str, float] = {}
        self.drag_offset = (0.0, 0.0)
        self._drag_task_name = "holoutopia-snap-panel-drag"
        self._drag_task_active = False
        self._snap_sequence = 0

    def destroy(self) -> None:
        for panel_id in list(self.panels):
            self.close_panel(panel_id)
        self.dragging_panel_id = None
        self.resizing_panel_id = None
        self.resize_origin = {}
        self.focused_panel_id = None

    def close_focused(self) -> bool:
        if not self.focused_panel_id:
            return False
        return self.close_panel(self.focused_panel_id)

    def close_panel(self, panel_id: str) -> bool:
        panel_id = str(panel_id or "")
        item = self.panels.pop(panel_id, None)
        if not item:
            return False
        try:
            node = item.get("node")
            if node is not None:
                node.destroy()
        except Exception:
            try:
                node.removeNode()
            except Exception:
                pass
        if self.focused_panel_id == panel_id:
            self.focused_panel_id = next(iter(self.panels.keys()), None)
        if self.dragging_panel_id == panel_id:
            self.dragging_panel_id = None
        if self.resizing_panel_id == panel_id:
            self.resizing_panel_id = None
            self.resize_origin = {}
        self._layout_docked_panels()
        if not self.panels and callable(self.on_all_panels_closed):
            try:
                self.on_all_panels_closed()
            except Exception:
                pass
        return True

    def show_citizen_panel(self, payload: dict[str, Any]) -> str:
        """Create/update the citizen inspector panel for a selected robot civilian."""
        from holoutopia_display_names import build_citizen_panel_tabs

        queue = payload.get("queue") if isinstance(payload.get("queue"), dict) else {}
        citizen_id = str(queue.get("citizen_id") or payload.get("citizen_id") or "citizen")
        panel_id = f"citizen:{citizen_id}"
        runtime_context = payload.get("runtime_context") if isinstance(payload.get("runtime_context"), dict) else {}
        view = build_citizen_panel_tabs(
            queue,
            holoverse_root=runtime_context.get("holoverse_root"),
            debug_raw_ids=bool(payload.get("debug_raw_ids", self.debug_raw_ids)),
        )
        tabs = view.get("tabs") if isinstance(view.get("tabs"), dict) else {}
        default_tab = str(view.get("default_tab") or "overview")
        body = str(tabs.get(default_tab) or next(iter(tabs.values()), "No citizen data loaded."))
        return self.show_text_panel(
            panel_id,
            str(view.get("title") or "Citizen"),
            body,
            accent=(0.20, 0.96, 1.0, 0.96),
            tab_bodies=tabs,
            active_tab=default_tab,
            preferred_snap="left_top",
        )

    def show_building_panel(self, payload: dict[str, Any]) -> str:
        """Create/update a clean building inspector panel from highlight data."""
        from holoutopia_display_names import build_building_panel_tabs

        building = payload.get("building") if isinstance(payload.get("building"), dict) else payload
        building_id = str(building.get("id") or payload.get("building_id") or "building")
        panel_id = f"building:{building_id}"
        runtime_context = payload.get("runtime_context") if isinstance(payload.get("runtime_context"), dict) else {}
        view = build_building_panel_tabs(
            payload,
            holoverse_root=runtime_context.get("holoverse_root"),
            debug_raw_ids=bool(payload.get("debug_raw_ids", self.debug_raw_ids)),
        )
        tabs = view.get("tabs") if isinstance(view.get("tabs"), dict) else {}
        default_tab = str(view.get("default_tab") or "overview")
        body = str(tabs.get(default_tab) or next(iter(tabs.values()), "No building data loaded."))
        return self.show_text_panel(
            panel_id,
            str(view.get("title") or "Building"),
            body,
            accent=(1.0, 0.36, 0.92, 0.96),
            tab_bodies=tabs,
            active_tab=default_tab,
            preferred_snap="bottom_bar",
        )

    def _content_left(self, half_w: float | None = None) -> float:
        return -float(half_w if half_w is not None else self.PANEL_HALF_W) + 0.045

    def _content_right(self, half_w: float | None = None) -> float:
        return float(half_w if half_w is not None else self.PANEL_HALF_W) - 0.055

    def _panel_wordwrap(self, half_w: float | None = None) -> float:
        # DirectGUI wordwrap is approximate text units; this tracks the visual card width.
        return max(24.0, min(39.0, float(half_w if half_w is not None else self.PANEL_HALF_W) * 72.0))

    def _panel_half_w(self, item: dict[str, Any] | None = None) -> float:
        if isinstance(item, dict):
            try:
                return max(self.MIN_PANEL_HALF_W, min(self.MAX_PANEL_HALF_W, float(item.get("half_w", self.PANEL_HALF_W))))
            except Exception:
                pass
        return float(self.PANEL_HALF_W)

    def _panel_half_h(self, item: dict[str, Any] | None = None) -> float:
        if isinstance(item, dict):
            try:
                return max(self.MIN_PANEL_HALF_H, min(self.MAX_PANEL_HALF_H, float(item.get("half_h", self.PANEL_HALF_H))))
            except Exception:
                pass
        return float(self.PANEL_HALF_H)

    def _place_resize_handle(self, item: dict[str, Any], *, half_w: float, half_h: float, compact: bool) -> None:
        handle = item.get("resize_handle")
        if handle is None:
            return
        try:
            if compact:
                handle.hide()
            else:
                handle.show()
                handle.setPos(half_w - 0.030, 0, -half_h + 0.030)
                handle.setScale(0.016)
        except Exception:
            pass

    def show_text_panel(
        self,
        panel_id: str,
        title: str,
        body: str,
        *,
        accent=(0.20, 0.96, 1.0, 0.96),
        tab_bodies: dict[str, str] | None = None,
        active_tab: str = "overview",
        preferred_snap: str | None = None,
    ) -> str:
        from direct.gui.DirectGui import DirectButton, DirectFrame, DirectLabel
        from direct.gui import DirectGuiGlobals as DGG
        from panda3d.core import TextNode

        panel_id = str(panel_id or "panel")
        self._trim_panel_count(keep_panel_id=panel_id)
        if panel_id in self.panels:
            item = self.panels[panel_id]
            try:
                new_tabs = dict(tab_bodies or {"overview": str(body)})
                new_active = str(active_tab or next(iter(new_tabs.keys()), "overview"))
                new_body = str(new_tabs.get(new_active, body))
                cache_key = self._panel_text_cache_key(str(title), new_tabs, new_active)
                unchanged = cache_key == item.get("content_cache_key")
                if not unchanged:
                    item["title"]["text"] = str(title)
                    item["tab_bodies"] = new_tabs
                    item["active_tab"] = new_active
                    item["full_body_text"] = new_body
                    item["body"]["text"] = self._fit_panel_body_text(new_body, item=item, compact=bool(item.get("compact")))
                    item["content_cache_key"] = cache_key
                    self.perf_stats["panel_text_writes"] = int(self.perf_stats.get("panel_text_writes", 0)) + 1
                else:
                    self.perf_stats["panel_text_skips"] = int(self.perf_stats.get("panel_text_skips", 0)) + 1
                self._snap_sequence += 1
                item["snap_order"] = self._snap_sequence
                item["snap"] = self._normalize_snap(preferred_snap or item.get("snap") or self.default_snap)
                self.focus_panel(panel_id)
                self._layout_docked_panels()
                return panel_id
            except Exception:
                self.close_panel(panel_id)

        aspect2d = getattr(self.app, "aspect2d", None)
        if aspect2d is None:
            aspect2d = getattr(__import__("builtins"), "aspect2d", None)
        half_w = float(self.PANEL_HALF_W)
        half_h = float(self.PANEL_HALF_H)
        content_left = self._content_left(half_w)
        content_right = self._content_right(half_w)
        frame = DirectFrame(
            parent=aspect2d,
            frameSize=(-half_w, half_w, -half_h, half_h),
            frameColor=(0.003, 0.014, 0.024, 0.68),
            state=DGG.NORMAL,
            sortOrder=150,
        )
        frame.setTransparency(True)
        titlebar = DirectFrame(
            parent=frame,
            frameSize=(-half_w, half_w, 0.318, half_h),
            frameColor=(accent[0], accent[1], accent[2], 0.26),
            state=DGG.NORMAL,
        )
        title_label = DirectLabel(
            parent=frame,
            text=str(title),
            text_align=TextNode.ALeft,
            text_fg=(0.80, 1.0, 1.0, 1.0),
            text_scale=0.032,
            text_pos=(content_left, 0.343),
            frameColor=(0, 0, 0, 0),
        )
        fitted_body = self._fit_panel_body_text(str(body), half_w=half_w, half_h=half_h, compact=False)
        body_label = DirectLabel(
            parent=frame,
            text=fitted_body,
            text_align=TextNode.ALeft,
            text_fg=(0.92, 1.0, 1.0, 0.95),
            text_scale=0.024,
            text_wordwrap=self._panel_wordwrap(half_w),
            text_pos=(content_left, 0.116),
            frameColor=(0, 0, 0, 0),
        )
        close_button = DirectButton(parent=frame, text="X", scale=0.020, pos=(content_right, 0, 0.344), frameColor=(0.18, 0.020, 0.035, 0.42), text_fg=(1.0, 0.66, 0.64, 0.95), command=lambda: self.close_panel(panel_id))
        resize_handle = DirectButton(parent=frame, text="", scale=0.016, pos=(half_w - 0.030, 0, -half_h + 0.030), frameColor=(0.035, 0.34, 0.42, 0.30), text_fg=(0.60, 1.0, 1.0, 0.72))
        trim = self._make_glass_trim(frame, accent, half_w, half_h)
        tab_buttons = self._make_tab_buttons(frame, panel_id, tab_bodies or {"overview": str(body)}, active_tab, half_w=half_w)
        try:
            resize_handle.bind(DGG.B1PRESS, lambda _event=None, pid=panel_id: self.begin_resize(pid))
            resize_handle.bind(DGG.B1RELEASE, lambda _event=None: self.end_resize())
        except Exception:
            pass
        for widget in (titlebar, title_label):
            try:
                widget.bind(DGG.B1PRESS, lambda _event=None, pid=panel_id: self.begin_drag(pid))
                widget.bind(DGG.B1RELEASE, lambda _event=None: self.end_drag())
            except Exception:
                pass
        self._snap_sequence += 1
        snap = self._normalize_snap(preferred_snap or self.default_snap)
        self.panels[panel_id] = {
            "node": frame,
            "titlebar": titlebar,
            "title": title_label,
            "body": body_label,
            "buttons": [close_button, resize_handle, *list(tab_buttons.values())],
            "trim": trim,
            "close_button": close_button,
            "resize_handle": resize_handle,
            "half_w": half_w,
            "half_h": half_h,
            "min_half_w": self.MIN_PANEL_HALF_W,
            "max_half_w": self.MAX_PANEL_HALF_W,
            "min_half_h": self.MIN_PANEL_HALF_H,
            "max_half_h": self.MAX_PANEL_HALF_H,
            "resizable": True,
            "titlebar_color": (accent[0], accent[1], accent[2], 0.26),
            "accent": tuple(accent),
            "full_body_text": str(body),
            "content_cache_key": self._panel_text_cache_key(str(title), dict(tab_bodies or {"overview": str(body)}), str(active_tab or "overview")),
            "compact": False,
            "tab_buttons": tab_buttons,
            "pinned": False,
            "snap": snap,
            "snap_order": self._snap_sequence,
            "tab_bodies": dict(tab_bodies or {"overview": str(body)}),
            "active_tab": str(active_tab or "overview"),
        }
        self.perf_stats["panel_creates"] = int(self.perf_stats.get("panel_creates", 0)) + 1
        self.perf_stats["panel_text_writes"] = int(self.perf_stats.get("panel_text_writes", 0)) + 1
        self.snap_panel(panel_id, snap)
        self.focus_panel(panel_id)
        return panel_id

    def focus_panel(self, panel_id: str) -> None:
        panel_id = str(panel_id or "")
        if panel_id not in self.panels:
            return
        self.focused_panel_id = panel_id
        for idx, (pid, item) in enumerate(self.panels.items()):
            node = item.get("node")
            try:
                node.setBin("fixed", 142 + idx + (20 if pid == panel_id else 0))
            except Exception:
                pass

    def begin_drag(self, panel_id: str) -> None:
        if panel_id not in self.panels:
            return
        self.focus_panel(panel_id)
        self.resizing_panel_id = None
        self.resize_origin = {}
        item = self.panels[panel_id]
        node = item.get("node")
        mx, mz = self._mouse_aspect2d()
        try:
            self.drag_offset = (float(node.getX()) - mx, float(node.getZ()) - mz)
            item["snap"] = "free"
            node.setScale(0.84)
        except Exception:
            self.drag_offset = (0.0, 0.0)
        self.dragging_panel_id = panel_id
        self._ensure_drag_task()

    def end_drag(self) -> None:
        pid = self.dragging_panel_id
        self.dragging_panel_id = None
        if pid:
            self._auto_snap_if_near_edge(pid)

    def begin_resize(self, panel_id: str) -> None:
        if panel_id not in self.panels:
            return
        item = self.panels[panel_id]
        if item.get("compact") or not item.get("resizable", True):
            return
        self.focus_panel(panel_id)
        self.dragging_panel_id = None
        node = item.get("node")
        mx, mz = self._mouse_aspect2d()
        half_w = self._panel_half_w(item)
        half_h = self._panel_half_h(item)
        try:
            scale = float(node.getSx()) or 1.0
            node_x = float(node.getX())
            node_z = float(node.getZ())
            left_edge = node_x - half_w * scale
            top_edge = node_z + half_h * scale
        except Exception:
            scale = 1.0
            left_edge = -self._aspect_ratio() + self.SAFE_MARGIN_X
            top_edge = 1.0 - self.SAFE_MARGIN_Z - 0.18
        self.resize_origin = {
            "mouse_x": float(mx),
            "mouse_z": float(mz),
            "left_edge": float(left_edge),
            "top_edge": float(top_edge),
            "scale": float(scale),
            "half_w": float(half_w),
            "half_h": float(half_h),
        }
        self.resizing_panel_id = panel_id
        self._ensure_drag_task()

    def end_resize(self) -> None:
        pid = self.resizing_panel_id
        self.resizing_panel_id = None
        self.resize_origin = {}
        if pid and pid in self.panels:
            self._layout_docked_panels()

    def snap_panel(self, panel_id: str, side: str) -> None:
        item = self.panels.get(str(panel_id or ""))
        if not item:
            return
        item["snap"] = self._normalize_snap(side)
        self._snap_sequence += 1
        item["snap_order"] = self._snap_sequence
        self._layout_docked_panels()

    def _make_glass_trim(self, frame: Any, accent: tuple[float, float, float, float], half_w: float, half_h: float) -> dict[str, Any]:
        """Attach thin holographic trim to a DirectGUI frame.

        DirectGUI does not provide CSS-like borders, so these are tiny child
        frames.  They are intentionally transparent and cheap: no textures, no
        shader dependency, and no extra world geometry.
        """
        from direct.gui.DirectGui import DirectFrame
        from direct.gui import DirectGuiGlobals as DGG

        color = (float(accent[0]), float(accent[1]), float(accent[2]), 0.54)
        faint = (float(accent[0]), float(accent[1]), float(accent[2]), 0.18)
        hot = (float(accent[0]), float(accent[1]), float(accent[2]), 0.78)
        t = 0.006
        corner = 0.120
        widgets: dict[str, Any] = {}
        specs = {
            "top": (-half_w, half_w, half_h - t, half_h, color),
            "bottom": (-half_w, half_w, -half_h, -half_h + t, faint),
            "left": (-half_w, -half_w + t, -half_h, half_h, faint),
            "right": (half_w - t, half_w, -half_h, half_h, faint),
            "tl_h": (-half_w, -half_w + corner, half_h - t * 2.0, half_h, hot),
            "tl_v": (-half_w, -half_w + t * 2.0, half_h - corner, half_h, hot),
            "br_h": (half_w - corner, half_w, -half_h, -half_h + t * 2.0, color),
            "br_v": (half_w - t * 2.0, half_w, -half_h, -half_h + corner, color),
        }
        for name, (x1, x2, z1, z2, rgba) in specs.items():
            widget = DirectFrame(parent=frame, frameSize=(x1, x2, z1, z2), frameColor=rgba, state=DGG.NORMAL)
            widget.setTransparency(True)
            widgets[name] = widget
        return widgets

    def _style_glass_trim(self, item: dict[str, Any], *, half_w: float, half_h: float, compact: bool) -> None:
        trim = item.get("trim") if isinstance(item.get("trim"), dict) else {}
        accent = item.get("accent") or (0.20, 0.96, 1.0, 0.96)
        color = (float(accent[0]), float(accent[1]), float(accent[2]), 0.54 if not compact else 0.46)
        faint = (float(accent[0]), float(accent[1]), float(accent[2]), 0.18 if not compact else 0.12)
        hot = (float(accent[0]), float(accent[1]), float(accent[2]), 0.78 if not compact else 0.58)
        t = 0.006
        corner = 0.120 if not compact else 0.090
        specs = {
            "top": (-half_w, half_w, half_h - t, half_h, color),
            "bottom": (-half_w, half_w, -half_h, -half_h + t, faint),
            "left": (-half_w, -half_w + t, -half_h, half_h, faint),
            "right": (half_w - t, half_w, -half_h, half_h, faint),
            "tl_h": (-half_w, -half_w + corner, half_h - t * 2.0, half_h, hot),
            "tl_v": (-half_w, -half_w + t * 2.0, half_h - corner, half_h, hot),
            "br_h": (half_w - corner, half_w, -half_h, -half_h + t * 2.0, color),
            "br_v": (half_w - t * 2.0, half_w, -half_h, -half_h + corner, color),
        }
        for name, widget in trim.items():
            if name not in specs:
                continue
            x1, x2, z1, z2, rgba = specs[name]
            try:
                widget["frameSize"] = (x1, x2, z1, z2)
                widget["frameColor"] = rgba
            except Exception:
                pass

    def _make_tab_buttons(self, frame: Any, panel_id: str, tab_bodies: dict[str, str], active_tab: str, *, half_w: float | None = None) -> dict[str, Any]:
        from direct.gui.DirectGui import DirectButton

        labels = {"overview": "Overview", "status": "Status", "tasks": "Tasks", "social": "Social", "people": "People", "activity": "Activity"}
        buttons: dict[str, Any] = {}
        ordered_tabs = [key for key in ("overview", "status", "tasks", "social", "people", "activity") if key in tab_bodies]
        half_w = float(half_w if half_w is not None else self.PANEL_HALF_W)
        start_x = -half_w + 0.045
        available = max(0.46, half_w * 2.0 - 0.095)
        spacing = min(0.150, available / max(1, min(len(ordered_tabs), 6))) if len(ordered_tabs) >= 5 else min(0.168, available / max(1, min(len(ordered_tabs), 4)))
        for idx, tab in enumerate(ordered_tabs[:6]):
            is_active = tab == active_tab
            button = DirectButton(
                parent=frame,
                text=labels.get(tab, tab.title()),
                scale=0.021,
                pos=(start_x + idx * spacing, 0, 0.257),
                frameColor=self._tab_color(is_active),
                text_fg=(0.78, 1.0, 1.0, 0.92),
                command=lambda tab_id=tab: self.set_panel_tab(panel_id, tab_id),
            )
            buttons[tab] = button
        return buttons

    @staticmethod
    def _tab_color(active: bool) -> tuple[float, float, float, float]:
        return (0.06, 0.31, 0.38, 0.46) if active else (0.010, 0.055, 0.075, 0.26)

    def _layout_tab_buttons(self, item: dict[str, Any], *, half_w: float) -> None:
        buttons = item.get("tab_buttons") if isinstance(item.get("tab_buttons"), dict) else {}
        if not buttons:
            return
        ordered_tabs = [key for key in ("overview", "status", "tasks", "social", "people", "activity") if key in buttons]
        start_x = -half_w + 0.045
        available = max(0.46, half_w * 2.0 - 0.095)
        spacing = min(0.150, available / max(1, min(len(ordered_tabs), 6))) if len(ordered_tabs) >= 5 else min(0.168, available / max(1, min(len(ordered_tabs), 4)))
        for idx, tab in enumerate(ordered_tabs[:6]):
            try:
                buttons[tab].setPos(start_x + idx * spacing, 0, 0.257)
                buttons[tab].setScale(0.019 if half_w < 0.38 else 0.021)
            except Exception:
                pass

    def set_panel_tab(self, panel_id: str, tab_id: str) -> bool:
        item = self.panels.get(str(panel_id or ""))
        if not item:
            return False
        tabs = item.get("tab_bodies") if isinstance(item.get("tab_bodies"), dict) else {}
        tab_id = str(tab_id or "")
        if tab_id not in tabs:
            return False
        item["active_tab"] = tab_id
        try:
            item["body"]["text"] = str(tabs[tab_id])
            buttons = item.get("tab_buttons") if isinstance(item.get("tab_buttons"), dict) else {}
            for key, button in buttons.items():
                try:
                    button["frameColor"] = self._tab_color(str(key) == tab_id)
                except Exception:
                    pass
            if item.get("compact"):
                self._apply_panel_visual_mode(item, compact=True)
        except Exception:
            return False
        self.focus_panel(panel_id)
        return True

    def _trim_panel_count(self, *, keep_panel_id: str) -> None:
        if keep_panel_id in self.panels:
            return
        while len(self.panels) >= self.max_open_panels:
            victim = next((pid for pid, item in self.panels.items() if not item.get("pinned")), None)
            if victim is None:
                victim = next(iter(self.panels.keys()), None)
            if victim is None:
                return
            self.close_panel(victim)

    def _ensure_drag_task(self) -> None:
        if self._drag_task_active:
            return
        task_mgr = getattr(self.app, "taskMgr", None) or getattr(self.app, "task_mgr", None)
        if task_mgr is None:
            task_mgr = getattr(__import__("builtins"), "taskMgr", None)
        if task_mgr is not None and hasattr(task_mgr, "add"):
            try:
                task_mgr.add(self._drag_update_task, self._drag_task_name)
                self._drag_task_active = True
            except Exception:
                pass

    def _drag_update_task(self, task: Any) -> Any:
        resize_pid = self.resizing_panel_id
        if resize_pid and resize_pid in self.panels:
            self._resize_update(resize_pid)
            return getattr(task, "cont", task)
        pid = self.dragging_panel_id
        if pid and pid in self.panels:
            mx, mz = self._mouse_aspect2d()
            dx, dz = self.drag_offset
            x = mx + dx
            z = mz + dz
            aspect = self._aspect_ratio()
            item = self.panels[pid]
            scale = 0.84
            half_w = self._panel_half_w(item) * scale
            half_h = self._panel_half_h(item) * scale
            x = max(-aspect + half_w + self.SAFE_MARGIN_X, min(aspect - half_w - self.SAFE_MARGIN_X, x))
            z = max(-1.0 + half_h + self.SAFE_MARGIN_Z, min(1.0 - half_h - self.SAFE_MARGIN_Z, z))
            try:
                self.panels[pid]["node"].setPos(x, 0, z)
            except Exception:
                pass
        return getattr(task, "cont", task)

    def _resize_update(self, panel_id: str) -> None:
        item = self.panels.get(panel_id)
        if not item:
            return
        node = item.get("node")
        if node is None:
            return
        origin = self.resize_origin if isinstance(self.resize_origin, dict) else {}
        mx, mz = self._mouse_aspect2d()
        scale = max(0.50, float(origin.get("scale", 1.0) or 1.0))
        left_edge = float(origin.get("left_edge", 0.0))
        top_edge = float(origin.get("top_edge", 0.0))
        new_half_w = (float(mx) - left_edge) / scale
        new_half_h = (top_edge - float(mz)) / scale
        new_half_w = max(self.MIN_PANEL_HALF_W, min(self.MAX_PANEL_HALF_W, new_half_w))
        new_half_h = max(self.MIN_PANEL_HALF_H, min(self.MAX_PANEL_HALF_H, new_half_h))
        item["half_w"] = new_half_w
        item["half_h"] = new_half_h
        self.perf_stats["resize_updates"] = int(self.perf_stats.get("resize_updates", 0)) + 1
        self._apply_panel_visual_mode(item, compact=False)
        try:
            node.setPos(left_edge + new_half_w * scale, 0, top_edge - new_half_h * scale)
        except Exception:
            pass

    def _auto_snap_if_near_edge(self, panel_id: str) -> None:
        item = self.panels.get(panel_id)
        if not item:
            return
        node = item.get("node")
        try:
            x = float(node.getX())
            z = float(node.getZ())
        except Exception:
            self.snap_panel(panel_id, self.default_snap)
            return
        # View Mode uses two readable lanes only: top-left primary stack and bottom bar.
        # Any release in the lower half goes to the bar; otherwise prefer the left/top stack.
        if z < -0.18:
            lane = "bottom_bar"
        elif x < 0.10 or z > 0.35:
            lane = "left_top"
        else:
            lane = "bottom_bar"
        self.snap_panel(panel_id, lane)

    def _layout_docked_panels(self) -> None:
        if not self.panels:
            return
        self.perf_stats["layout_reflows"] = int(self.perf_stats.get("layout_reflows", 0)) + 1
        left_items: list[tuple[str, dict[str, Any]]] = []
        bottom_items: list[tuple[str, dict[str, Any]]] = []
        for pid, item in self.panels.items():
            snap = self._normalize_snap(str(item.get("snap") or self.default_snap))
            if snap == "free" or pid == self.dragging_panel_id:
                continue
            if snap == "left_top":
                left_items.append((pid, item))
            else:
                bottom_items.append((pid, item))
        # Newest selected panel owns the single expanded primary slot.
        left_items.sort(key=lambda pair: int(pair[1].get("snap_order", 0) or 0), reverse=True)
        bottom_items.sort(key=lambda pair: int(pair[1].get("snap_order", 0) or 0), reverse=True)
        if len(left_items) > self.left_top_slots:
            overflow = left_items[self.left_top_slots:]
            left_items = left_items[:self.left_top_slots]
            for pid, item in overflow:
                item["snap"] = "bottom_bar"
            bottom_items.extend(overflow)
            bottom_items.sort(key=lambda pair: int(pair[1].get("snap_order", 0) or 0), reverse=True)
        self._layout_left_top_lane(left_items)
        self._layout_bottom_bar_lane(bottom_items)

    def _apply_panel_visual_mode(self, item: dict[str, Any], *, compact: bool) -> None:
        """Switch a full inspector into a small bottom-shelf card, or back.

        Expanded cards can be narrowed/resized per panel.  All child controls use
        the current half-width so the right side trims inward without hiding text
        or leaving close/tab controls floating in the old oversized space.
        """
        try:
            item["compact"] = bool(compact)
            tabs = item.get("tab_buttons") if isinstance(item.get("tab_buttons"), dict) else {}
            for button in tabs.values():
                try:
                    button.hide() if compact else button.show()
                except Exception:
                    pass
            body = item.get("body")
            title = item.get("title")
            titlebar = item.get("titlebar")
            node = item.get("node")
            close = item.get("close_button")
            active = str(item.get("active_tab") or "overview")
            full_text = str((item.get("tab_bodies") or {}).get(active) or item.get("full_body_text") or "")
            if compact:
                half_w = self.COMPACT_HALF_W
                half_h = self.COMPACT_PANEL_H * 0.5
                if node is not None:
                    node["frameSize"] = (-half_w, half_w, -half_h, half_h)
                    node["frameColor"] = (0.003, 0.014, 0.024, 0.52)
                if titlebar is not None:
                    titlebar["frameSize"] = (-half_w, half_w, 0.048, half_h)
                    titlebar["frameColor"] = (0.02, 0.20, 0.24, 0.22)
                if title is not None:
                    title["text_scale"] = 0.023
                    title["text_pos"] = (-half_w + 0.038, 0.068)
                if body is not None:
                    body["text"] = self._fit_panel_body_text(full_text, half_w=half_w, half_h=half_h, compact=True)
                    body["text_scale"] = 0.019
                    body["text_pos"] = (-half_w + 0.038, -0.032)
                    body["text_wordwrap"] = max(25.0, half_w * 68.0)
                if close is not None:
                    close.setPos(half_w - 0.044, 0, 0.068)
                    close.setScale(0.015)
                self._style_glass_trim(item, half_w=half_w, half_h=half_h, compact=True)
                self._place_resize_handle(item, half_w=half_w, half_h=half_h, compact=True)
            else:
                half_w = self._panel_half_w(item)
                half_h = self._panel_half_h(item)
                content_left = self._content_left(half_w)
                content_right = self._content_right(half_w)
                if node is not None:
                    node["frameSize"] = (-half_w, half_w, -half_h, half_h)
                    node["frameColor"] = (0.003, 0.014, 0.024, 0.68)
                if titlebar is not None:
                    titlebar["frameSize"] = (-half_w, half_w, half_h - 0.072, half_h)
                    titlebar["frameColor"] = item.get("titlebar_color") or (0.20, 0.96, 1.0, 0.20)
                if title is not None:
                    title["text_scale"] = 0.031 if half_w < 0.38 else 0.033
                    title["text_pos"] = (content_left, half_h - 0.047)
                if body is not None:
                    body["text"] = self._fit_panel_body_text(full_text, half_w=half_w, half_h=half_h, compact=False)
                    body["text_scale"] = 0.024 if half_w < 0.38 else 0.025
                    body["text_pos"] = (content_left, half_h - 0.274)
                    body["text_wordwrap"] = self._panel_wordwrap(half_w)
                if close is not None:
                    close.setPos(content_right, 0, half_h - 0.046)
                    close.setScale(0.019)
                self._layout_tab_buttons(item, half_w=half_w)
                self._style_glass_trim(item, half_w=half_w, half_h=half_h, compact=False)
                self._place_resize_handle(item, half_w=half_w, half_h=half_h, compact=False)
        except Exception:
            pass


    def _panel_text_cache_key(self, title: str, tab_bodies: dict[str, str], active_tab: str) -> str:
        parts = [str(title), str(active_tab)]
        for key in sorted((tab_bodies or {}).keys()):
            parts.append(str(key))
            parts.append(str(tab_bodies.get(key) or "")[: self.MAX_PANEL_TEXT_CHARS])
        return "|".join(parts)

    def _fit_panel_body_text(
        self,
        text: str,
        *,
        item: dict[str, Any] | None = None,
        half_w: float | None = None,
        half_h: float | None = None,
        compact: bool = False,
    ) -> str:
        if compact:
            return self._compact_panel_text(text)
        if half_w is None:
            half_w = self._panel_half_w(item) if isinstance(item, dict) else self.PANEL_HALF_W
        if half_h is None:
            half_h = self._panel_half_h(item) if isinstance(item, dict) else self.PANEL_HALF_H
        # Fit content to the current card height so narrower user-resized panels
        # do not become a wall of text.  The detailed tab payload remains cached
        # in full_body_text and is re-fit whenever the card is resized.
        height_budget = max(8, int((float(half_h) * 2.0 - 0.28) / 0.044))
        line_budget = min(self.MAX_PANEL_BODY_LINES, height_budget)
        char_budget = max(34, min(58, int(float(half_w) * 122.0)))
        lines: list[str] = []
        for raw in str(text or "").splitlines():
            line = " ".join(str(raw).strip().split())
            if not line:
                if lines and lines[-1] != "":
                    lines.append("")
                continue
            while len(line) > char_budget:
                cut = line.rfind(" ", 0, char_budget)
                if cut < 18:
                    cut = char_budget
                lines.append(line[:cut].rstrip())
                line = line[cut:].strip()
                if len(lines) >= line_budget:
                    break
            if len(lines) >= line_budget:
                break
            lines.append(line)
            if len(lines) >= line_budget:
                break
        while lines and lines[-1] == "":
            lines.pop()
        source_lines = [ln for ln in str(text or "").splitlines() if str(ln).strip()]
        visible_nonempty = [ln for ln in lines if str(ln).strip()]
        if len(source_lines) > len(visible_nonempty) and lines:
            if len(lines) >= line_budget:
                lines[-1] = "… more in tabs"
            else:
                lines.append("… more in tabs")
        return "\n".join(lines[:line_budget])

    def performance_summary(self) -> dict[str, Any]:
        return {
            "content_profile": self.content_profile,
            "visual_style": self.visual_style,
            "max_body_lines": int(self.MAX_PANEL_BODY_LINES),
            "max_compact_lines": int(self.MAX_COMPACT_LINES),
            **{key: int(value) for key, value in self.perf_stats.items()},
        }

    @staticmethod
    def _compact_panel_text(text: str) -> str:
        """Return two clean lines for bottom shelf cards instead of a full inspector."""
        lines: list[str] = []
        for raw in str(text or "").splitlines():
            line = " ".join(str(raw).strip().split())
            if not line:
                continue
            if line.lower() in {"overview", "status", "tasks", "social", "people", "activity"}:
                continue
            if line not in lines:
                lines.append(line)
            if len(lines) >= 2:
                break
        if not lines:
            return "Open inspector"
        return "\n".join(lines[:2])

    def _layout_left_top_lane(self, items: list[tuple[str, dict[str, Any]]]) -> None:
        if not items:
            return
        aspect = self._aspect_ratio()
        count = max(1, min(len(items), self.left_top_slots))
        available_h = 2.0 - self.SAFE_MARGIN_Z * 2.0
        # Only one expanded card is shown, but keep the math future-safe.
        max_half_h = max(self._panel_half_h(item) for _pid, item in items[: self.left_top_slots])
        scale = min(0.92, max(0.82, (available_h - (count - 1) * self.LANE_GAP) / (count * max_half_h * 2.0)))
        # Leave a clear top HUD row for the Holo-Utopia title/status chips.
        top_edge = 1.0 - self.SAFE_MARGIN_Z - 0.18
        for idx, (_pid, item) in enumerate(items[: self.left_top_slots]):
            node = item.get("node")
            self._apply_panel_visual_mode(item, compact=False)
            half_w = self._panel_half_w(item)
            half_h = self._panel_half_h(item)
            x = -aspect + half_w * scale + self.SAFE_MARGIN_X
            z = top_edge - half_h * scale - idx * (half_h * 2.0 * scale + self.LANE_GAP)
            try:
                node.setScale(scale)
                node.setPos(x, 0, z)
            except Exception:
                pass

    def _layout_bottom_bar_lane(self, items: list[tuple[str, dict[str, Any]]]) -> None:
        if not items:
            return
        aspect = self._aspect_ratio()
        count = max(1, min(len(items), self.bottom_bar_slots))
        available_w = aspect * 2.0 - self.SAFE_MARGIN_X * 2.0
        # Bottom-bar items are compact cards, not full inspector windows.
        scale = min(0.96, max(0.78, (available_w - (count - 1) * self.LANE_GAP) / (count * self.COMPACT_PANEL_W)))
        panel_w = self.COMPACT_PANEL_W * scale
        total_w = count * panel_w + (count - 1) * self.LANE_GAP
        start_x = -total_w * 0.5 + self.COMPACT_HALF_W * scale
        z = -1.0 + (self.COMPACT_PANEL_H * 0.5) * scale + self.SAFE_MARGIN_Z
        for idx, (_pid, item) in enumerate(items[: self.bottom_bar_slots]):
            node = item.get("node")
            self._apply_panel_visual_mode(item, compact=True)
            try:
                node.setScale(scale)
                node.setPos(start_x + idx * (panel_w + self.LANE_GAP), 0, z)
            except Exception:
                pass

    @staticmethod
    def _normalize_snap(side: str) -> str:
        value = str(side or "left_top").strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "left": "left_top",
            "top": "left_top",
            "lefttop": "left_top",
            "left_top": "left_top",
            "top_left": "left_top",
            "right": "bottom_bar",
            "bottom": "bottom_bar",
            "bar": "bottom_bar",
            "bottom_bar": "bottom_bar",
            "bottombar": "bottom_bar",
            "free": "free",
        }
        return aliases.get(value, "left_top")

    def _mouse_aspect2d(self) -> tuple[float, float]:
        watcher = getattr(self.app, "mouseWatcherNode", None)
        if watcher is not None and watcher.hasMouse():
            m = watcher.getMouse()
            return float(m.getX()) * self._aspect_ratio(), float(m.getY())
        return 0.0, 0.0

    def _aspect_ratio(self) -> float:
        try:
            return float(self.app.getAspectRatio())
        except Exception:
            return 16.0 / 9.0


def build_snap_panel_summary() -> SnapPanelSummary:
    return SnapPanelSummary()

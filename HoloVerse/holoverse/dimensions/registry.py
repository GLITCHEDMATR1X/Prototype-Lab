from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from .links import STATE_SCHEMA, inspect_entry, merge_link, refresh_links

DIMENSION_MANIFEST = "dimension.json"
COMPATIBILITY = {"native", "adapted", "linked", "legacy", "disabled"}
NATIVE_LAUNCHABLE = {"native", "adapted"}

# 282.6 archive hygiene. Physical MatrixCore artifacts are already the primary
# navigation surface for their realities, so Gleebs' archive should not duplicate
# those same destinations as menu entries. The authoritative list lives in
# Dimensions/_system/archive_visibility.json so future artifact additions can be
# handled as data rather than another UI code patch.
ARCHIVE_VISIBILITY_FILE = "archive_visibility.json"
EXTERNAL_DIMENSION_INDEX_FILE = "external_dimension_index.json"
PASS2826_HOLOUTOPIA_MIGRATION = "282.6_disconnect_holoutopia"
PASS2827_RESONANCE_REMOVAL = "282.7_remove_resonance_garden"
SYSTEM_ARCHIVE_PROJECTS = ("HoloMap", "HoloTactics", "HoloCore")  # fallback if external index is missing
# 282.50: realities are read from anywhere inside Prototype Lab and MatrixCore Project (a few
# folders deep), so a project can be moved into the spotlight without breaking its link.
LAB_SCAN_DEPTH = 3
LAB_SCAN_MAX_FOLDERS = 4000
LAB_SCAN_SECONDS = 15.0
LAB_SCAN_SKIP = {
    "assets", "audio", "textures", "models", "shaders", "fonts", "music", "sfx", "ui", "data",
    "tools", "docs", "logs", "saves", "reports", "screenshots", "verification", "patch_notes",
    "reference", "runtime", "runtime_state", "libraries", "dimensions", "node_modules", "venv",
    "env", "build", "dist", "site-packages", "__pycache__", "modes", "game",
}


def _persistent_dimension_archive_path() -> Path:
    """Version-independent user-data home for linked simulation records.

    Full HoloVerse builds are replaced often during Prototype Lab passes, so a
    link archive inside a specific build folder is not durable enough.  Windows
    uses LOCALAPPDATA; other platforms use XDG_DATA_HOME / ~/.local/share.
    ``HOLOVERSE_DIMENSION_ARCHIVE`` can override the location for portable/test
    environments.
    """
    override = str(os.environ.get("HOLOVERSE_DIMENSION_ARCHIVE") or "").strip()
    if override:
        return Path(override).expanduser()
    try:
        from holoverse_userdata import user_data_root   # Pass 282.68: one shared user-data home
        return user_data_root() / "dimension_archive.json"
    except Exception:
        pass
    local = str(os.environ.get("LOCALAPPDATA") or "").strip()
    if local:
        return Path(local) / "GLITCHED MATRIX" / "HoloVerse" / "dimension_archive.json"
    xdg = str(os.environ.get("XDG_DATA_HOME") or "").strip()
    if xdg:
        return Path(xdg).expanduser() / "glitched-matrix" / "holoverse" / "dimension_archive.json"
    return Path.home() / ".local" / "share" / "glitched-matrix" / "holoverse" / "dimension_archive.json"


def _merge_archive_payloads(package_raw: dict, persistent_raw: dict) -> dict:
    """Merge a build-local archive into durable user state without losing links."""
    package_raw = package_raw if isinstance(package_raw, dict) else {}
    persistent_raw = persistent_raw if isinstance(persistent_raw, dict) else {}
    dims = {}
    for source in (package_raw.get("dimensions"), persistent_raw.get("dimensions")):
        if isinstance(source, dict):
            for key, value in source.items():
                if isinstance(value, dict):
                    merged = dict(dims.get(str(key), {}))
                    merged.update(value)
                    dims[str(key)] = merged
    links = {}
    for source in (package_raw.get("links"), persistent_raw.get("links")):
        if isinstance(source, dict):
            for key, value in source.items():
                if isinstance(value, dict):
                    merged = dict(links.get(str(key), {}))
                    merged.update(value)
                    links[str(key)] = merged
    return {
        "schema": STATE_SCHEMA,
        "last_dimension_id": str(persistent_raw.get("last_dimension_id") or package_raw.get("last_dimension_id") or ""),
        "last_link_dir": str(persistent_raw.get("last_link_dir") or package_raw.get("last_link_dir") or ""),
        "dimensions": dims,
        "links": links,
        "migrations": {
            **(package_raw.get("migrations") if isinstance(package_raw.get("migrations"), dict) else {}),
            **(persistent_raw.get("migrations") if isinstance(persistent_raw.get("migrations"), dict) else {}),
        },
    }


# Realities removed from the build.  A player's dimension_archive.json may still hold a link to
# one; it is ignored instead of showing as a lost signal in Gleebs' archive or as a planet.
RETIRED_DIMENSIONS = frozenset({"zonez", "holoutopia"})   # Pass 282.84: HoloUtopia removed (its planet look went to The Archivist)


def _record_is_retired(record) -> bool:
    keys = {_slug(getattr(record, "title", "")), _slug(getattr(record, "dimension_id", ""))}
    try:
        keys.add(_slug(Path(getattr(record, "folder", "")).name))
    except Exception:
        pass
    return any(key == retired or key.startswith(retired + "_") for key in keys for retired in RETIRED_DIMENSIONS)


def _slug(value: str) -> str:
    out = []
    for ch in str(value or "dimension").lower():
        out.append(ch if ch.isalnum() else "_")
    return "_".join(part for part in "".join(out).split("_") if part) or "dimension"


def _inside(folder: Path, parent: Path) -> bool:
    try:
        return Path(folder).resolve().is_relative_to(Path(parent).resolve())
    except Exception:
        return False


_PLAYER_BLURBS: dict | None = None


def _player_blurbs() -> dict:
    """Pass 282.67: player-facing archive text, keyed by casefolded title.  Linked projects
    describe themselves for developers (engines, adapters, contracts); players read these."""
    global _PLAYER_BLURBS
    if _PLAYER_BLURBS is None:
        path = Path(__file__).resolve().parents[2] / "assets" / "config" / "holoverse_dimension_blurbs.json"
        data = _read_json(path) if path.is_file() else {}
        table = data.get("blurbs") if isinstance(data.get("blurbs"), dict) else {}
        _PLAYER_BLURBS = {str(k).strip().casefold(): " ".join(str(v).split()) for k, v in table.items() if str(v).strip()}
    return _PLAYER_BLURBS


def player_blurb(record) -> str:
    title = str(getattr(record, "title", "") or "").strip().casefold()
    return _player_blurbs().get(title) or str(getattr(record, "description", "") or "")


def player_route_tag(record) -> str:
    """Short archive tag in player words instead of NATIVE / LINKED / LEGACY."""
    if not record.launchable:
        return "OFFLINE"
    if record.native_launchable:
        return "IN-WORLD"
    return "OWN WINDOW"


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _accent(value) -> tuple[float, float, float]:
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        try:
            vals = [float(value[i]) for i in range(3)]
            if max(vals) > 1.0:
                vals = [v / 255.0 for v in vals]
            return tuple(max(0.0, min(1.0, v)) for v in vals)
        except Exception:
            pass
    raw = str(value or "").strip().lstrip("#")
    if len(raw) == 6:
        try:
            return tuple(int(raw[i:i+2], 16) / 255.0 for i in (0, 2, 4))
        except Exception:
            pass
    return (0.20, 0.90, 1.00)


def _project_icon(*folders: Path | None) -> Path | None:
    """Resolve canonical project icon.png from the closest project folder.

    The entry folder is passed first for external links, then any stored project
    root.  This deliberately outranks manifest/saved preview paths so every
    linked reality uses the icon that currently exists beside its main.py.
    """
    seen = set()
    for raw_folder in folders:
        if raw_folder is None:
            continue
        folder = Path(raw_folder)
        try:
            key = str(folder.resolve()).casefold()
        except Exception:
            key = str(folder).casefold()
        if key in seen:
            continue
        seen.add(key)
        try:
            exact = folder / "icon.png"
            if exact.is_file():
                return exact
            if not folder.is_dir():
                continue
            for child in folder.iterdir():
                if child.is_file() and child.name.casefold() == "icon.png":
                    return child
        except Exception:
            continue
    return None


def _safe_rel_file(folder: Path, value: str, default: str = "") -> Path | None:
    raw = str(value or default).strip().replace("\\", "/")
    if not raw:
        return None
    rel = Path(raw)
    if rel.is_absolute() or ".." in rel.parts:
        return None
    candidate = folder / rel
    return candidate if candidate.exists() and candidate.is_file() else None


@dataclass(frozen=True)
class DimensionRecord:
    folder: Path
    dimension_id: str
    title: str
    version: str
    compatibility: str
    adapter: Path | None
    entry: Path | None
    preview: Path | None
    accent: tuple[float, float, float]
    symbol: str
    description: str
    issue: str = ""
    origin: str = "packaged"
    engine: str = ""
    link_id: str = ""

    @property
    def native_launchable(self) -> bool:
        return self.compatibility in NATIVE_LAUNCHABLE and self.adapter is not None and self.adapter.exists()

    @property
    def launchable(self) -> bool:
        if self.origin == "linked":
            return self.entry is not None and self.entry.exists() and (self.native_launchable or self.compatibility in {"linked", "legacy"})
        return self.native_launchable

    @property
    def signature(self) -> tuple:
        return (
            self.folder.name,
            self.dimension_id,
            self.title,
            self.version,
            self.compatibility,
            str(self.adapter or ""),
            str(self.entry or ""),
            str(self.preview or ""),
            self.accent,
            self.symbol,
            self.description,
            self.issue,
            self.origin,
            self.engine,
            self.link_id,
        )


def scan_dimension_packages(dimensions_root: Path) -> list[DimensionRecord]:
    root = Path(dimensions_root)
    if not root.exists():
        return []
    try:
        children = sorted(
            (p for p in root.iterdir() if p.is_dir() and not p.name.startswith("_")),
            key=lambda p: p.name.lower(),
        )
    except Exception:
        return []

    records: list[DimensionRecord] = []
    for folder in children:
        manifest_path = folder / DIMENSION_MANIFEST
        manifest = _read_json(manifest_path) if manifest_path.exists() else {}
        title = str(manifest.get("title") or folder.name.replace("_", " ")).strip() or folder.name
        dimension_id = _slug(str(manifest.get("id") or folder.name))
        version = str(manifest.get("version") or "").strip()
        compatibility = str(manifest.get("compatibility") or "legacy").strip().lower()
        if compatibility not in COMPATIBILITY:
            compatibility = "legacy"

        adapter_rel = str(manifest.get("adapter") or "adapter/holoverse_adapter.py").strip()
        entry_rel = str(manifest.get("entry") or "source/main.py").strip()
        adapter = _safe_rel_file(folder, adapter_rel)
        entry = _safe_rel_file(folder, entry_rel)

        issue = ""
        if not manifest:
            compatibility, issue = "legacy", "manifest missing"
        elif compatibility in NATIVE_LAUNCHABLE and adapter is None:
            compatibility, issue = "legacy", "adapter missing"
        elif entry_rel and entry is None:
            issue = "source entry missing"
        elif compatibility == "disabled":
            issue = str(manifest.get("disabled_reason") or "disabled by manifest")

        presentation = manifest.get("presentation") if isinstance(manifest.get("presentation"), dict) else {}
        # Old portal presentation fields remain readable for backwards compatibility,
        # but the Hub does not build or traverse dimension portals.
        legacy_portal = manifest.get("portal") if isinstance(manifest.get("portal"), dict) else {}
        # icon.png is the canonical archive identity when the package supplies
        # one; configured preview art remains a fallback for older dimensions.
        preview = _project_icon(folder)
        if preview is None:
            preview = _safe_rel_file(folder, str(presentation.get("preview") or manifest.get("preview") or "preview.png"))
        description = str(
            presentation.get("description")
            or manifest.get("description")
            or "Gleebs has indexed this reality, but no archival description was supplied yet."
        ).strip()
        description = " ".join(description.split())[:360]

        records.append(
            DimensionRecord(
                folder=folder,
                dimension_id=dimension_id,
                title=title,
                version=version,
                compatibility=compatibility,
                adapter=adapter,
                entry=entry,
                preview=preview,
                accent=_accent(presentation.get("accent") or legacy_portal.get("accent") or manifest.get("accent")),
                symbol=str(presentation.get("symbol") or legacy_portal.get("symbol") or manifest.get("symbol") or "O")[:3],
                description=description,
                issue=issue,
            )
        )
    return records


class DimensionRegistry:
    """Gleebs-owned drop-in dimension catalog. No Hub portal geometry is created."""

    RESCAN_SECONDS = 2.0
    PAGE_SIZE = 8

    def __init__(self, host, dimensions_root: Path):
        self.host = host
        self.dimensions_root = Path(dimensions_root)
        self.dimensions_root.mkdir(parents=True, exist_ok=True)
        # Pass 282.68: the old in-build mirror (<game>/saves) is retired so a shipped build never
        # carries the developer's links or visits; both names now point at the user-data file.
        self.state_path = _persistent_dimension_archive_path()
        self.package_state_path = self.state_path
        self.state = self._load_state()
        self.records: list[DimensionRecord] = []
        self._signature = ()
        self._last_scan = 0.0
        self._task_name = f"holoverse-dimension-registry-{id(self)}"
        self.menu_root = None
        self.menu_page = 0
        self.menu_mode = "gleebs"
        self.selected_id = ""
        self._talk_callback = None
        self._mouse_restore = None
        self._host_menu_restore = None
        self._host_hud_restore = None
        self._host_view_restore = None
        self._ui = {}
        self.observatory = None
        # Player-facing archive stays clean once realities are indexed.
        # Shift+F8 toggles these developer-only link controls from the host.
        self.link_tools_visible = False
        self._artifact_hidden_keys = self._load_artifact_hidden_keys()
        self._bot_hosted = self._load_bot_hosted()
        self.hosted_records: list[DimensionRecord] = []
        self._external_archive_specs = self._load_external_archive_specs()
        self._lab_folders_cache: list[Path] = []
        self._lab_folders_at = -1e9
        self._apply_pass2826_link_migrations()
        self._apply_pass2827_resonance_removal()

    def _load_artifact_hidden_keys(self) -> set[str]:
        """Load archive identities already represented by physical hub artifacts."""
        path = self.dimensions_root / "_system" / ARCHIVE_VISIBILITY_FILE
        payload = _read_json(path) if path.is_file() else {}
        values = payload.get("artifact_backed") if isinstance(payload, dict) else []
        keys: set[str] = set()
        if isinstance(values, list):
            for value in values:
                key = _slug(str(value or ""))
                if key:
                    keys.add(key)
        return keys

    def _load_bot_hosted(self) -> dict[str, str]:
        """Pass 282.56: archive realities a region guide hosts (slug -> guide).
        They leave Gleebs' archive and its orbs; the guide's dialogue enters them."""
        path = self.dimensions_root / "_system" / ARCHIVE_VISIBILITY_FILE
        payload = _read_json(path) if path.is_file() else {}
        values = payload.get("bot_hosted") if isinstance(payload, dict) else {}
        out: dict[str, str] = {}
        if isinstance(values, dict):
            for title, bot in values.items():
                key = _slug(str(title or ""))
                if key:
                    out[key] = str(bot or "")
        return out

    def _record_is_bot_hosted(self, record: DimensionRecord) -> bool:
        if not self._bot_hosted:
            return False
        return bool({_slug(record.dimension_id), _slug(record.title), _slug(record.folder.name)} & set(self._bot_hosted))

    def hosted_record(self, title: str):
        """The launchable record a guide hosts under ``title`` (rescanning if needed)."""
        key = _slug(str(title or ""))
        if not key or key not in self._bot_hosted:
            return None
        self.rescan()
        for record in list(self.hosted_records):
            if key in {_slug(record.title), _slug(record.dimension_id), _slug(record.folder.name)} and record.launchable:
                return record
        if not self.hosted_records:
            self.rescan(force=True)
            for record in list(self.hosted_records):
                if key in {_slug(record.title), _slug(record.dimension_id), _slug(record.folder.name)} and record.launchable:
                    return record
        return None

    def _load_external_archive_specs(self) -> list[dict]:
        """Load data-driven first-class external realities for Gleebs' archive.

        These are *not* copied into ``Dimensions`` and they do not become physical
        artifacts.  The index only teaches HoloVerse how to recognize a known
        sibling project by responder metadata / conservative folder aliases.
        """
        path = self.dimensions_root / "_system" / EXTERNAL_DIMENSION_INDEX_FILE
        payload = _read_json(path) if path.is_file() else {}
        projects = payload.get("projects") if isinstance(payload, dict) else None
        specs = [dict(item) for item in projects if isinstance(item, dict)] if isinstance(projects, list) else []
        if specs:
            return specs
        # Preserve the accepted 282.7 behavior if the data file is absent/damaged.
        return [
            {"key": name, "title": name, "folder_aliases": [name, name.replace("Holo", "Holo ", 1)],
             "symbol": {"HoloMap": "MAP", "HoloTactics": "TAC", "HoloCore": "COR"}.get(name, "SYS"),
             "accent": "70E0B8", "legacy_native_adapter": True}
            for name in SYSTEM_ARCHIVE_PROJECTS
        ]

    def _external_spec_for_project(self, root: Path, data: dict | None = None) -> dict:
        """Return first-class archive metadata for a known external project."""
        data = data if isinstance(data, dict) else {}
        responder = _read_json(root / "holoverse" / "holoverse_dimension.json")
        package = _read_json(root / DIMENSION_MANIFEST)
        titles = {_slug(data.get("title")), _slug(responder.get("title"))}
        ids = {_slug(package.get("id"))}
        folder_key = _slug(root.name)
        specs = getattr(self, "_external_archive_specs", None)
        if not isinstance(specs, list):
            try:
                specs = self._load_external_archive_specs()
            except Exception:
                specs = []
        for spec in specs:
            responder_titles = {_slug(str(x)) for x in spec.get("responder_titles", []) if str(x).strip()}
            manifest_ids = {_slug(str(x)) for x in spec.get("manifest_ids", []) if str(x).strip()}
            aliases = {_slug(str(x)) for x in spec.get("folder_aliases", []) if str(x).strip()}
            prefixes = [_slug(str(x)) for x in spec.get("folder_prefixes", []) if str(x).strip()]
            if responder_titles and titles & responder_titles:
                return spec
            if manifest_ids and ids & manifest_ids:
                return spec
            if folder_key in aliases or any(folder_key.startswith(prefix) for prefix in prefixes):
                if not bool(spec.get("requires_responder", False)) or str(responder.get("protocol") or "").strip() == "holoverse_responder_v1":
                    return spec
        return {}

    def _persistent_link_matches_spec(self, spec: dict) -> bool:
        """True when durable link state already owns this catalog reality."""
        target = _slug(str(spec.get("key") or spec.get("title") or ""))
        if not target:
            return False
        links = self.state.get("links") if isinstance(self.state.get("links"), dict) else {}
        aliases = {_slug(str(x)) for x in spec.get("folder_aliases", []) if str(x).strip()}
        prefixes = [_slug(str(x)) for x in spec.get("folder_prefixes", []) if str(x).strip()]
        for data in links.values():
            if not isinstance(data, dict):
                continue
            if _slug(str(data.get("catalog_key") or "")) == target:
                return True
            raw_root = str(data.get("project_root") or data.get("entry_path") or "").strip()
            if not raw_root:
                continue
            root = Path(raw_root).expanduser()
            if root.suffix.lower() == ".py":
                root = root.parent
            # A generic pre-282.40 manual link may not carry catalog_key yet.
            # Preserve it across later source moves by recognizing its stored title.
            stored_title = _slug(str(data.get("title") or ""))
            if stored_title in aliases or any(stored_title.startswith(prefix) for prefix in prefixes):
                return True
            matched = self._external_spec_for_project(root, data)
            matched_key = _slug(str(matched.get("key") or matched.get("title") or ""))
            if matched_key == target:
                return True
        return False

    def _catalog_spec(self, key: str) -> dict:
        target = _slug(str(key or ""))
        for spec in self._external_archive_specs:
            spec_key = _slug(str(spec.get("key") or spec.get("title") or ""))
            if spec_key == target:
                return spec
        return {}

    def _external_project_candidates(self, spec: dict, search_parents: list[Path]) -> list[Path]:
        """Resolve a catalogued external project without recursively scanning drives."""
        aliases = [str(x).strip() for x in spec.get("folder_aliases", []) if str(x).strip()]
        prefixes = [_slug(str(x)) for x in spec.get("folder_prefixes", []) if str(x).strip()]
        responder_titles = {_slug(str(x)) for x in spec.get("responder_titles", []) if str(x).strip()}
        manifest_ids = {_slug(str(x)) for x in spec.get("manifest_ids", []) if str(x).strip()}
        requires_responder = bool(spec.get("requires_responder", False))
        out: list[Path] = []
        seen: set[str] = set()

        def add(folder: Path):
            try:
                key = str(folder.resolve()).casefold()
            except Exception:
                key = str(folder).casefold()
            if key not in seen and (folder / "main.py").is_file():
                seen.add(key)
                out.append(folder)

        # Exact historical names remain the fastest/least surprising path.
        for parent in search_parents:
            for alias in aliases:
                folder = parent / alias
                if not folder.is_dir():
                    continue
                responder = _read_json(folder / "holoverse" / "holoverse_dimension.json")
                responder_ok = str(responder.get("protocol") or "").strip() == "holoverse_responder_v1"
                if not requires_responder or responder_ok:
                    add(folder)

        # Pass-numbered Prototype Lab folders change names often.  Scan only direct
        # siblings and match a responder title / manifest id, never arbitrary source.
        for parent in search_parents:
            if not parent.is_dir():
                continue
            try:
                children = [p for p in parent.iterdir() if p.is_dir()]
            except Exception:
                continue
            for folder in children[:512]:
                if not (folder / "main.py").is_file():
                    continue
                responder = _read_json(folder / "holoverse" / "holoverse_dimension.json")
                responder_ok = str(responder.get("protocol") or "").strip() == "holoverse_responder_v1"
                responder_match = responder_ok and (not responder_titles or _slug(responder.get("title")) in responder_titles)
                package = _read_json(folder / DIMENSION_MANIFEST)
                id_match = bool(manifest_ids and _slug(package.get("id")) in manifest_ids)
                prefix_match = bool(prefixes and any(_slug(folder.name).startswith(prefix) for prefix in prefixes))
                if requires_responder:
                    if responder_match and (not manifest_ids or id_match or prefix_match):
                        add(folder)
                elif responder_match or id_match or prefix_match:
                    add(folder)

        # 282.50: projects moved deeper inside Prototype Lab / MatrixCore Project (Utopia
        # Vision/Glyphbound, a nested HoloTactics/HoloTactics...) are matched the same way.
        bundles = [Path(b) for b in search_parents] if bool(spec.get("bundle_only", False)) else []
        for folder in self._lab_responder_folders():
            if bundles and not any(_inside(folder, bundle) for bundle in bundles):
                continue
            responder = _read_json(folder / "holoverse" / "holoverse_dimension.json")
            responder_match = not responder_titles or _slug(responder.get("title")) in responder_titles
            package = _read_json(folder / DIMENSION_MANIFEST)
            id_match = bool(manifest_ids and (_slug(package.get("id")) in manifest_ids or _slug(responder.get("id")) in manifest_ids))
            prefix_match = bool(prefixes and any(_slug(folder.name).startswith(prefix) for prefix in prefixes))
            alias_match = _slug(folder.name) in {_slug(a) for a in aliases}
            if responder_titles and responder_match:
                add(folder)
            elif not responder_titles and (id_match or prefix_match or alias_match):
                add(folder)
        return out

    def _record_has_physical_artifact(self, record: DimensionRecord) -> bool:
        if not self._artifact_hidden_keys:
            return False
        candidates = {
            _slug(record.dimension_id),
            _slug(record.title),
            _slug(record.folder.name),
        }
        return bool(candidates & self._artifact_hidden_keys)

    @staticmethod
    def _looks_like_holoutopia_link(link_key: str, data: dict) -> bool:
        """Identify only the abandoned HoloUtopia link requested for 282.6 removal."""
        fields = [
            link_key,
            data.get("dimension_id"),
            data.get("title"),
            data.get("project_root"),
            data.get("entry_path"),
        ]
        normalized = " | ".join(str(v or "") for v in fields).lower().replace("_", " ").replace("-", " ")
        compact = "".join(ch for ch in normalized if ch.isalnum())
        return "holoutopia" in compact

    def _apply_pass2826_link_migrations(self) -> None:
        """Disconnect HoloUtopia once while preserving the ability to relink later."""
        migrations = self.state.setdefault("migrations", {})
        if not isinstance(migrations, dict):
            migrations = self.state["migrations"] = {}
        if bool(migrations.get(PASS2826_HOLOUTOPIA_MIGRATION)):
            return
        links = self.state.get("links") if isinstance(self.state.get("links"), dict) else {}
        removed = []
        for key, data in list(links.items()):
            if not isinstance(data, dict):
                continue
            if self._looks_like_holoutopia_link(str(key), data):
                removed.append((str(key), str(data.get("title") or "HoloUtopia")))
                links.pop(key, None)
        last_id = str(self.state.get("last_dimension_id") or "")
        if any(key == last_id for key, _title in removed):
            self.state["last_dimension_id"] = ""
        last_link_dir = str(self.state.get("last_link_dir") or "")
        compact_last_dir = "".join(ch for ch in last_link_dir.lower() if ch.isalnum())
        if removed and "holoutopia" in compact_last_dir:
            self.state["last_link_dir"] = ""
        migrations[PASS2826_HOLOUTOPIA_MIGRATION] = {
            "applied": int(time.time()),
            "removed": [key for key, _title in removed],
        }
        for key, title in removed:
            print(f"dimension_link_disconnected_migration id={key} title={title}")

    @staticmethod
    def _looks_like_resonance_record(key: str, data: dict) -> bool:
        fields = [key, data.get("dimension_id"), data.get("title"), data.get("last_title"), data.get("project_root"), data.get("entry_path")]
        compact = "".join(ch for ch in " | ".join(str(v or "") for v in fields).lower() if ch.isalnum())
        return "resonancegarden" in compact

    def _apply_pass2827_resonance_removal(self) -> None:
        """Remove the unfinished Resonance Garden from durable archive state once."""
        migrations = self.state.setdefault("migrations", {})
        if not isinstance(migrations, dict):
            migrations = self.state["migrations"] = {}
        if bool(migrations.get(PASS2827_RESONANCE_REMOVAL)):
            return
        links = self.state.get("links") if isinstance(self.state.get("links"), dict) else {}
        removed_links = []
        for key, data in list(links.items()):
            if isinstance(data, dict) and self._looks_like_resonance_record(str(key), data):
                removed_links.append(str(key))
                links.pop(key, None)
        dims = self.state.get("dimensions") if isinstance(self.state.get("dimensions"), dict) else {}
        removed_dims = []
        for key, data in list(dims.items()):
            if isinstance(data, dict) and self._looks_like_resonance_record(str(key), data):
                removed_dims.append(str(key))
                dims.pop(key, None)
        last_id = str(self.state.get("last_dimension_id") or "")
        if last_id in set(removed_links + removed_dims):
            self.state["last_dimension_id"] = ""
        migrations[PASS2827_RESONANCE_REMOVAL] = {
            "applied": int(time.time()),
            "removed_links": removed_links,
            "removed_dimensions": removed_dims,
        }
        if removed_links or removed_dims:
            print(f"dimension_resonance_removed links={len(removed_links)} states={len(removed_dims)}")


    def _matrixcore_bundle_roots(self) -> list[Path]:
        """Return bounded MatrixCore bundle roots near this HoloVerse install.

        This deliberately mirrors the accepted external-reality search radius: direct
        parents/siblings only, never a recursive drive scan.  It also supports the
        two common layouts where HoloVerse is either beside MatrixCore Project or
        nested inside it.
        """
        project_root = self.dimensions_root.parent
        search_parents = [project_root, project_root.parent]
        grandparent = project_root.parent.parent
        if grandparent not in search_parents:
            search_parents.append(grandparent)
        roots: list[Path] = []
        seen: set[str] = set()

        def add(folder: Path):
            if not folder.is_dir():
                return
            try:
                key = str(folder.resolve()).casefold()
            except Exception:
                key = str(folder).casefold()
            if key in seen:
                return
            seen.add(key)
            roots.append(folder)

        for parent in search_parents:
            if _slug(parent.name) in {"matrixcore", "matrixcore_project"}:
                add(parent)
            if not parent.is_dir():
                continue
            try:
                children = list(parent.iterdir())[:256]
            except Exception:
                continue
            for child in children:
                if child.is_dir() and _slug(child.name) in {"matrixcore", "matrixcore_project"}:
                    add(child)
        return roots

    def _lab_roots(self) -> list[Path]:
        """Prototype Lab (HoloVerse's parent folder) and every MatrixCore bundle root."""
        roots: list[Path] = []
        seen: set[str] = set()
        for folder in [self.dimensions_root.parent.parent] + self._matrixcore_bundle_roots():
            try:
                key = str(folder.resolve()).casefold()
            except Exception:
                key = str(folder).casefold()
            if key not in seen and folder.is_dir():
                seen.add(key)
                roots.append(folder)
        return roots

    def _lab_responder_folders(self, force: bool = False) -> list[Path]:
        """Every project folder under the lab roots that answers HoloVerse (main.py plus a
        holoverse_responder_v1 manifest), up to LAB_SCAN_DEPTH folders deep.

        Bounded and cached: asset/tool/log folders, dot/underscore folders and HoloVerse itself
        are never entered, a responder project's own subfolders are not searched further, and
        the scan runs at most every LAB_SCAN_SECONDS.
        """
        now = time.monotonic()
        if not force and now - self._lab_folders_at < LAB_SCAN_SECONDS:
            return list(self._lab_folders_cache)
        try:
            holoverse_key = str(self.dimensions_root.parent.resolve()).casefold()
        except Exception:
            holoverse_key = str(self.dimensions_root.parent).casefold()
        found: list[Path] = []
        seen: set[str] = set()
        visited = 0
        queue = [(root, 0) for root in self._lab_roots()]
        while queue and visited < LAB_SCAN_MAX_FOLDERS:
            folder, depth = queue.pop(0)
            try:
                key = str(folder.resolve()).casefold()
            except Exception:
                key = str(folder).casefold()
            if key in seen or key == holoverse_key:
                continue
            seen.add(key)
            visited += 1
            if depth > 0 and (folder / "main.py").is_file():
                responder = _read_json(folder / "holoverse" / "holoverse_dimension.json")
                if str(responder.get("protocol") or "").strip() == "holoverse_responder_v1":
                    found.append(folder)      # keep going: a reality can hold another (Utopia Conflict / Vector Arena)
            if depth >= LAB_SCAN_DEPTH:
                continue
            try:
                children = sorted((p for p in folder.iterdir() if p.is_dir()), key=lambda p: p.name.casefold())[:256]
            except Exception:
                continue
            for child in children:
                name = child.name
                if name.startswith((".", "_")) or name.casefold() in LAB_SCAN_SKIP:
                    continue
                queue.append((child, depth + 1))
        self._lab_folders_cache = found
        self._lab_folders_at = now
        return list(found)

    def _adopt_matrixcore_projects(self) -> bool:
        """Auto-link direct MatrixCore prototypes using the established legacy link law.

        A direct child only qualifies when it has a real ``main.py``.  Responder
        projects retain responder identity/native metadata; generic projects receive
        the same stable ``.holoverse_link.json`` sidecar the existing LINK SIMULATION
        workflow already uses.  No recursive source scan and no copied game content.
        """
        links = self.state.setdefault("links", {})
        if not isinstance(links, dict):
            links = self.state["links"] = {}
        current_root = self.dimensions_root.parent
        try:
            current_key = str(current_root.resolve()).casefold()
        except Exception:
            current_key = str(current_root).casefold()

        def known(info: dict, folder: Path, entry: Path) -> bool:
            dimension_id = str(info.get("dimension_id") or "").strip()
            responder_key = str(info.get("responder_key") or "").strip()
            fingerprint = str(info.get("fingerprint") or "").strip()
            try:
                folder_key = str(folder.resolve()).casefold()
                entry_key = str(entry.resolve()).casefold()
            except Exception:
                folder_key = str(folder).casefold()
                entry_key = str(entry).casefold()
            for data in links.values():
                if not isinstance(data, dict):
                    continue
                if dimension_id and str(data.get("dimension_id") or "") == dimension_id:
                    return True
                if responder_key and str(data.get("responder_key") or "") == responder_key:
                    return True
                if fingerprint and str(data.get("fingerprint") or "") == fingerprint:
                    return True
                raw_root = str(data.get("project_root") or "").strip()
                raw_entry = str(data.get("entry_path") or "").strip()
                try:
                    if raw_root and str(Path(raw_root).expanduser().resolve()).casefold() == folder_key:
                        return True
                except Exception:
                    pass
                try:
                    if raw_entry and str(Path(raw_entry).expanduser().resolve()).casefold() == entry_key:
                        return True
                except Exception:
                    pass
            return False

        changed = False
        adopted = []
        previous_last_link_dir = str(self.state.get("last_link_dir") or "")
        for bundle in self._matrixcore_bundle_roots():
            try:
                children = sorted((p for p in bundle.iterdir() if p.is_dir()), key=lambda p: p.name.casefold())[:512]
            except Exception:
                continue
            for folder in children:
                if folder.name.startswith((".", "_")):
                    continue
                try:
                    if str(folder.resolve()).casefold() == current_key:
                        continue
                except Exception:
                    pass
                entry = folder / "main.py"
                if not entry.is_file():
                    continue
                try:
                    info = inspect_entry(entry, create_identity=False)
                    if known(info, folder, entry):
                        continue
                    link, _updated = merge_link(self.state, entry)
                    link["matrixcore_auto_adopted"] = True
                    link["matrixcore_bundle_root"] = str(bundle)
                    adopted.append(str(link.get("title") or folder.name))
                    changed = True
                except Exception as exc:
                    print(f"dimension_matrixcore_auto_link_failed folder={folder} err={exc}")
        # Automatic discovery must not steal the user's manual file-picker location.
        self.state["last_link_dir"] = previous_last_link_dir
        if adopted:
            print(f"dimension_matrixcore_auto_linked count={len(adopted)} titles={adopted}")
        return changed

    def _system_archive_records(self) -> list[DimensionRecord]:
        """Discover catalogued archive-only sibling projects without copying them.

        282.15 keeps the accepted HoloMap/HoloTactics/HoloCore behavior and adds
        Mirror's Limbo through a data-driven external index.  Detection is read-only:
        no UUID sidecar is written until the user explicitly uses LINK SIMULATION.
        """
        project_root = self.dimensions_root.parent
        search_parents = [project_root, project_root.parent]
        grandparent = project_root.parent.parent
        if grandparent not in search_parents:
            search_parents.append(grandparent)
        bundle_roots = self._matrixcore_bundle_roots()
        for bundle in bundle_roots:
            if bundle not in search_parents:
                search_parents.append(bundle)
        records: list[DimensionRecord] = []
        for spec in self._external_archive_specs:
            key = str(spec.get("key") or spec.get("title") or "External Reality").strip()
            # 282.18: HoloCore is intentionally an external MatrixCore Project
            # reality.  When a catalog record opts into bundle_only, stale root-
            # level copies beside/in HoloVerse are ignored so HoloVerse cannot
            # accidentally regress to the old combined layout.
            candidate_parents = list(bundle_roots) if bool(spec.get("bundle_only", False)) else list(search_parents)
            candidates = self._external_project_candidates(spec, candidate_parents)
            entry = next((folder / "main.py" for folder in candidates if (folder / "main.py").is_file()), None)
            if entry is None:
                if bool(spec.get("show_when_missing", False)) and not self._persistent_link_matches_spec(spec):
                    fallback_id = str(spec.get("catalog_dimension_id") or f"system_{_slug(key)}")
                    aliases = [str(x).strip() for x in spec.get("folder_aliases", []) if str(x).strip()]
                    placeholder_folder = project_root.parent / (aliases[0] if aliases else key)
                    records.append(DimensionRecord(
                        folder=placeholder_folder,
                        dimension_id=fallback_id,
                        title=str(spec.get("title") or key),
                        version=str(spec.get("version") or ""),
                        compatibility="linked",
                        adapter=None,
                        entry=None,
                        preview=None,
                        accent=_accent(spec.get("accent") or "70E0B8"),
                        symbol=str(spec.get("symbol") or "SYS")[:3],
                        description=" ".join(str(spec.get("description") or f"{key} external reality.").split())[:360],
                        issue=str(spec.get("missing_issue") or f"{key} source not linked — select its main.py to restore access"),
                        origin="linked",
                        engine=str(spec.get("engine") or "python"),
                        link_id=f"catalog:{_slug(key)}",
                    ))
                continue
            try:
                info = inspect_entry(entry, create_identity=False)
            except Exception as exc:
                print(f"dimension_system_discovery_failed project={key} err={exc}")
                continue
            adapter_raw = str(info.get("native_adapter") or "").strip()
            adapter = Path(adapter_raw) if adapter_raw else None
            if adapter is not None and not adapter.is_file():
                adapter = None
            # Older core siblings predate responder manifests but already ship the
            # established root-level native adapter.  Catalog data opts into this.
            legacy_native = entry.parent / "holoverse_native_adapter.py"
            if adapter is None and bool(spec.get("legacy_native_adapter", False)) and legacy_native.is_file():
                adapter = legacy_native
            compatibility = str(info.get("compatibility") or "linked").strip().lower()
            if adapter is not None and compatibility in {"linked", "legacy"}:
                compatibility = "native"
            if compatibility not in COMPATIBILITY:
                compatibility = "linked"
            preview = _project_icon(entry.parent)
            if preview is None:
                preview_raw = str(info.get("preview") or "").strip()
                preview = Path(preview_raw) if preview_raw else None
                if preview is not None and not preview.is_file():
                    preview = None
            package = _read_json(entry.parent / DIMENSION_MANIFEST)
            fallback_id = str(spec.get("catalog_dimension_id") or f"system_{_slug(key)}")
            dimension_id = str(info.get("dimension_id") or fallback_id)
            # Catalog identity owns the player-facing title/description even when a
            # pass-numbered raw folder has no responder metadata of its own.
            title = str(spec.get("title") or info.get("title") or key)
            description = str(spec.get("description") or info.get("description") or f"{title} reality discovered beside HoloVerse.")
            records.append(DimensionRecord(
                folder=entry.parent,
                dimension_id=dimension_id,
                title=title,
                version=str(package.get("version") or spec.get("version") or ""),
                compatibility=compatibility,
                adapter=adapter,
                entry=Path(str(info.get("entry_path") or entry)),
                preview=preview,
                accent=_accent(spec.get("accent") or "70E0B8"),
                symbol=str(spec.get("symbol") or "SYS")[:3],
                description=" ".join(description.split())[:360],
                issue="",
                origin="linked",
                engine=str(info.get("engine") or spec.get("engine") or "python"),
                link_id=f"catalog:{_slug(key)}",
            ))
        records.extend(self._lab_responder_records(records))
        return records

    def _lab_responder_records(self, catalog_records: list[DimensionRecord]) -> list[DimensionRecord]:
        """282.50: any responder project inside Prototype Lab / MatrixCore Project that no catalog
        entry claims is listed from its own responder metadata (read-only, nothing is written)."""
        taken: set[str] = set()
        for record in catalog_records:
            try:
                taken.add(str(record.folder.resolve()).casefold())
            except Exception:
                taken.add(str(record.folder).casefold())
        out: list[DimensionRecord] = []
        for folder in self._lab_responder_folders():
            try:
                key = str(folder.resolve()).casefold()
            except Exception:
                key = str(folder).casefold()
            if key in taken:
                continue
            responder = _read_json(folder / "holoverse" / "holoverse_dimension.json")
            if self._external_spec_for_project(folder, {"title": responder.get("title")}):
                continue            # a catalog entry owns it; it decides where it is shown
            entry = folder / "main.py"
            try:
                info = inspect_entry(entry, create_identity=False)
            except Exception as exc:
                print(f"dimension_lab_discovery_failed folder={folder} err={exc}")
                continue
            adapter_raw = str(info.get("native_adapter") or "").strip()
            adapter = Path(adapter_raw) if adapter_raw else None
            if adapter is not None and not adapter.is_file():
                adapter = None
            compatibility = str(info.get("compatibility") or "linked").strip().lower()
            if compatibility not in COMPATIBILITY:
                compatibility = "linked"
            package = _read_json(folder / DIMENSION_MANIFEST)
            title = str(info.get("title") or responder.get("title") or folder.name)
            presentation = package.get("presentation") if isinstance(package.get("presentation"), dict) else {}
            symbol = str(responder.get("symbol") or presentation.get("symbol") or package.get("symbol") or "LNK")
            accent = responder.get("accent") or presentation.get("accent") or package.get("accent") or "70E0B8"
            dimension_id = str(info.get("dimension_id") or f"lab_{_slug(title)}")
            out.append(DimensionRecord(
                folder=folder,
                dimension_id=dimension_id,
                title=title,
                version=str(package.get("version") or responder.get("version") or ""),
                compatibility=compatibility,
                adapter=adapter,
                entry=Path(str(info.get("entry_path") or entry)),
                preview=_project_icon(folder),
                accent=_accent(accent),
                symbol=symbol[:3],
                description=" ".join(str(info.get("description") or responder.get("description") or f"{title} reality inside Prototype Lab.").split())[:360],
                issue="",
                origin="linked",
                engine=str(info.get("engine") or responder.get("engine") or "python"),
                link_id=f"lab:{_slug(title)}",
            ))
            taken.add(key)
        return out

    @property
    def menu_open(self):
        return self.menu_root is not None

    def start(self):
        self.rescan(force=True)
        # Always materialize the merged archive in durable storage so an old
        # build-local archive is migrated on the first launch of Pass 280+.
        self._save_state()
        self.host.taskMgr.add(self._task, self._task_name, sort=38)
        try:
            from .observatory import DimensionObservatory
            asset_root = self.dimensions_root.parent / "assets" / "dimension_spheres"
            self.observatory = DimensionObservatory(self.host, self, asset_root).start()
        except Exception as exc:
            self.observatory = None
            print(f"dimension_observatory_init_failed err={exc}")
        print(f"dimension_registry_storage persistent={self.state_path} mirror={self.package_state_path}")
        print(f"dimension_registry_ready mode=gleebs_archive_v7 count={len(self.records)}")
        return self

    def destroy(self):
        self.close_menu()
        if self.observatory is not None:
            try:
                self.observatory.destroy()
            except Exception:
                pass
            self.observatory = None
        try:
            self.host.taskMgr.remove(self._task_name)
        except Exception:
            pass

    def _task(self, task):
        # Pass 282.48: registry discovery is event-driven.  The former task ran a
        # full package/link/system scan every RESCAN_SECONDS (2s) during gameplay.
        # That performs filesystem I/O on Panda's foreground task chain and caused
        # visible periodic frame hitches.  Startup already scans once, the archive
        # menu scans on open, and link/relink/recovery routes force their own scan.
        # Keep this task as a zero-I/O compatibility heartbeat so older lifecycle
        # code can still remove it by name without special cases.
        return task.cont

    def _load_state(self) -> dict:
        package_raw = _read_json(self.package_state_path) if self.package_state_path.exists() else {}
        persistent_raw = _read_json(self.state_path) if self.state_path.exists() else {}
        return _merge_archive_payloads(package_raw, persistent_raw)

    def _save_state(self):
        payload = json.dumps(self.state, indent=2, sort_keys=True) + "\n"
        errors = []
        targets = [(self.state_path, True)]
        if self.package_state_path != self.state_path:
            targets.append((self.package_state_path, False))
        for target, required in targets:
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                tmp = target.with_suffix(target.suffix + ".tmp")
                tmp.write_text(payload, encoding="utf-8")
                os.replace(tmp, target)
            except Exception as exc:
                errors.append((target, exc, required))
        required_failures = [item for item in errors if item[2]]
        if required_failures:
            target, exc, _ = required_failures[0]
            print(f"dimension_archive_state_write_failed path={target} err={exc}")
        elif errors:
            # Build-folder mirrors may be read-only in installed/Steam layouts;
            # durable user storage remains authoritative.
            target, exc, _ = errors[0]
            print(f"dimension_archive_mirror_write_skipped path={target} err={exc}")

    def _state_for(self, dimension_id: str, create=False) -> dict:
        dims = self.state.setdefault("dimensions", {})
        if dimension_id in dims:
            return dims[dimension_id]
        if not create:
            return {}
        dims[dimension_id] = {"seen": False, "visits": 0, "last_visit": 0}
        return dims[dimension_id]

    def _mark_seen(self, record: DimensionRecord):
        info = self._state_for(record.dimension_id, create=True)
        if not bool(info.get("seen", False)):
            info["seen"] = True
            info["first_seen"] = int(time.time())
            self._save_state()

    def _mark_visit(self, record: DimensionRecord):
        info = self._state_for(record.dimension_id, create=True)
        info["seen"] = True
        info["visits"] = max(0, int(info.get("visits", 0))) + 1
        info["last_visit"] = int(time.time())
        info["last_title"] = record.title
        self.state["last_dimension_id"] = record.dimension_id
        self._save_state()

    # Pass 282.75: Gleebs' archive list only opens a reality once the player has entered its
    # planet in HoloSpace.  The unlock lives in the player's dimension_archive.json in the
    # per-user save folder (holoverse_userdata), so it survives updates and reinstalls.
    def is_unlocked(self, record: DimensionRecord) -> bool:
        info = self._state_for(record.dimension_id, create=False)
        return bool(info.get("planet_unlocked", False)) if info else False

    def unlock_from_planet(self, record: DimensionRecord) -> bool:
        info = self._state_for(record.dimension_id, create=True)
        info["seen"] = True
        if bool(info.get("planet_unlocked", False)):
            return False
        info["planet_unlocked"] = True
        info["planet_unlocked_at"] = int(time.time())
        info["last_title"] = record.title
        self._save_state()
        print(f"dimension_archive_unlocked id={record.dimension_id} title={record.title!r} source=holospace_planet")
        return True

    def _archive_status(self, record: DimensionRecord) -> str:
        if not self.is_unlocked(record):
            return "LOCKED // FIND ITS PLANET IN HOLOSPACE"
        info = self._state_for(record.dimension_id, create=False)
        visits = max(0, int(info.get("visits", 0))) if info else 0
        if visits:
            return f"VISITED x{visits}"
        if info.get("seen"):
            return "INDEXED"
        return "NEW SIGNAL"

    def _linked_records(self) -> list[DimensionRecord]:
        records = []
        links = self.state.get("links") if isinstance(self.state.get("links"), dict) else {}
        for link_key, data in links.items():
            if not isinstance(data, dict):
                continue
            root = Path(str(data.get("project_root") or data.get("entry_path") or ".")).expanduser()
            if root.suffix.lower() == ".py":
                root = root.parent
            entry_raw = str(data.get("entry_path") or "").strip()
            entry = Path(entry_raw).expanduser() if entry_raw else None
            if entry is not None and not entry.is_file():
                entry = None
            adapter_raw = str(data.get("native_adapter") or "").strip()
            adapter = Path(adapter_raw).expanduser() if adapter_raw else None
            if adapter is not None and not adapter.is_file():
                adapter = None
            # The active main.py folder is the authority for linked visuals.
            # This repairs persistent links that still contain an older, valid
            # preview path and also follows moved/relinked projects correctly.
            preview = _project_icon(entry.parent if entry is not None else None, root)
            if preview is None:
                preview_raw = str(data.get("preview") or "").strip()
                preview = Path(preview_raw).expanduser() if preview_raw else None
                if preview is not None and not preview.is_file():
                    preview = None
            compatibility = str(data.get("compatibility") or "linked").strip().lower()
            if compatibility not in COMPATIBILITY:
                compatibility = "linked"
            missing = bool(data.get("missing", False)) or entry is None
            catalog = self._external_spec_for_project(entry.parent if entry is not None else root, data)
            if not catalog and str(data.get("catalog_key") or "").strip():
                catalog = self._catalog_spec(str(data.get("catalog_key") or ""))
            issue = "linked source missing — use LINK SIMULATION to relink main.py" if missing else ""
            title = str(catalog.get("title") or data.get("title") or root.name or "Linked Simulation").strip()
            engine = str(data.get("engine") or catalog.get("engine") or "python").strip()
            description = str(catalog.get("description") or data.get("description") or "External simulation linked to Gleebs' archive.").strip()
            package = _read_json((entry.parent if entry is not None else root) / DIMENSION_MANIFEST)
            records.append(
                DimensionRecord(
                    folder=root,
                    dimension_id=str(data.get("dimension_id") or link_key),
                    title=title,
                    version=str(package.get("version") or catalog.get("version") or ""),
                    compatibility=compatibility,
                    adapter=adapter,
                    entry=entry,
                    preview=preview,
                    accent=_accent(catalog.get("accent") or "70E0B8"),
                    symbol=str(catalog.get("symbol") or "LNK")[:3],
                    description=" ".join(description.split())[:360],
                    issue=issue,
                    origin="linked",
                    engine=engine,
                    link_id=str(link_key),
                )
            )
        return records

    def _repoint_missing_links(self, linked: list[DimensionRecord], system: list[DimensionRecord]) -> bool:
        """282.50: a saved link whose source is missing is pointed at the same reality (same
        dimension id) found in Prototype Lab / MatrixCore Project."""
        found = {r.dimension_id: r for r in system if r.entry is not None and r.entry.is_file()}
        links = self.state.get("links") if isinstance(self.state.get("links"), dict) else {}
        changed = False
        for record in linked:
            if record.entry is not None:
                continue
            target = found.get(record.dimension_id)
            data = links.get(record.link_id)
            if target is None or not isinstance(data, dict):
                continue
            try:
                fresh = inspect_entry(target.entry, create_identity=False)
            except Exception:
                continue
            if not str(fresh.get("dimension_id") or "").strip():
                fresh["dimension_id"] = record.dimension_id
            roots = [str(target.folder.parent), str(target.folder.parent.parent)]
            roots += [str(r) for r in data.get("search_roots") or [] if str(r) not in roots]
            links[record.link_id] = {**data, **fresh, "missing": False, "search_roots": roots[:8],
                                     "recovered_at": int(time.time()), "recovered_by": "lab_scan"}
            print(f"dimension_link_repointed title={record.title} entry={target.entry}")
            changed = True
        return changed

    def rescan(self, force=False):
        now = time.monotonic()
        if not force and now - self._last_scan < self.RESCAN_SECONDS:
            return False
        self._last_scan = now
        adopted_changed = self._adopt_matrixcore_projects()
        links_changed = refresh_links(self.state)
        if adopted_changed or links_changed:
            self._save_state()
        packaged = scan_dimension_packages(self.dimensions_root)
        linked = self._linked_records()
        system = self._system_archive_records()
        if self._repoint_missing_links(linked, system):
            self._save_state()
            linked = self._linked_records()
        # Preserve packaged/persistent-link authority on collisions. System sibling
        # discovery is a read-only convenience layer and never duplicates a real link.
        packaged_ids = {r.dimension_id for r in packaged}
        all_records = packaged + [r for r in linked if r.dimension_id not in packaged_ids]
        occupied_ids = {r.dimension_id for r in all_records}
        occupied_folders = {str(r.folder.resolve()).lower() for r in all_records if r.folder.exists()}
        for record in system:
            folder_key = str(record.folder.resolve()).lower() if record.folder.exists() else str(record.folder).lower()
            if record.dimension_id in occupied_ids or folder_key in occupied_folders:
                continue
            all_records.append(record)
            occupied_ids.add(record.dimension_id)
            occupied_folders.add(folder_key)
        # Pass 282.77: retired realities never come back, even from an old saved link.
        all_records = [r for r in all_records if not _record_is_retired(r)]
        artifact_hidden = [r for r in all_records if self._record_has_physical_artifact(r)]
        self.hosted_records = [r for r in all_records if self._record_is_bot_hosted(r) and not self._record_has_physical_artifact(r)]
        records = [r for r in all_records if not self._record_has_physical_artifact(r) and not self._record_is_bot_hosted(r)]
        records.sort(key=lambda r: (0 if r.origin == "linked" else 1, r.title.lower()))
        signature = tuple(r.signature for r in records)
        if not force and signature == self._signature:
            return False
        self.records, self._signature = records, signature
        if self.observatory is not None:
            try:
                self.observatory.sync_records(records)
            except Exception as exc:
                print(f"dimension_observatory_sync_failed err={exc}")
        if self.menu_open and self.menu_mode == "archive":
            self._rebuild_archive_page()
        print(
            "dimension_registry_scan mode=gleebs_archive_v7 count=%d linked=%d packaged=%d hidden_artifact=%d bot_hosted=%d [%s]"
            % (len(records), len(linked) + len(system), len(packaged), len(artifact_hidden), len(self.hosted_records), ", ".join(f"{r.title}:{r.compatibility}" for r in records) or "none")
        )
        return True

    def open_gleebs_menu(self, talk_callback=None):
        if getattr(self.host, "active_native_mode", None) is not None:
            return False
        if self.menu_open:
            return True
        self.rescan(force=True)
        self._talk_callback = talk_callback
        self.menu_page = 0
        self._capture_host_view()
        self._enter_modal()
        self._show_pointer()
        self._build_root()
        self._rebuild_gleebs_page()
        return True

    def close_menu(self):
        root, self.menu_root = self.menu_root, None
        self._ui.clear()
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass
        self._restore_pointer()
        self._exit_modal()
        self._restore_host_view()
        self._arm_mouse_look_resume()
        self._talk_callback = None

    def _capture_host_view(self):
        """Snapshot the gameplay view before Gleebs takes absolute mouse input."""
        try:
            camera = getattr(self.host, "camera", None)
            render = getattr(self.host, "render", None)
            hpr = camera.getHpr(render) if camera is not None and render is not None else camera.getHpr()
            self._host_view_restore = {
                "yaw": float(getattr(self.host, "player_yaw", hpr.x)),
                "pitch": float(getattr(self.host, "player_pitch", hpr.y)),
                "hpr": (float(hpr.x), float(hpr.y), float(hpr.z)),
            }
        except Exception:
            self._host_view_restore = None

    def _restore_host_view(self):
        """Restore the exact pre-menu look direction before FPS mouse sampling resumes."""
        saved, self._host_view_restore = self._host_view_restore, None
        if not isinstance(saved, dict):
            return
        try:
            yaw = float(saved.get("yaw", getattr(self.host, "player_yaw", 0.0)))
            pitch = float(saved.get("pitch", getattr(self.host, "player_pitch", 0.0)))
            self.host.player_yaw = yaw
            self.host.player_pitch = pitch
            hpr = saved.get("hpr", (yaw, pitch, 0.0))
            self.host.camera.setHpr(float(hpr[0]), float(hpr[1]), float(hpr[2]))
        except Exception:
            pass

    def _arm_mouse_look_resume(self):
        """Center the cursor and suppress stale absolute-pointer deltas briefly."""
        try:
            import time
            self.host.mouse_look_resume_at = max(
                float(getattr(self.host, "mouse_look_resume_at", 0.0)),
                time.monotonic() + 0.12,
            )
        except Exception:
            pass
        recenter = getattr(self.host, "recenter_mouse", None)
        if callable(recenter):
            try:
                recenter(force=True)
            except Exception:
                pass

    def _enter_modal(self):
        if self._host_menu_restore is not None:
            return
        self._host_menu_restore = bool(getattr(self.host, "menu_open", False))
        self._host_hud_restore = bool(getattr(self.host, "hud_visible", True))
        try:
            self.host.menu_open = True
            self.host.hud_visible = False
            host_menu = getattr(self.host, "menu_root", None)
            if host_menu is not None:
                host_menu.hide()
            hint = getattr(self.host, "center_hint", None)
            if hint is not None:
                hint["text"] = ""
            refresh = getattr(self.host, "refresh_ui", None)
            if callable(refresh):
                refresh()
            safety = getattr(self.host, "safety_exit_root", None)
            if safety is not None:
                safety.hide()
        except Exception:
            pass

    def _exit_modal(self):
        if self._host_menu_restore is None:
            return
        previous = bool(self._host_menu_restore)
        hud_previous = bool(self._host_hud_restore) if self._host_hud_restore is not None else True
        self._host_menu_restore = None
        self._host_hud_restore = None
        try:
            self.host.menu_open = previous
            self.host.hud_visible = hud_previous
            host_menu = getattr(self.host, "menu_root", None)
            if host_menu is not None:
                if previous:
                    host_menu.show()
                else:
                    host_menu.hide()
            refresh = getattr(self.host, "refresh_ui", None)
            if callable(refresh):
                refresh()
        except Exception:
            pass

    def _show_pointer(self):
        try:
            from panda3d.core import WindowProperties

            props = self.host.win.getProperties()
            self._mouse_restore = (props.getCursorHidden(), props.getMouseMode())
            new = WindowProperties()
            new.setCursorHidden(False)
            new.setMouseMode(WindowProperties.M_absolute)
            self.host.win.requestProperties(new)
        except Exception:
            self._mouse_restore = None

    def _restore_pointer(self):
        if self._mouse_restore is None:
            return
        try:
            from panda3d.core import WindowProperties

            hidden, mode = self._mouse_restore
            new = WindowProperties()
            new.setCursorHidden(bool(hidden))
            new.setMouseMode(mode)
            self.host.win.requestProperties(new)
        except Exception:
            pass
        self._mouse_restore = None

    def _build_root(self):
        from direct.gui.DirectFrame import DirectFrame

        parent = getattr(self.host, "aspect2d", None) or getattr(self.host, "render2d", None)
        self.menu_root = DirectFrame(
            parent=parent,
            frameColor=(0.010, 0.016, 0.025, 0.965),
            frameSize=(-1.30, 1.30, -0.79, 0.79),
            pos=(0, 0, 0),
            relief=1,
        )
        self._ui = {"root": self.menu_root}

    def _clear_children(self):
        for key, child in list(self._ui.items()):
            if key == "root":
                continue
            try:
                child.destroy()
            except Exception:
                try:
                    child.removeNode()
                except Exception:
                    pass
        self._ui = {"root": self.menu_root}

    def _label(self, key, text, x, z, scale=0.05, color=(0.86, 0.94, 1, 1), parent=None, align=None, wrap=None):
        from direct.gui.DirectLabel import DirectLabel
        from panda3d.core import Filename, TextNode

        node = DirectLabel(
            parent=parent or self.menu_root,
            text=text,
            text_scale=scale,
            text_fg=color,
            text_align=align if align is not None else TextNode.ACenter,
            text_wordwrap=wrap,
            frameColor=(0, 0, 0, 0),
            pos=(x, 0, z),
        )
        self._ui[key] = node
        return node

    def _button(self, key, text, x, z, command=None, enabled=True, width=0.50, height=0.062, scale=0.036):
        from direct.gui.DirectButton import DirectButton
        from direct.gui import DirectGuiGlobals as DGG

        node = DirectButton(
            parent=self.menu_root,
            text=text,
            text_scale=scale,
            text_fg=(0.92, 0.97, 1, 1) if enabled else (0.44, 0.49, 0.55, 1),
            frameColor=(
                (0.025, 0.055, 0.075, 0.96),
                (0.05, 0.115, 0.15, 1),
                (0.07, 0.16, 0.20, 1),
                (0.025, 0.055, 0.075, 0.96),
            ),
            frameSize=(-width, width, -height, height),
            pos=(x, 0, z),
            relief=1,
            command=command if enabled else None,
            state=DGG.NORMAL if enabled else DGG.DISABLED,
        )
        self._ui[key] = node
        return node

    def _link_tools_enabled(self) -> bool:
        # With an empty archive the first link must remain reachable. Once one or
        # more realities exist, link management is intentionally developer-only.
        return bool(self.link_tools_visible or not self.records)

    def toggle_link_tools(self) -> bool:
        self.link_tools_visible = not bool(self.link_tools_visible)
        if self.menu_open:
            if self.menu_mode == "archive":
                self._rebuild_archive_page()
            else:
                self._rebuild_gleebs_page()
        state = "VISIBLE" if self.link_tools_visible else "HIDDEN"
        print(f"dimension_link_tools {state.lower()}")
        try:
            self.host.center_hint["text"] = f"DIMENSION LINK TOOLS // {state}"
        except Exception:
            pass
        return self.link_tools_visible

    def _rebuild_gleebs_page(self):
        self._clear_children()
        self.menu_mode = "gleebs"
        last_id = str(self.state.get("last_dimension_id") or "")
        last = next((r for r in self.records if r.dimension_id == last_id), None)
        self._label("title", "GLEEBS // CONTINUUM INTERFACE", 0, 0.61, 0.058, (0.72, 0.95, 0.44, 1))
        self._label("line1", "Archive-only realities are indexed here. Artifact-backed destinations stay physical around MatrixCore.", 0, 0.43, 0.036)
        if last is not None:
            self._label("last", f"LAST CROSSING // {last.title.upper()}", 0, 0.33, 0.030, (0.48, 0.72, 0.78, 1))
        else:
            self._label("last", "NO DIMENSION CROSSING RECORDED YET", 0, 0.33, 0.030, (0.48, 0.60, 0.68, 1))
        self._button("talk", "TALK TO GLEEBS", 0, 0.17, self._talk, width=0.70, height=0.068, scale=0.041)
        self._button("archive", f"DIMENSION ARCHIVE  //  {len(self.records)} INDEXED", 0, 0.01, self._open_archive, width=0.70, height=0.068, scale=0.041)
        # Pass 282.59: Gleebs opens HoloSpace, open deep space with Dyson Prime far beyond reach.
        self._button("holospace", "HOLOSPACE  //  FLY DEEP SPACE", 0, -0.15, self._holospace, width=0.70, height=0.068, scale=0.041)
        if self._link_tools_enabled():
            self._button("link", "LINK SIMULATION", 0, -0.31, self._link_simulation_dialog, width=0.70, height=0.068, scale=0.041)
            close_z, hint_z = -0.47, -0.58
        else:
            close_z, hint_z = -0.31, -0.45
        self._button("close", "CLOSE", 0, close_z, self.close_menu, width=0.70, height=0.060, scale=0.036)
        self._label("hint", "Artifact-backed realities stay physical. Linked realities are managed with the hidden developer toggle.", 0, hint_z, 0.027, (0.47, 0.58, 0.66, 1))
        self._label("esc", "ESC  CLOSE", 0, -0.68, 0.026, (0.40, 0.50, 0.58, 1))

    def _talk(self):
        callback = self._talk_callback
        self.close_menu()
        if callable(callback):
            try:
                callback()
            except Exception as exc:
                print(f"gleebs_talk_callback_failed err={exc}")

    def _holospace(self):
        """Pass 282.59: close the menu first (region travel refuses while a menu
        is open), then warp into HoloSpace through the normal Region 8 route."""
        self.close_menu()
        host = self.host
        fn = getattr(host, "activate_holospace_region_from_mode", None)
        try:
            if callable(fn):
                fn(None, source="gleebs_menu")
            else:
                fallback = getattr(host, "enter_holospace_region_from_matrixcore", None)
                if callable(fallback):
                    fallback(source="gleebs_menu")
        except Exception as exc:
            print(f"gleebs_holospace_failed err={exc.__class__.__name__}:{exc}")

    def _open_archive(self):
        self.menu_page = 0
        preferred = str(self.state.get("last_dimension_id") or "")
        self.selected_id = preferred if any(r.dimension_id == preferred for r in self.records) else ""
        self._rebuild_archive_page()

    def _current_subset(self) -> list[DimensionRecord]:
        start = self.menu_page * self.PAGE_SIZE
        return self.records[start : start + self.PAGE_SIZE]

    def _selected_record(self, subset=None) -> DimensionRecord | None:
        pool = subset if subset is not None else self.records
        selected = next((r for r in pool if r.dimension_id == self.selected_id), None)
        if selected is None and pool:
            selected = pool[0]
            self.selected_id = selected.dimension_id
        return selected

    def _rebuild_archive_page(self):
        self._clear_children()
        self.menu_mode = "archive"
        pages = max(1, (len(self.records) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        self.menu_page = max(0, min(self.menu_page, pages - 1))
        subset = self._current_subset()
        selected = self._selected_record(subset)
        if selected is not None:
            self._mark_seen(selected)

        self._label("title", "GLEEBS // DIMENSION ARCHIVE", 0, 0.68, 0.055, (0.72, 0.95, 0.44, 1))
        unlocked = sum(1 for r in self.records if self.is_unlocked(r))
        self._label("page", f"REALITY INDEX  {self.menu_page + 1}/{pages}   //   UNLOCKED {unlocked}/{len(self.records)}", -0.73, 0.57, 0.026, (0.48, 0.72, 0.78, 1))
        self._label("inspect", "INSPECT SIGNAL", 0.63, 0.57, 0.026, (0.48, 0.72, 0.78, 1))

        if not subset:
            self._label("empty", "No archive-only realities are currently indexed.", -0.63, 0.18, 0.038, (0.70, 0.72, 0.76, 1))
        for i, record in enumerate(subset):
            # Eight compact entries fit cleanly between the header and controls,
            # keeping the current seven-reality MatrixCore set on one page.
            z = 0.43 - i * 0.126
            state = self._archive_status(record)
            text = f"{record.symbol:<3} {record.title}  [{player_route_tag(record)}]\n{state}"
            button = self._button(
                f"dim{i}",
                text,
                -0.72,
                z,
                lambda r=record: self._select_dimension(r),
                True,
                width=0.49,
                height=0.052,
                scale=0.027,
            )
            if selected is not None and record.dimension_id == selected.dimension_id:
                try:
                    button["frameColor"] = (
                        (0.06, 0.16, 0.18, 1),
                        (0.08, 0.20, 0.22, 1),
                        (0.10, 0.24, 0.26, 1),
                        (0.06, 0.16, 0.18, 1),
                    )
                except Exception:
                    pass

        self._build_detail_panel(selected)

        if self.menu_page > 0:
            self._button("prev", "< PREVIOUS", -0.96, -0.57, self._prev, width=0.25, height=0.050, scale=0.029)
        if self.menu_page + 1 < pages:
            self._button("next", "NEXT >", -0.47, -0.57, self._next, width=0.25, height=0.050, scale=0.029)
        self._button("back", "BACK TO GLEEBS", -0.72, -0.69, self._rebuild_gleebs_page, width=0.49, height=0.050, scale=0.030)
        if self._link_tools_enabled():
            self._button("link_archive", "LINK SIMULATION", 0.63, -0.64, self._link_simulation_dialog, width=0.43, height=0.045, scale=0.028)
        self._label("escape", "ESC  CLOSE", 0.63, -0.735, 0.022, (0.40, 0.50, 0.58, 1))

    def _build_detail_panel(self, record: DimensionRecord | None):
        from direct.gui.DirectFrame import DirectFrame
        from panda3d.core import Filename, TextNode

        panel = DirectFrame(
            parent=self.menu_root,
            frameColor=(0.018, 0.035, 0.050, 0.96),
            frameSize=(-0.57, 0.57, -0.54, 0.54),
            pos=(0.63, 0, -0.03),
            relief=1,
        )
        self._ui["detail_panel"] = panel
        if record is None:
            self._label("detail_empty", "NO SIGNAL SELECTED", 0, 0.05, 0.036, (0.58, 0.62, 0.68, 1), parent=panel)
            return

        accent = (*record.accent, 1.0)
        self._label("detail_title", record.title.upper(), 0, 0.46, 0.041, accent, parent=panel)
        version = f" v{record.version}" if record.version else ""
        self._label(
            "detail_meta",
            f"{record.compatibility.upper()}{version}  //  {record.engine.upper() if record.engine else record.origin.upper()}  //  {self._archive_status(record)}",
            0,
            0.395,
            0.024,
            (0.64, 0.76, 0.82, 1),
            parent=panel,
        )

        # Resolve icon.png again at draw time instead of trusting a scan-time or
        # persisted preview path.  This makes adding/replacing icon.png visible
        # immediately when the Archive is reopened, without relinking the game.
        preview_path = _project_icon(
            record.entry.parent if record.entry is not None else None,
            record.folder,
        ) or record.preview
        if preview_path is not None:
            try:
                from direct.gui.OnscreenImage import OnscreenImage

                # External links originate as OS-native pathlib paths.  Panda3D
                # requires its own Filename convention, especially on Windows
                # where drive letters/backslashes must be translated first.
                preview_filename = Filename.fromOsSpecific(str(preview_path))
                texture = self.host.loader.loadTexture(preview_filename, okMissing=True)
                if texture is None:
                    raise IOError(f"texture loader returned no texture for {preview_path}")
                # Keep source aspect ratio inside the existing preview frame.
                tex_w = max(1, int(texture.getXSize()))
                tex_h = max(1, int(texture.getYSize()))
                ratio = float(tex_w) / float(tex_h)
                max_x, max_z = 0.48, 0.27
                if ratio >= max_x / max_z:
                    scale_x, scale_z = max_x, max_x / max(0.001, ratio)
                else:
                    scale_z, scale_x = max_z, max_z * ratio
                image = OnscreenImage(image=texture, parent=panel, pos=(0, 0, 0.075), scale=(scale_x, 1, scale_z))
                image.setTransparency(True)
                self._ui["detail_preview"] = image
                print(f"dimension_preview_loaded id={record.dimension_id} file={preview_path.name} source={preview_path}")
            except Exception as exc:
                print(f"dimension_preview_failed id={record.dimension_id} path={preview_path} err={exc}")
                self._preview_fallback(panel, record)
        else:
            self._preview_fallback(panel, record)

        self._label(
            "detail_description",
            player_blurb(record),
            -0.49,
            -0.235,
            0.024,
            (0.80, 0.87, 0.91, 1),
            parent=panel,
            align=TextNode.ALeft,
            wrap=39.0,
        )

        # Pass 282.67: status in player words; the technical reason still goes to the log.
        unlocked = self.is_unlocked(record)
        if not unlocked:
            self._label("detail_issue", "LOCKED // ENTER THIS REALITY'S PLANET IN HOLOSPACE TO UNLOCK IT", 0, -0.34, 0.021, (0.86, 0.62, 0.95, 1), parent=panel)
        elif record.issue:
            print(f"dimension_archive_issue title={record.title} issue={record.issue}")
            self._label("detail_issue", "SIGNAL LOST // THIS REALITY'S FILES WERE MOVED OR ARE MISSING", 0, -0.34, 0.021, (1.0, 0.58, 0.30, 1), parent=panel)
        elif record.launchable and record.native_launchable:
            self._label("detail_issue", "READY // OPENS RIGHT HERE IN HOLOVERSE", 0, -0.34, 0.023, (0.55, 0.92, 0.72, 1), parent=panel)
        elif record.launchable:
            self._label("detail_issue", "READY // OPENS IN ITS OWN WINDOW, CLOSE IT TO RETURN", 0, -0.34, 0.023, (0.70, 0.86, 0.52, 1), parent=panel)
        else:
            self._label("detail_issue", "SIGNAL UNSTABLE // NOT ENTERABLE YET", 0, -0.34, 0.023, (0.80, 0.66, 0.32, 1), parent=panel)

        enterable = bool(record.launchable and unlocked)
        enter = self._button(
            "detail_enter",
            "RUN SIMULATION" if enterable else ("LOCKED" if not unlocked else "SIMULATION UNAVAILABLE"),
            0.63,
            -0.49,
            lambda r=record: self._choose_dimension(r),
            enterable,
            width=0.43,
            height=0.054,
            scale=0.031,
        )
        try:
            enter["text_fg"] = (0.94, 1.0, 0.92, 1) if enterable else (0.44, 0.49, 0.55, 1)
        except Exception:
            pass

    def _preview_fallback(self, panel, record: DimensionRecord):
        from direct.gui.DirectFrame import DirectFrame

        accent = record.accent
        box = DirectFrame(
            parent=panel,
            frameColor=(accent[0] * 0.12, accent[1] * 0.12, accent[2] * 0.12, 1),
            frameSize=(-0.48, 0.48, -0.27, 0.27),
            pos=(0, 0, 0.075),
            relief=1,
        )
        self._ui["detail_preview_fallback"] = box
        self._label("preview_symbol", record.symbol or "O", 0, 0.06, 0.11, (*record.accent, 0.92), parent=box)
        self._label("preview_text", "VISUAL MEMORY NOT RECORDED", 0, -0.11, 0.023, (0.55, 0.64, 0.70, 1), parent=box)

    def _register_link_entry(self, entry: Path, expected_catalog_key: str = "") -> tuple[dict, bool]:
        """Register main.py, optionally enforcing a first-class catalog identity.

        Catalog validation happens before ``merge_link`` so the wrong selected project
        cannot receive a HoloVerse identity sidecar as a side effect.
        """
        entry = Path(entry).expanduser().resolve()
        info = inspect_entry(entry, create_identity=False)
        expected = _slug(expected_catalog_key) if expected_catalog_key else ""
        if expected:
            spec = self._catalog_spec(expected)
            if not spec:
                raise ValueError(f"unknown catalog reality: {expected_catalog_key}")
            matched = self._external_spec_for_project(entry.parent, info)
            matched_key = _slug(str(matched.get("key") or matched.get("title") or ""))
            if matched_key != expected:
                expected_title = str(spec.get("title") or expected_catalog_key)
                raise ValueError(f"selected main.py is not recognized as {expected_title}")
        link, updated = merge_link(self.state, entry)
        if expected:
            link["catalog_key"] = expected
        return link, updated

    def link_catalog_record(self, record: DimensionRecord) -> bool:
        link_id = str(getattr(record, "link_id", "") or "")
        if not link_id.startswith("catalog:"):
            return False
        return bool(self._link_simulation_dialog(expected_catalog_key=link_id.split(":", 1)[1]))

    def _link_simulation_dialog(self, expected_catalog_key: str = ""):
        """Open a native file picker and register a project main.py in-place."""
        root = None
        selected = ""
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            try:
                root.attributes("-topmost", True)
            except Exception:
                pass
            initial = str(self.state.get("last_link_dir") or "").strip()
            if not initial or not Path(initial).exists():
                initial = str(Path.home())
            expected_spec = self._catalog_spec(expected_catalog_key) if expected_catalog_key else {}
            expected_title = str(expected_spec.get("title") or "").strip()
            picker_title = (
                f"HoloVerse — Link {expected_title} (select main.py)"
                if expected_title else "HoloVerse — Link Simulation (select main.py)"
            )
            selected = filedialog.askopenfilename(
                parent=root,
                title=picker_title,
                initialdir=initial,
                filetypes=(("Simulation entry", "main.py"), ("Python files", "*.py"), ("All files", "*.*")),
            )
        except Exception as exc:
            print(f"dimension_link_picker_failed err={exc}")
            try:
                self.host.center_hint["text"] = "LINK SIMULATION // FILE PICKER UNAVAILABLE"
            except Exception:
                pass
            return False
        finally:
            if root is not None:
                try:
                    root.destroy()
                except Exception:
                    pass
        if not selected:
            return False
        entry = Path(selected).expanduser()
        if entry.name.lower() != "main.py" or not entry.is_file():
            try:
                self.host.center_hint["text"] = "LINK SIMULATION // SELECT THE PROJECT'S main.py"
            except Exception:
                pass
            return False
        try:
            link, updated = self._register_link_entry(entry, expected_catalog_key=expected_catalog_key)
            self._save_state()
            self.rescan(force=True)
            dimension_id = str(link.get("dimension_id") or "")
            self.selected_id = dimension_id
            self.menu_page = max(0, next((i // self.PAGE_SIZE for i, r in enumerate(self.records) if r.dimension_id == dimension_id), 0))
            if self.menu_open:
                self._rebuild_archive_page()
            action = "RELINKED" if updated else "LINKED"
            print(f"dimension_link_{action.lower()} id={dimension_id} entry={entry}")
            try:
                self.host.center_hint["text"] = f"SIMULATION {action} // {str(link.get('title') or entry.parent.name).upper()}"
            except Exception:
                pass
            return True
        except Exception as exc:
            print(f"dimension_link_failed entry={entry} expected_catalog={expected_catalog_key or '-'} err={exc}")
            try:
                prefix = "LINK REALITY FAILED" if expected_catalog_key else "LINK SIMULATION FAILED"
                self.host.center_hint["text"] = f"{prefix} // {exc}"
            except Exception:
                pass
            return False

    def _select_dimension(self, record: DimensionRecord):
        self.selected_id = record.dimension_id
        self._mark_seen(record)
        self._rebuild_archive_page()

    def _prev(self):
        self.menu_page = max(0, self.menu_page - 1)
        self.selected_id = ""
        self._rebuild_archive_page()

    def _next(self):
        self.menu_page += 1
        self.selected_id = ""
        self._rebuild_archive_page()

    def _choose_dimension(self, record: DimensionRecord):
        if not self.is_unlocked(record):
            try:
                self.host.center_hint["text"] = "LOCKED // ENTER ITS PLANET IN HOLOSPACE FIRST"
            except Exception:
                pass
            return False
        if not record.launchable:
            if str(record.link_id or "").startswith("catalog:"):
                return self.link_catalog_record(record)
            return False
        self.close_menu()
        return self._launch(record)

    def _launch(self, record: DimensionRecord):
        if getattr(self.host, "active_native_mode", None) is not None or not record.launchable:
            return False
        label = f"DIMENSION // {record.title.upper()}"

        # Newly linked simulations deliberately begin as independent compatibility
        # launches. Their source stays where the user keeps it. Later passes can
        # add a native adapter to that project and this exact same stable link will
        # automatically promote to the same-window lifecycle below.
        if record.origin == "linked" and not record.native_launchable:
            if record.entry is None or not record.entry.is_file():
                return False
            try:
                launcher = getattr(self.host, "launch_external_level", None)
                if not callable(launcher):
                    raise RuntimeError("host compatibility launcher unavailable")
                ok = bool(launcher(
                    record.entry,
                    label,
                    extra_env={
                        "HOLOVERSE_DIMENSION_ID": record.dimension_id,
                        "HOLOVERSE_PROJECT_ROOT": str(record.folder),
                        "HOLOVERSE_LINK_MODE": "compatibility_external",
                        "HOLOVERSE_RETURN_TARGET": "gleebs_dimension_archive",
                    },
                ))
                if ok:
                    self._mark_visit(record)
                    try:
                        self.host._append_mode_gateway_history(
                            "linked_dimension_launched", label=label, route="gleebs_archive_external",
                            extra={"dimension_id": record.dimension_id, "entry": str(record.entry)},
                        )
                    except Exception:
                        pass
                    print(f"dimension_enter route=gleebs_archive_external id={record.dimension_id} title={record.title}")
                return ok
            except Exception as exc:
                print(f"dimension_enter_failed route=gleebs_archive_external id={record.dimension_id} err={exc}")
                return False

        adapter_rel = record.adapter.relative_to(record.folder).as_posix()
        manifest = {
            "schema": 2,
            "launch_type": "native_panda",
            "native_adapter": adapter_rel,
            "host_contract": "holoverse_dimension_v1",
            "dimension_id": record.dimension_id,
            "compatibility": record.compatibility,
            "return_target": "gleebs_dimension_archive",
        }
        mode = {"name": record.title, "folder": record.folder, "manifest": manifest, "dimension": True}
        try:
            try:
                self.host.show_bridge_transition(
                    f"ENTERING {record.title.upper()}",
                    "NATIVE REALITY // SAME WINDOW",
                    target=1.0,
                    hold=0.12,
                )
                self.host._set_bridge_transition_alpha(max(0.24, float(getattr(self.host, "bridge_transition_alpha", 0.0) or 0.0)))
            except Exception:
                pass
            loading = getattr(self.host, "present_dimension_loading", None)
            if callable(loading):
                loading(record.title)
            self.host.suspend_for_native_mode(label)
            native = self.host._load_native_mode_object(mode, record.entry, label)
            self.host.active_native_mode = native
            self.host.native_mode_entry = Path(record.entry) if record.entry else None
            enter = getattr(native, "enter", None)
            if callable(enter):
                enter()
            # Pass 282.75: the same post-entry fix-ups as launch_native_mode (cursor for
            # mouse-driven realities, key forwarding for host-input realities).
            after_enter = getattr(self.host, "_after_native_mode_enter", None)
            if callable(after_enter):
                after_enter(native, label)
            refresh = getattr(self.host, "refresh_ui", None)
            if callable(refresh):
                refresh()
            try:
                self.host.fade_bridge_transition(hold=0.08)
            except Exception:
                pass
            self._mark_visit(record)
            try:
                self.host._append_mode_gateway_history(
                    "dimension_entered", mode=mode, label=label, route="gleebs_archive"
                )
            except Exception:
                pass
            print(f"dimension_enter route=gleebs_archive id={record.dimension_id} title={record.title}")
            return True
        except Exception as exc:
            print(f"dimension_enter_failed route=gleebs_archive id={record.dimension_id} err={exc}")
            try:
                self.host.return_from_native_mode(reason="dimension-load-failed")
            except Exception:
                pass
            return False

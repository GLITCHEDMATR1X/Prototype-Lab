from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .constants import DEFAULT_SEED, ZONE_DEFS, ZONE_ORDER


def user_data_root() -> Path:
    """Where Zonez keeps the player's world saves (same layout as the other Glitched Matrix games).

    Windows %LOCALAPPDATA%\\GLITCHED MATRIX\\Zonez, macOS ~/Library/Application Support/GLITCHED MATRIX/Zonez,
    Linux ~/.local/share/glitched-matrix/zonez.  ZONEZ_USER_DATA overrides it (tests, portable runs).
    """
    override = str(os.environ.get('ZONEZ_USER_DATA') or '').strip()
    if override:
        return Path(override).expanduser()
    if os.name == 'nt':
        base = str(os.environ.get('LOCALAPPDATA') or '').strip()
        return (Path(base) if base else Path.home() / 'AppData' / 'Local') / 'GLITCHED MATRIX' / 'Zonez'
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'GLITCHED MATRIX' / 'Zonez'
    xdg = str(os.environ.get('XDG_DATA_HOME') or '').strip()
    return (Path(xdg) if xdg else Path.home() / '.local' / 'share') / 'glitched-matrix' / 'zonez'


class SaveSystem:
    """Player saves live in the user-data folder; the game's own zones/ folder only holds the
    starting seeds and is never written (so a shipped build carries nobody's progress)."""

    def __init__(self, root: Path):
        self.root = root                                  # game folder (read-only)
        self.seed_zones_root = root / 'zones'             # shipped starting states
        self.user_root = user_data_root()
        self.zones_root = self.user_root / 'zones'        # player saves
        self.zones_root.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.zones_root / 'session.json'
        for zone_key in ZONE_ORDER:
            self.zone_dir(zone_key).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _zone_folder(zone_key: str) -> str:
        return ZONE_DEFS[zone_key].folder_name if zone_key in ZONE_DEFS else zone_key

    def zone_dir(self, zone_key: str) -> Path:
        return self.zones_root / self._zone_folder(zone_key)

    def zone_state_path(self, zone_key: str) -> Path:
        return self.zone_dir(zone_key) / 'zone_state.json'

    def _readable_zone_state_path(self, zone_key: str) -> Path:
        saved = self.zone_state_path(zone_key)
        if saved.exists():
            return saved
        return self.seed_zones_root / self._zone_folder(zone_key) / 'zone_state.json'

    def save(self, active_zone: str, zone_states: dict[str, dict], world_size_chunks: int | None = None) -> Path:
        manifest = {
            'active_zone': active_zone,
            'world_size_chunks': int(world_size_chunks) if world_size_chunks is not None else None,
            'zones': {},
        }
        for zone_key, state in zone_states.items():
            zone_payload = {
                'zone_key': zone_key,
                'seed': int(state.get('seed', DEFAULT_SEED)),
                'player_pos': [float(v) for v in state.get('player_pos', (0.5, 0.5, 10.0))],
                'modifications': [
                    {'pos': [int(x), int(y), int(z)], 'block': int(block_id)}
                    for (x, y, z), block_id in sorted(state.get('modifications', {}).items())
                ],
            }
            zone_path = self.zone_state_path(zone_key)
            zone_path.parent.mkdir(parents=True, exist_ok=True)
            zone_path.write_text(json.dumps(zone_payload, indent=2), encoding='utf-8')
            manifest['zones'][zone_key] = {
                'folder': str(zone_path.parent.relative_to(self.user_root)).replace('\\', '/'),
                'state_file': str(zone_path.relative_to(self.user_root)).replace('\\', '/'),
            }
        self.manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        return self.manifest_path

    def load(self) -> dict | None:
        zones: dict[str, dict] = {}
        active_zone = ZONE_ORDER[0]

        manifest = None
        if self.manifest_path.exists():
            try:
                manifest = json.loads(self.manifest_path.read_text(encoding='utf-8'))
                active_zone = str(manifest.get('active_zone', active_zone))
            except (OSError, json.JSONDecodeError):
                manifest = None

        if manifest and isinstance(manifest.get('zones'), dict):
            zone_keys = list(manifest['zones'].keys())
        else:
            zone_keys = list(ZONE_ORDER)

        for zone_key in zone_keys:
            zone_path = self._readable_zone_state_path(zone_key)
            if not zone_path.exists():
                continue
            try:
                payload = json.loads(zone_path.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError):
                continue
            modifications = {}
            for item in payload.get('modifications', []):
                x, y, z = item.get('pos', [0, 0, 0])
                modifications[(int(x), int(y), int(z))] = int(item.get('block', 0))
            zones[zone_key] = {
                'seed': int(payload.get('seed', DEFAULT_SEED)),
                'player_pos': tuple(float(v) for v in payload.get('player_pos', [0.5, 0.5, 10.0])),
                'modifications': modifications,
            }

        if not zones:
            return None

        return {
            'active_zone': active_zone if active_zone in zones else next(iter(zones.keys())),
            'world_size_chunks': manifest.get('world_size_chunks') if isinstance(manifest, dict) else None,
            'zones': zones,
        }

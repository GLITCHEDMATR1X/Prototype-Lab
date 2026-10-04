"""HoloVerse native adapter for The Archivist 3-D dimension."""
from __future__ import annotations
from pathlib import Path
from archive3d.mode import ArchivistMode

ADAPTER_ID = "the_archivist_native_dimension_v5"
MODE_ID = "the_archivist"
HOST_CONTRACT = "holoverse_dimension_v1"


def adapter_manifest():
    return {
        "id": ADAPTER_ID,
        "mode_id": MODE_ID,
        "route": "native_panda",
        "host_contract": HOST_CONTRACT,
        "same_window_only": True,
        "forbid_child_process": True,
        "nested_dimension_capable": True,
        "return_target": "gleebs_dimension_archive",
    }


def create_mode(host_app, *, mode=None, entry_path: Path | None = None, label="The Archivist"):
    return ArchivistMode(host_app, mode=mode, entry_path=entry_path, label=label)


HoloVerseNativeMode = ArchivistMode
create_adapter = create_mode
create_native_adapter = create_mode

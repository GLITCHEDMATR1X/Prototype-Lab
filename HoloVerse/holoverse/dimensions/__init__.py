"""Host-owned dimension discovery, external linking, and Gleebs integration."""

from .links import inspect_entry, merge_link, recover_link, refresh_links
from .registry import DimensionRecord, DimensionRegistry, scan_dimension_packages

__all__ = [
    "DimensionRecord",
    "DimensionRegistry",
    "scan_dimension_packages",
    "inspect_entry",
    "merge_link",
    "recover_link",
    "refresh_links",
]

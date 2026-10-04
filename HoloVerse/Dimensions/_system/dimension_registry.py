"""Compatibility import for pre-Pass271 dimension tooling.

The authoritative host-owned implementation moved to
``holoverse.dimensions.registry`` in Pass 271.  Imported dimensions may still
refer to this historical path, so it remains as a deliberately tiny shim.
"""
from holoverse.dimensions.registry import *  # noqa: F401,F403

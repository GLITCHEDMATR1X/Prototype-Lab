"""Shared runtime for Mirror's Limbo and its linked worlds (DreamCatcher, Andrew's Nightmare).

Nested worlds find this package by walking up from their own folder to the Mirror's
Limbo root, then append that root to ``sys.path`` (appended, never prepended, so a
world's own modules always win over Limbo's).
"""

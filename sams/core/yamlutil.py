"""YAML loading that doesn't mangle SAMS keywords.

PyYAML follows YAML 1.1, where the bare words ``on``, ``off``, ``yes``, ``no`` are
booleans. SAMS uses ``on:`` as a key in workflow triggers and manifest routing
(spec 8.1, 6.2), so a default ``safe_load`` would turn that key into ``True``.
This loader uses YAML-1.2-style booleans (only ``true``/``false``), keeping
``on``/``off``/``yes``/``no`` as plain strings.
"""

from __future__ import annotations

from typing import Any

import yaml


class SamsSafeLoader(yaml.SafeLoader):
    """SafeLoader with the YAML-1.1 bool words demoted to strings."""


# Remove the implicit resolvers that map on/off/yes/no/y/n to booleans.
def _strip_bool_resolvers() -> None:
    bad_first_chars = "oOyYnN"  # on/off, yes/no (and y/n)
    for ch in list(SamsSafeLoader.yaml_implicit_resolvers):
        resolvers = [
            (tag, regexp)
            for tag, regexp in SamsSafeLoader.yaml_implicit_resolvers[ch]
            if tag != "tag:yaml.org,2002:bool" or ch not in bad_first_chars
        ]
        SamsSafeLoader.yaml_implicit_resolvers[ch] = resolvers


_strip_bool_resolvers()


def safe_load(text: str) -> Any:
    """Load YAML keeping ``on``/``off``/``yes``/``no`` as strings."""
    return yaml.load(text, Loader=SamsSafeLoader)

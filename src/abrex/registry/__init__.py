"""Generic component registration and lookup primitives."""

from abrex.registry.core import (
    DuplicateKeyError,
    RegisteredComponent,
    Registry,
    RegistryError,
    UnknownKeyError,
)

__all__ = [
    "DuplicateKeyError",
    "RegisteredComponent",
    "Registry",
    "RegistryError",
    "UnknownKeyError",
]

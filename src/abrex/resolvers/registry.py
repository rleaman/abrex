"""Default and injectable resolver registry."""

from __future__ import annotations

from abrex.registry import Registry
from abrex.resolvers.base import Resolver

RESOLVERS = Registry[Resolver]("resolvers")


def register_builtin_components() -> None:
    """Register deterministic resolver fixtures once per process."""

    from abrex.resolvers.adapters.toy import ToyResolver, ToyResolverConfig

    if "toy" not in RESOLVERS:
        RESOLVERS.register("toy", ToyResolver, config_model=ToyResolverConfig)


register_builtin_components()

__all__ = ["RESOLVERS", "register_builtin_components"]

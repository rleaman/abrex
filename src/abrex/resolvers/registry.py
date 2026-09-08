"""Default and injectable resolver registry."""

from __future__ import annotations

from abrex.registry import Registry
from abrex.resolvers.base import Resolver

RESOLVERS = Registry[Resolver]("resolvers")


def register_builtin_components() -> None:
    """Register deterministic resolver fixtures once per process."""

    from abrex.resolvers.adapters.ab3p import Ab3PResolverConfig
    from abrex.resolvers.adapters.ab3p_resolver import Ab3PResolver
    from abrex.resolvers.adapters.bioadi import BioADIResolver, BioADIResolverConfig
    from abrex.resolvers.adapters.learned import (
        LearnedScorerResolverConfig,
        create_learned_scorer_resolver,
    )
    from abrex.resolvers.adapters.schwartz_hearst import (
        SchwartzHearstResolver,
        SchwartzHearstResolverConfig,
    )
    from abrex.resolvers.adapters.toy import ToyResolver, ToyResolverConfig
    from abrex.resolvers.plod import PlodConfig, PlodSpanDetector
    from abrex.resolvers.plod_pairing import (
        PlodPairingResolver,
        PlodPairingResolverConfig,
    )

    if "toy" not in RESOLVERS:
        RESOLVERS.register("toy", ToyResolver, config_model=ToyResolverConfig)
    if "ab3p" not in RESOLVERS:
        RESOLVERS.register("ab3p", Ab3PResolver, config_model=Ab3PResolverConfig)
    if "bioadi" not in RESOLVERS:
        RESOLVERS.register("bioadi", BioADIResolver, config_model=BioADIResolverConfig)
    if "schwartz_hearst" not in RESOLVERS:
        RESOLVERS.register(
            "schwartz_hearst",
            SchwartzHearstResolver,
            config_model=SchwartzHearstResolverConfig,
        )
    if "learned_scorer" not in RESOLVERS:
        RESOLVERS.register(
            "learned_scorer",
            create_learned_scorer_resolver,
            config_model=LearnedScorerResolverConfig,
        )
    if "plodv2" not in RESOLVERS:
        RESOLVERS.register("plodv2", PlodSpanDetector, config_model=PlodConfig)
    if "plodv2_pairing" not in RESOLVERS:
        RESOLVERS.register(
            "plodv2_pairing",
            PlodPairingResolver,
            config_model=PlodPairingResolverConfig,
        )


register_builtin_components()

__all__ = ["RESOLVERS", "register_builtin_components"]

"""Application-layer construction of configured registry components."""

from __future__ import annotations

import inspect
from typing import Any, TypeVar

from pydantic import ValidationError

from abrex.config.models import ComponentSpec
from abrex.registry import RegisteredComponent, Registry

ComponentT = TypeVar("ComponentT")


def create_component[T](spec: ComponentSpec, registry: Registry[T]) -> T:
    """Validate ``spec.params`` and construct its registered component.

    A registration may provide a Pydantic model for actionable validation. If
    it does not, the factory signature still receives an explicit binding check
    before construction.
    """

    registration: RegisteredComponent[T] = registry.get_entry(spec.type)
    params: dict[str, Any] = spec.params
    if registration.config_model is not None:
        try:
            validated = registration.config_model.model_validate(params)
        except ValidationError as error:
            raise ValueError(
                f"Invalid params for component {spec.type!r}: {error}"
            ) from error
        params = validated.model_dump(mode="python")
    else:
        try:
            inspect.signature(registration.factory).bind(**params)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"Invalid params for component {spec.type!r}: {error}"
            ) from error
    return registration.factory(**params)

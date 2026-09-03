"""Unit and composition tests for the generic registry."""

from typing import Any, cast

import pytest
from pydantic import BaseModel

from abrex.config import ComponentSpec, create_component
from abrex.registry import (
    DuplicateKeyError,
    Registry,
    UnknownKeyError,
)


class ToyParams(BaseModel):
    greeting: str
    punctuation: str = "!"


def test_explicit_registration_lookup_and_alias() -> None:
    registry = Registry[str]("toy")

    def make(greeting: str, punctuation: str = "!") -> str:
        return greeting + punctuation

    returned = registry.register(
        "toy", make, aliases=("friendly",), config_model=ToyParams
    )

    assert returned is make
    assert registry.get("toy") is make
    assert registry.get("friendly") is make
    assert registry.create("toy", greeting="hi") == "hi!"
    assert registry.get_entry("friendly").key == "toy"
    assert registry.keys() == ("friendly", "toy")


def test_decorator_registration_and_explicit_alias() -> None:
    registry = Registry[str]("decorated")

    @registry.register("make")
    def make(value: str) -> str:
        return value

    registry.register_alias("identity", "make")
    assert registry.get("identity") is make


def test_registry_isolation_and_duplicate_protection() -> None:
    first = Registry[str]("first")
    second = Registry[str]("second")
    first.register("same", lambda: "first")
    second.register("same", lambda: "second")

    assert first.create("same") == "first"
    assert second.create("same") == "second"
    with pytest.raises(DuplicateKeyError, match="same"):
        first.register("same", lambda: "again")
    with pytest.raises(DuplicateKeyError, match="same"):
        first.register("other", lambda: "other", aliases=("same",))
    with pytest.raises(DuplicateKeyError, match="Duplicate keys"):
        first.register("duplicate", lambda: "duplicate", aliases=("duplicate",))
    with pytest.raises(DuplicateKeyError, match="same"):
        first.register_alias("same", "same")


def test_registry_rejects_bad_names_and_unknown_keys() -> None:
    with pytest.raises(ValueError, match="name"):
        Registry[str](" ")
    with pytest.raises(ValueError, match="name"):
        Registry[str](1)  # type: ignore[arg-type]
    registry = Registry[str]("empty")
    with pytest.raises(ValueError, match="non-empty"):
        registry.register(" ", lambda: "x")
    with pytest.raises(TypeError, match="callable"):
        registry.register("bad", cast(Any, 1))
    with pytest.raises(UnknownKeyError) as error:
        registry.get("missing")
    assert "Available keys: <none>" in str(error.value)
    with pytest.raises(UnknownKeyError, match="Available keys: known"):
        registry.register("known", lambda: "x")
        registry.get("missing")
    with pytest.raises(UnknownKeyError, match="known"):
        registry.register_alias("alias", "missing")


def test_component_composition_validates_pydantic_params() -> None:
    registry = Registry[str]("components")
    registry.register(
        "toy",
        lambda greeting, punctuation: greeting + punctuation,
        config_model=ToyParams,
    )

    spec = ComponentSpec(type="toy", params={"greeting": "hello"})
    assert create_component(spec, registry) == "hello!"
    with pytest.raises(ValueError, match="Invalid params"):
        create_component(ComponentSpec(type="toy", params={}), registry)


def test_component_composition_checks_factory_signature() -> None:
    registry = Registry[str]("components")

    def make(value: str) -> str:
        return value

    registry.register("make", make)
    assert (
        create_component(ComponentSpec(type="make", params={"value": "ok"}), registry)
        == "ok"
    )
    with pytest.raises(ValueError, match="Invalid params"):
        create_component(ComponentSpec(type="make", params={"other": "bad"}), registry)


def test_component_spec_rejects_extra_fields() -> None:
    with pytest.raises(ValueError, match="Extra inputs"):
        ComponentSpec.model_validate({"type": "toy", "params": {}, "extra": True})


def test_registry_accepts_arbitrary_component_output() -> None:
    registry = Registry[Any]("any")
    registry.register("value", lambda: {"ok": True})
    assert registry.create("value") == {"ok": True}

"""Small, dependency-free registry abstraction.

The registry stores factories and metadata only. Configuration parsing and
component construction live in the application/configuration layer.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, overload

if TYPE_CHECKING:
    from pydantic import BaseModel

type Factory[T] = Callable[..., T]


class RegistryError(Exception):
    """Base class for registry failures."""


class DuplicateKeyError(RegistryError):
    """Raised when a key or alias is already registered."""


class UnknownKeyError(RegistryError):
    """Raised when a requested key is not registered."""

    def __init__(
        self, registry_name: str, key: str, available_keys: tuple[str, ...]
    ) -> None:
        self.registry_name = registry_name
        self.key = key
        self.available_keys = available_keys
        available = ", ".join(available_keys) or "<none>"
        super().__init__(
            f"Unknown key {key!r} in registry {registry_name!r}. "
            f"Available keys: {available}"
        )


@dataclass(frozen=True, slots=True)
class RegisteredComponent[T]:
    """A registered factory and its optional parameter-validation model."""

    key: str
    factory: Factory[T]
    config_model: type[BaseModel] | None = None


class Registry[T]:
    """An isolated registry mapping stable keys to component factories."""

    def __init__(self, name: str) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Registry name must not be empty")
        self.name = name
        self._components: dict[str, RegisteredComponent[T]] = {}

    @staticmethod
    def _validate_key(key: str) -> str:
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Registry keys must be non-empty strings")
        return key

    @overload
    def register(
        self,
        key: str,
        factory: Factory[T],
        *,
        aliases: Iterable[str] = (),
        config_model: type[BaseModel] | None = None,
    ) -> Factory[T]: ...

    @overload
    def register(
        self,
        key: str,
        factory: None = None,
        *,
        aliases: Iterable[str] = (),
        config_model: type[BaseModel] | None = None,
    ) -> Callable[[Factory[T]], Factory[T]]: ...

    def register(
        self,
        key: str,
        factory: Factory[T] | None = None,
        *,
        aliases: Iterable[str] = (),
        config_model: type[BaseModel] | None = None,
    ) -> Factory[T] | Callable[[Factory[T]], Factory[T]]:
        """Register a factory explicitly or return a registration decorator."""

        canonical_key = self._validate_key(key)
        alias_keys = tuple(self._validate_key(alias) for alias in aliases)
        all_keys = (canonical_key, *alias_keys)
        if len(set(all_keys)) != len(all_keys):
            raise DuplicateKeyError(
                f"Duplicate keys in registration for {self.name!r}: {all_keys!r}"
            )

        def add_component(
            component_factory: Factory[T],
        ) -> Factory[T]:
            if not callable(component_factory):
                raise TypeError("Registered component must be callable")
            duplicates = [name for name in all_keys if name in self._components]
            if duplicates:
                duplicate_text = ", ".join(repr(name) for name in duplicates)
                raise DuplicateKeyError(
                    f"Keys already registered in {self.name!r}: {duplicate_text}"
                )
            component: RegisteredComponent[T] = RegisteredComponent(
                canonical_key, component_factory, config_model
            )
            for name in all_keys:
                self._components[name] = component
            return component_factory

        if factory is None:
            return add_component
        return add_component(factory)

    def register_alias(self, alias: str, key: str) -> None:
        """Register one explicit alias for an existing canonical key."""

        alias = self._validate_key(alias)
        key = self._validate_key(key)
        if alias in self._components:
            raise DuplicateKeyError(
                f"Key {alias!r} is already registered in {self.name!r}"
            )
        component = self.get_entry(key)
        self._components[alias] = component

    def get_entry(self, key: str) -> RegisteredComponent[T]:
        """Return registration metadata for ``key``."""

        try:
            return self._components[key]
        except KeyError as error:
            raise UnknownKeyError(self.name, key, self.keys()) from error

    def get(self, key: str) -> Factory[T]:
        """Return the factory registered under ``key``."""

        return self.get_entry(key).factory

    def create(self, key: str, *args: object, **kwargs: object) -> T:
        """Call a registered factory directly.

        Configuration-aware construction is intentionally provided separately
        by :func:`abrex.config.composition.create_component`.
        """

        return self.get(key)(*args, **kwargs)

    def keys(self) -> tuple[str, ...]:
        """Return all canonical keys and explicit aliases in stable order."""

        return tuple(sorted(self._components))

    def __contains__(self, key: object) -> bool:
        """Return whether ``key`` is registered, including explicit aliases."""

        return key in self._components

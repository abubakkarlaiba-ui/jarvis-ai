"""
Dependency injection container for JARVIS.
==========================================
Provides a lightweight DI system using class-based providers.
Ensures singleton instances where appropriate and manages lifecycle.

Usage:
    from jarvis.config.dependency import Container, get_container
    container = get_container()
    brain = container.resolve("brain")
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class Provider:
    """Wraps a factory function and its resulting singleton instance."""

    __slots__ = ("factory", "instance", "singleton")

    def __init__(self, factory: Callable, singleton: bool = True):
        self.factory = factory
        self.instance: Any = None
        self.singleton = singleton

    def resolve(self) -> Any:
        """Return the cached instance or create a new one."""
        if self.singleton and self.instance is not None:
            return self.instance
        instance = self.factory()
        if self.singleton:
            self.instance = instance
        return instance


class Container:
    """Central dependency injection container.

    Registers factories by name and resolves them on demand.
    Supports both named and type-based resolution.

    Example:
        container = Container()
        container.register("brain", lambda: BrainModule(), singleton=True)
        brain = container.resolve("brain")
    """

    def __init__(self):
        self._providers: dict[str, Provider] = {}
        self._type_providers: dict[Type, Provider] = {}
        self._initialized = False

    def register(
        self,
        name: str,
        factory: Callable,
        singleton: bool = True,
        type_hint: Type | None = None,
    ) -> None:
        """Register a factory under a name and optional type hint.

        Args:
            name: Unique identifier for the provider.
            factory: Callable that returns the dependency instance.
            singleton: If True, the factory is called once and the result is cached.
            type_hint: Optional type for type-based resolution.
        """
        self._providers[name] = Provider(factory, singleton)
        if type_hint is not None:
            self._type_providers[type_hint] = self._providers[name]
        logger.debug("Registered provider: %s (singleton=%s)", name, singleton)

    def resolve(self, name: str) -> Any:
        """Resolve a dependency by name.

        Args:
            name: The registered name of the dependency.

        Returns:
            The resolved instance.

        Raises:
            KeyError: If no provider is registered with the given name.
        """
        if name not in self._providers:
            raise KeyError(f"No provider registered with name '{name}'")
        return self._providers[name].resolve()

    def resolve_type(self, type_hint: Type[T]) -> T:
        """Resolve a dependency by its type hint.

        Args:
            type_hint: The type to resolve.

        Returns:
            An instance matching the requested type.

        Raises:
            KeyError: If no provider is registered for the given type.
        """
        if type_hint not in self._type_providers:
            raise KeyError(f"No provider registered for type {type_hint.__name__}")
        return self._type_providers[type_hint].resolve()

    def has(self, name: str) -> bool:
        """Check whether a provider is registered."""
        return name in self._providers

    def reset(self) -> None:
        """Reset all cached singleton instances without removing registrations."""
        for provider in self._providers.values():
            provider.instance = None
        self._initialized = False
        logger.info("Container reset: all singleton instances cleared")


_container: Container | None = None


def get_container() -> Container:
    """Return the global container singleton.

    Returns:
        The application-wide dependency injection container.
    """
    global _container
    if _container is None:
        _container = Container()
    return _container

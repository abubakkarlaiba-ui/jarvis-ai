"""
Performance module — lazy-load modules on demand for fast startup.
================================================================
Provides a lazy-loading mechanism that defers module imports until first use.
"""

from __future__ import annotations

import importlib
import sys
import time
from typing import Any

from jarvis.core.performance.base import CacheStrategy


class _ModuleProxy:
    """Proxy object that loads on first attribute access."""

    def __init__(self, loader: LazyLoader, module_path: str):
        object.__setattr__(self, "_loader", loader)
        object.__setattr__(self, "_path", module_path)
        object.__setattr__(self, "_module", None)

    def _ensure_loaded(self) -> Any:
        mod = object.__getattribute__(self, "_module")
        if mod is None:
            loader = object.__getattribute__(self, "_loader")
            path = object.__getattribute__(self, "_path")
            mod = loader.load(path)
            object.__setattr__(self, "_module", mod)
        return mod

    def __getattr__(self, name: str) -> Any:
        return getattr(self._ensure_loaded(), name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(self._ensure_loaded(), name, value)

    def __repr__(self) -> str:
        mod = object.__getattribute__(self, "_module")
        path = object.__getattribute__(self, "_path")
        if mod is not None:
            return repr(mod)
        return f"<LazyProxy for '{path}'>"


class LazyLoader:
    """Lazy-load modules on demand for fast startup."""

    def __init__(self) -> None:
        self._registry: dict[str, str] = {}
        self._loaded: dict[str, Any] = {}
        self._load_times: dict[str, float] = {}

    def register(self, module_path: str, module_name: str | None = None) -> None:
        self._registry[module_path] = module_name or module_path

    def load(self, module_path: str) -> Any:
        if module_path in self._loaded:
            return self._loaded[module_path]

        name = self._registry.get(module_path, module_path)
        start = time.perf_counter()
        try:
            module = importlib.import_module(name)
        except Exception:
            # Try importing as an attribute chain: a.b.c => import a, getattr a.b, getattr a.b.c
            parts = name.split(".")
            module = importlib.import_module(parts[0])
            for part in parts[1:]:
                module = getattr(module, part)
        elapsed = time.perf_counter() - start

        self._loaded[module_path] = module
        self._load_times[module_path] = elapsed
        sys.modules[name] = module
        return module

    def load_attr(self, module_path: str, attr_name: str) -> Any:
        module = self.load(module_path)
        return getattr(module, attr_name)

    def is_loaded(self, module_path: str) -> bool:
        return module_path in self._loaded

    def get_loaded(self) -> list[str]:
        return list(self._loaded.keys())

    def preload(self, module_paths: list[str]) -> None:
        for path in module_paths:
            self.load(path)

    def unload(self, module_path: str) -> bool:
        if module_path not in self._loaded:
            return False
        name = self._registry.get(module_path, module_path)
        del self._loaded[module_path]
        self._load_times.pop(module_path, None)
        sys.modules.pop(name, None)
        return True

    def get_load_time(self, module_path: str) -> float:
        return self._load_times.get(module_path, -1.0)

    def get_stats(self) -> dict:
        times = list(self._load_times.values())
        total = len(self._registry) + len(self._loaded)
        loaded = len(self._loaded)
        avg_time = sum(times) / len(times) if times else 0.0
        return {
            "total_registered": len(self._registry),
            "loaded": loaded,
            "avg_load_time": avg_time,
        }

    def create_proxy(self, module_path: str) -> Any:
        return _ModuleProxy(self, module_path)

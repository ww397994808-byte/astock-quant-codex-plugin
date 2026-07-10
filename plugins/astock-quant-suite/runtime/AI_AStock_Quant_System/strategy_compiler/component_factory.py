from __future__ import annotations

import importlib

from strategy_compiler.component_registry import ComponentRegistry


class ComponentFactory:
    def __init__(self, registry: ComponentRegistry | None = None) -> None:
        self.registry = registry or ComponentRegistry()

    def create(self, component_name: str, params: dict | None = None):
        spec = self.registry.require(component_name)
        module = importlib.import_module(spec.import_path)
        cls = getattr(module, spec.class_name)
        merged = {**spec.default_params, **(params or {})}
        return cls(**merged)

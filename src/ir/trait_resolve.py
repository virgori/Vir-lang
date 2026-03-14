"""
trait_resolve.py – Trait Resolution for Vir Type System
========================================================
Phase 3 Task E2: Resolve trait implementations at compile time.

Responsibilities:
  1. Register trait definitions (method signatures)
  2. Register impl blocks (trait + target type + methods)
  3. Resolve trait method calls to concrete implementations
  4. Check trait bounds on generic type parameters
  5. Report errors for missing implementations

Static dispatch by default (no vtable unless `dyn Trait`).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TraitMethod:
    """A method declared in a trait."""
    name: str
    param_types: list[str]
    return_type: str = ""
    has_self: bool = True


@dataclass
class TraitDef:
    """A trait definition."""
    name: str
    methods: list[TraitMethod] = field(default_factory=list)
    generic_params: list[str] = field(default_factory=list)


@dataclass
class ImplDef:
    """An impl block linking a trait to a concrete type."""
    trait_name: str
    target_type: str
    methods: dict[str, str] = field(default_factory=dict)  # trait_method → impl_func_name
    generic_params: list[str] = field(default_factory=list)


@dataclass
class TraitError:
    """Error in trait resolution."""
    message: str
    location: str = ""


class TraitResolver:
    """
    Resolves trait method calls to concrete implementations.

    Usage:
        resolver = TraitResolver()
        resolver.register_trait(TraitDef("Display", [TraitMethod("to_string", [], "str")]))
        resolver.register_impl(ImplDef("Display", "Vec_i64", {"to_string": "vec_i64_to_string"}))
        func_name = resolver.resolve("Display", "to_string", "Vec_i64")
        # → "vec_i64_to_string"
    """

    def __init__(self) -> None:
        self._traits: dict[str, TraitDef] = {}
        # (trait_name, target_type) → ImplDef
        self._impls: dict[tuple[str, str], ImplDef] = {}
        self.errors: list[TraitError] = []

    def register_trait(self, trait: TraitDef) -> None:
        """Register a new trait definition."""
        self._traits[trait.name] = trait

    def register_impl(self, impl_def: ImplDef) -> None:
        """Register an impl block."""
        # Validate trait exists
        if impl_def.trait_name not in self._traits:
            self.errors.append(TraitError(
                f"Trait '{impl_def.trait_name}' not found",
            ))
            return

        trait = self._traits[impl_def.trait_name]

        # Validate all required methods are implemented
        for method in trait.methods:
            if method.name not in impl_def.methods:
                self.errors.append(TraitError(
                    f"Missing method '{method.name}' in impl {impl_def.trait_name} "
                    f"for {impl_def.target_type}",
                ))

        self._impls[(impl_def.trait_name, impl_def.target_type)] = impl_def

    def resolve(self, trait_name: str, method_name: str,
                target_type: str) -> str | None:
        """Resolve a trait method call to a concrete function name."""
        key = (trait_name, target_type)
        impl_def = self._impls.get(key)
        if impl_def is None:
            return None
        return impl_def.methods.get(method_name)

    def check_bounds(self, type_name: str, required_traits: list[str]) -> list[TraitError]:
        """Check that a type satisfies all required trait bounds."""
        errors = []
        for trait_name in required_traits:
            if trait_name not in self._traits:
                errors.append(TraitError(f"Unknown trait '{trait_name}'"))
                continue
            key = (trait_name, type_name)
            if key not in self._impls:
                errors.append(TraitError(
                    f"Type '{type_name}' does not implement trait '{trait_name}'"
                ))
        return errors

    def has_impl(self, trait_name: str, target_type: str) -> bool:
        """Check if a type implements a trait."""
        return (trait_name, target_type) in self._impls

    def get_trait(self, name: str) -> TraitDef | None:
        """Get trait definition by name."""
        return self._traits.get(name)

    def all_impls_for(self, target_type: str) -> list[ImplDef]:
        """Get all trait impls for a type."""
        return [
            impl_def for (_, t), impl_def in self._impls.items()
            if t == target_type
        ]

"""Finite receiver-type values and joins; no target imports or execution."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ReceiverValue:
    types: frozenset[str] = frozenset()
    unknown: bool = False
    external: bool = False

    def join(self, other: ReceiverValue) -> ReceiverValue:
        return ReceiverValue(
            self.types | other.types,
            self.unknown or other.unknown,
            self.external or other.external,
        )

    @property
    def project_only(self) -> bool:
        return bool(self.types) and not (self.unknown or self.external)


UNKNOWN_RECEIVER = ReceiverValue(unknown=True)
EXTERNAL_RECEIVER = ReceiverValue(external=True)


@dataclass
class ReceiverState:
    values: dict[str, ReceiverValue] = field(default_factory=dict)
    containers: set[str] = field(default_factory=set)
    dynamic_modules: set[str] = field(default_factory=set)

    def join(self, other: ReceiverState) -> ReceiverState:
        return ReceiverState(
            {
                name: self.values.get(name, UNKNOWN_RECEIVER).join(
                    other.values.get(name, UNKNOWN_RECEIVER)
                )
                for name in self.values.keys() | other.values.keys()
            },
            self.containers & other.containers,
            self.dynamic_modules | other.dynamic_modules,
        )

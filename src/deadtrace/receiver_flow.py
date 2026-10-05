"""Finite receiver-type values and joins; no target imports or execution."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ReceiverValue:
    types: frozenset[str] = frozenset()
    unknown: bool = False
    external: bool = False
    external_annotation: bool = False
    external_nominal: str | None = None

    def join(self, other: ReceiverValue) -> ReceiverValue:
        return ReceiverValue(
            self.types | other.types,
            self.unknown or other.unknown,
            self.external or other.external,
            (self.external or other.external)
            and (not self.external or self.external_annotation)
            and (not other.external or other.external_annotation),
            self.external_nominal
            if not other.external
            else other.external_nominal
            if not self.external
            else self.external_nominal
            if self.external_nominal == other.external_nominal
            else None,
        )

    @property
    def project_only(self) -> bool:
        return bool(self.types) and not (self.unknown or self.external)


UNKNOWN_RECEIVER = ReceiverValue(unknown=True)
EXTERNAL_RECEIVER = ReceiverValue(external=True)


@dataclass(frozen=True)
class StringValue:
    """A bounded set of immutable strings, or an explicitly unknown value."""

    names: frozenset[str] = frozenset()
    unknown: bool = True

    def join(self, other: StringValue) -> StringValue:
        names = self.names | other.names
        if self.unknown or other.unknown or len(names) > 32:
            return StringValue()
        return StringValue(names, unknown=False)


@dataclass
class ReceiverState:
    values: dict[str, ReceiverValue] = field(default_factory=dict)
    containers: set[str] = field(default_factory=set)
    dynamic_modules: set[str] = field(default_factory=set)
    strings: dict[str, StringValue] = field(default_factory=dict)

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
            {
                name: self.strings.get(name, StringValue()).join(
                    other.strings.get(name, StringValue())
                )
                for name in self.strings.keys() | other.strings.keys()
            },
        )

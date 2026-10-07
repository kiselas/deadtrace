# ADR-0056: Fixtures of a base class in another module are inherited

**Status:** Accepted, 2026-10-07; model revision 38.

A pytest fixture defined as a method of a base class is visible to every subclass, wherever the
base lives. The tests world kept fixtures in per-module namespaces and resolved only those
defined in or imported into the test module, so a test class that inherits `items` from a base
class in `tests/base.py` requested an unresolved fixture (`DT3201`), which made the world
incomplete and suppressed findings.

For each top-level class, the fixtures that its project ancestors in other modules define as
members join the namespace of the subclass's module. The granularity stays per module, like the
rest of the namespace model: a module with a subclass sees the fixture for all its tests. A
wrong join only resolves a request that would otherwise be reported as unresolved, so it keeps
code and adds a dependency edge to a real fixture; it never reports anything.

The case `corpus/frameworks/fixture_base_class_other_module` fails on revision 37.

MODEL_REVISION becomes `python-fastapi-dishka/38`.

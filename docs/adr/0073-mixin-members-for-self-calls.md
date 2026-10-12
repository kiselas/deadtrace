# ADR-0073: A self call reaches the member each subclass's MRO finds

**Status:** Accepted, 2026-10-12; model revision 55.

A call `self.m()` in class `B` may run `m` of any project subclass of `B` (ADR-0020). Overrides were
looked up only among members that a subclass defines itself. A mixin listed before `B` in a
subclass's bases, as in `class SortQuery(_NoFilterMixin, BaseQuery)`, supplies `m` through the
subclass's MRO without being a subclass of `B`, so its `m` was reported as unreached: the largest
remaining class of false findings on the reviewed cohorts (14 findings, template methods filled in by
mixins).

For each project subclass of `B`, the member that attribute lookup on that subclass finds first is
now an override target too, unless it is `B`'s own. This only adds call targets.

The case `corpus/python/mixin_supplies_template_hook` fails on revision 54.

MODEL_REVISION becomes `python-fastapi-dishka/55`.

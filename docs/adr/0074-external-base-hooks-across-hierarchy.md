# ADR-0074: External base hooks are blocked across the class hierarchy

**Status:** Accepted, 2026-10-12; model revision 56. Amends ADR-0071.

ADR-0071 blocks a finding on a method whose own class has an external base. A mixin usually has no
base: `TestDataMixin.setUpTestData` and `JSONResponseMixin.render_to_response` become hooks only in
the classes that mix them into a `TestCase` or a Django view. Such findings were shown and were
false (11 remaining `external-base-convention-hooks` findings on the reviewed cohorts).

`external_base_hooks` now applies when the method's class, any project ancestor of it, or any project
subclass of it has an external base. As before, blocking changes what is shown, not the analysis.

MODEL_REVISION becomes `python-fastapi-dishka/56`.

# ADR-0112: Django database cases inherit fixture hooks from project mixins

**Status:** Accepted, 2026-10-13; model revision 93. Paired development evaluation complete.

## Context

Django database test bases call `_fixture_setup` during pre-setup and `_fixture_teardown`
during post-teardown. A project subclass may supply those overrides through a project mixin
before its external Django base. The existing external-base boundary includes methods declared
on the subclass, but misses private callbacks inherited from a mixin without its own external
base. Model 92 fails four independently specified callback expectations.

Independent contract: [Django testcases source](https://github.com/django/django/blob/stable/5.2.x/django/test/testcases.py).
The classmethod setup form introduced in Django 5.2 and the earlier instance form both dispatch
the same name. Target code remains parsed as data, never imported or executed.

## Decision

For a class whose external ancestry names Django's TestCase, TransactionTestCase,
LiveServerTestCase or StaticLiveServerTestCase, include the first project definition of each
fixture hook in that class's external-base boundary. Recognize public Django import paths
and the defining `django.test.testcases` module. Use existing project MRO lookup, not global
name matching. The boundary becomes active only when the derived class is used.

Do not generalize to all private methods, arbitrary external bases, SimpleTestCase, or plain
unittest.TestCase. Shadowed project definitions remain candidates. The existing MRO skips
external definitions, so this is conservative where an external base precedes a project mixin;
it does not prove the precise full MRO of dependencies absent from the source universe.

## Verification and consequences

`corpus/frameworks/django_inherited_fixture_hooks` originated as a known violation, pinned
to exactly four unmet expectations on model 92 before implementation. Model 93 meets them.
Negative controls retain an unrelated private helper, an unused mixin's hook, a shadowed hook
and a fixture-named method mixed into plain unittest.TestCase as candidates.

Add capability `django.test-fixture-hooks` revision 1. Model revision becomes
`python-fastapi-dishka/93`; no new blocked reason, runtime dependency or report schema is added.
Compare reviewed development findings and identical seed-7 injection sets before accepting
the measured effect. No new blind accuracy claim follows from these development comparisons.

On the same 531 reviewed development targets, model 93 removes two confirmed false findings,
with no new findings or true losses. Seed-7 development and holdout injection identities and
reported flags are unchanged. Two other false callbacks in alternative conditional definitions
remain reported because lookup currently selects one project class binding. This is a partial
fix of that source pattern. See [the field methodology](../field/2026-10-cohort.md).

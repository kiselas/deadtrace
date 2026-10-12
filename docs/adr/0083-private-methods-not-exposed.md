# ADR-0083: A class handed to an unknown consumer exposes no private methods

**Status:** Accepted, 2026-10-12; model revision 66.

When a project class escapes to code the model does not resolve (`register(Handler)`, a class
stored where a framework reads it), the consumer may call any method the class offers. The model
protected every method of the class and its project bases, private ones included, through the
`escaped_class` and `escaped_reference` boundaries.

Code outside a class calls its public methods, its special `__name__` methods, and hooks that
libraries look up by a `_name_` name (`_repr_html_`, `_missing_`). A method named `_name` or
`__name` is private by Python convention, and `__name` is even mangled; it runs when the class's
own code calls it, and those calls resolve: `self._parse()` in a method that the consumer may run
is an edge from that method. The `namedtuple` protocol (`_asdict`, `_replace`, `_make`) is the
exception and stays exposed.

Other ways to reach a private method are unchanged: a base outside the project still guards every
method (`external_base_hooks`), a call on a value of unknown type still dispatches by name to
private methods as well, `getattr` with a computed name still dispatches, and a method passed as a
value (`callback=self._on_click`) still escapes itself.

Measured with the recall injections (10 packages, seed 7, private definitions): reported went
from 476 to 534 of 721 (66.0% to 74.1%). The rule adds findings on real projects, so its precision
was checked on the reviewed cohorts before acceptance (`docs/field/`).

The case `corpus/python/escaped_class_private_methods` fails on revision 65.

MODEL_REVISION becomes `python-fastapi-dishka/66`.

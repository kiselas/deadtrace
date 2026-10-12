# ADR-0092: Listing a value of unknown type uses its public members

**Status:** Accepted, 2026-10-12; model revision 75.

ADR-0089 lets `dir(x)`, `vars(x)` and `inspect.getmembers(x)` on a value of unknown type protect
every member of every project class. Plugin managers list whatever they are given: pluggy's
`dir(plugin)`, typer's listing of command objects. In the recall injections of revision 72 that
protection hid 44 injected private methods of pluggy and typer (534 to 490 of 721).

Code that lists the members of an arbitrary value works with the value's public interface: it
filters out names that start with an underscore (`not name.startswith("_")`), or looks for markers
that only public hooks carry. A private method is called by its own class, where the call
resolves, as ADR-0083 already assumes for a class handed to an unknown consumer.

For a value of unknown type, the listing now protects the public members of project classes and
of modules held as values: names without a leading underscore, `__name__` special methods, and
`_name_` hooks are kept, as in ADR-0083. A value of a known project type or a project class keeps
all members of its class family. `x.__dict__.get(name)` is unchanged.

Measured: recall injections are back to 534 of 721; the eight false findings ADR-0089 removed stay
removed (their listed methods are public).

The case `corpus/python/namespace_listing_public_members` fails on revision 74.

MODEL_REVISION becomes `python-fastapi-dishka/75`.

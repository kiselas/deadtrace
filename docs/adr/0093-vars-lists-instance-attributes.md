# ADR-0093: vars() of a value lists its own attributes

**Status:** Accepted, 2026-10-12; model revision 76.

ADR-0089 treats `vars(x)` like `dir(x)`: it lists the members of `x`, and for a value of unknown
type ADR-0092 protects the public members of every project class. But `vars(x)` is `x.__dict__`.
For an instance that is the instance's own attributes, and a callable stored there escaped where
it was stored; methods live in the class's namespace. Only `vars(SomeClass)` lists methods.

On the reviewed cohorts, `main(**vars(build_parser().parse_args()))` in one project protected six
reviewed true findings (cohort e) between revisions 71 and 75.

`vars(x)` now lists members only when `x` resolves to a project class; any other value lists
nothing the model tracks. A class used as a value already exposes its public methods (ADR-0083).
`dir(x)` and `inspect.getmembers(x)` are unchanged: they include the class's members. In the same
change, listing a value known to come from outside the project protects nothing.

The case `corpus/python/vars_lists_instance_attributes` fails on revision 75.

MODEL_REVISION becomes `python-fastapi-dishka/76`.

# ADR-0064: Keywords of a class statement are evaluated

**Status:** Accepted, 2026-10-07; model revision 46.

`class UserAdmin(ModelView, model=User)` evaluates `User` when the statement runs and hands it to
the base class's `__init_subclass__` or metaclass. The frontend visited the bases and decorators
of a class statement but not its keywords, so `User` had no reference and was reported as
unreached (5 reviewed findings in one cohort project, sqladmin-style admin classes).

The keyword values of a class statement are now visited like any expression the statement
evaluates. This only adds references; it cannot add a finding.

The case `corpus/frameworks/class_keyword_argument_reference` fails on revision 45.

MODEL_REVISION becomes `python-fastapi-dishka/46`.

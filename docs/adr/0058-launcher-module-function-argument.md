# ADR-0058: A `module:function` argument in a command file roots that function

**Status:** Accepted, 2026-10-07; model revision 40.

The deployment reader (ADR-0023) knows servers, task workers, `python -m`, and a few other
launchers. Others take the same `module:function` argument: `opyrator launch-ui app:hello` in a
supervisor program, an internal runner in a Makefile. Functions that only such a command starts
were reported as unreached: 23 reviewed members in one cohort project.

In a command file other than `pyproject.toml` (whose entry points have their own reader), a token
of the form `module:identifier` is recorded as a module reference. Ports (`host:8000`) and image
tags (`python:3.12`) start with a digit and do not match; a name that matches no project module
adds nothing. The rule only roots code, so it cannot add a finding.

The case `corpus/frameworks/launcher_module_function_argument` fails on revision 39.

MODEL_REVISION becomes `python-fastapi-dishka/40`.

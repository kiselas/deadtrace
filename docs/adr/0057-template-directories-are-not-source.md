# ADR-0057: Template directories are not source

**Status:** Accepted, 2026-10-07; model revision 39.

Project templates (cookiecutter, copier) keep their files below directories named like
`{{cookiecutter.project_slug}}`. Until rendered the files hold Jinja, so many fail to parse and
the rest describe code that does not exist at that path; the failures became `DT1001` limitations
and made worlds incomplete in cohort projects.

A directory whose name contains `{{` or `{%` is skipped by source discovery, like environments
and tool directories (ADR-0015). It appears in `skipped_directories`. The rule removes input
and so can only remove findings and limitations; it adds no code to any world.

The test `test_template_directories_are_not_source` fails on revision 38.

MODEL_REVISION becomes `python-fastapi-dishka/39`.

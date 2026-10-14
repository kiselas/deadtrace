# ADR-0119: Local Cookiecutter extensions named in the manifest are roots

**Status:** Proposed, 2026-10-14; model revision 94. Tracking: [issue 28](https://github.com/kiselas/deadtrace/issues/28).

## Context

Cookiecutter imports local extension objects listed under `_extensions` in a
template's `cookiecutter.json`. Its `simple_filter` decorator wraps a function in
a Jinja extension that registers the function as a filter. A reviewed FastAPI
template has a false finding on such a filter, loaded only by the manifest.

Independent contracts: [local extensions documentation](https://cookiecutter.readthedocs.io/en/stable/advanced/local_extensions.html),
[Cookiecutter v2.7.1 loader](https://github.com/cookiecutter/cookiecutter/blob/v2.7.1/cookiecutter/environment.py),
[simple_filter](https://github.com/cookiecutter/cookiecutter/blob/v2.7.1/cookiecutter/utils.py),
and [Jinja 3.1.6 string imports](https://github.com/pallets/jinja/blob/3.1.6/src/jinja2/utils.py).
These sources establish the expected behavior independently of scanner results.

Before implementation the owned case was pinned as a known violation: model 93
missed four expectations for the selected filter, helper, class and method. All
three unused controls stayed candidates. A package reexport adds a further local
binding boundary, even though the original library model already retains it.

## Decision

Read only exact `cookiecutter.json` manifests through the existing excluded-path,
symlink and 1 MiB input boundary. Parse JSON as data, never a template or program.
Require a top-level object, a list-valued `_extensions`, and string entries with
identifier components in `module.object` or `module:object` form. Invalid JSON,
excessive JSON nesting, wrong shapes, computed strings and other keys add no roots.

Record a `local_object` reference with the manifest as its origin. Resolve modules
by physical paths relative to that one template directory, preserving `src/`
layout independence. Do not use the general deployment suffix fallback or search
other templates. A regular package precedes a same-name `.py` file; a plain module
blocks importing descendants; namespace directories contribute no initializer.
Existing local package initializers traversed by an import are also module roots.
Directory names are projected once from collected module paths; lookup stops at
the first absent namespace. A long missing extension name must not cause quadratic
prefix construction. The independent 1,001-component work bound requires at most
one path join for a missing first component; the initial implementation made 1,001.

Resolve the selected object through existing static reexport facts. If logical
module names collide, use only symbols from the physical modules selected by the
program; build a temporary filtered index only when such shadowed symbols exist.
Use that same index for selected class members. No project values survive through
a global cache. Root the selected object conservatively in `production:commands`,
using existing configured-object behavior and provenance. Functions they call and
methods of selected classes receive their existing execution consequences.
Do not expose every definition of a module merely because it supplies an extension.

Add capability `cookiecutter.local-extensions` revision 1. MODEL_REVISION becomes
`python-fastapi-dishka/94`. No scanner dependency or external report schema changes.
Target source, configuration and extensions are never imported or executed.
Explicit configured worlds continue to replace automatic command-world inference.

## Consequences and validation

The independent eight-target case moves to `corpus/frameworks/cookiecutter_local_extensions`
after its four violations are resolved. Controls cover an unlisted helper in each
selected module and a same-name function in another template. Unit tests cover
regular-package reexports, package/file precedence, initializer roots, module
shadowing, directory locality, `src/` paths, invalid/oversized/deep manifests,
exclusions and symlinks.

External extensions, changes to `sys.path`, dynamic manifest rendering and runtime
replacement of exports are outside this bounded local-source rule. Ordinary
dotted strings do not create roots. Template source rendering is unchanged.

Before acceptance, compare reviewed development cohorts b–h on a clean model-94
revision worktree, classify every NEW/LOST member and check exact seed-7 injection
identities and outcomes. Run Ruff, both-platform mypy, coverage, both case
validators, build, wheel smoke and supported-platform CI. No blind accuracy or
general framework-support claim follows from the one development example.

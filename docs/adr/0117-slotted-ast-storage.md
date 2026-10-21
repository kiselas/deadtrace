# ADR-0117: Store parsed AST fields in slots

**Status:** Accepted, 2026-10-21. Internal storage change; model revision remains 94.
Supersedes the storage guarantees of ADR-0115 (exact node types and grammar fields in `vars`).

## Context

ADR-0115 shares attribute-dictionary keys, reducing peak RSS by about 19–20% on
two large FastAPI development inputs. Parsing still retains a dictionary for each
node. An owned synthetic tree of 10,000 functions used 30,880,240 bytes for native
nodes and dictionaries; slotted node objects alone used 10,560,072 bytes with a
conversion cost of about 0.3 seconds on CPython 3.12. Those object-size estimates
exclude scalar/list data and are not an OS RSS comparison with the current main.

An independent retained-allocation budget compares slots against the existing
grammar-key-sharing storage on 1,000 functions. It requires at least 15% less
retained traced allocation. The previous code fails that bound with 2,447,136
versus 2,447,128 bytes. A real-project comparison must include conversion costs.

## Decision

Continue parsing with the running interpreter's standard-library `ast` parser,
then rebuild one file using subclasses of its concrete node classes with slots
for the grammar fields and location attributes. Convert before publishing the
immutable `ParsedSource`. A local worklist/map handles children without recursive
conversion. Copy fields once from each native node while allocating its stored
children, rather than walking every child and then revisiting the parent. The
map preserves shared children and extra attributes without mutating the input.
Empty-field operators and contexts keep their original objects and
exact native types, including the frontend's `type(ctx) is ast.Load` check.

The grammar-only class registry retains no input values. Subclasses keep native
class names, `isinstance` relationships, field values and locations. Exact concrete
node types and identities change before publication; raw `vars(node)` no longer
projects the grammar fields. This supersedes those storage guarantees of ADR-0115.
Analysis passes still must not mutate the published tree.

AST class defaults of `None` remain visible through the storage metaclass, so
`ast.dump` keeps the standard omission behavior for optional fields. Instance
reads use slot descriptors. Deepcopy/pickle restore ordinary standard-library
nodes with all fields and extra dictionary attributes. No target code is executed
or imported, no dependency/parser/schema/capability change is introduced, and no
source data survives the analysis through the grammar registry.

The frontend's exact-type handler table uses a grammar-only canonical type lookup,
covering both native and stored nodes. Omitting this adaptation changed 352 of
358 corpus reports in an experimental run; canonical dispatch restored all hashes.
That experimental output is not accepted as a semantic change.

## Verification

Owned syntax tests compare dumps, locations, type names, standard-library subtype
checks, optional defaults, serialization and weak-reference release. Static data
verification of 549 source/corpus/fixture files (127,638 nodes) matched dumps,
deepcopy and pickle on CPython 3.12.4, 3.13.7 and 3.14.7 without importing target
modules. The 3.14 storage test includes template-string fields.

On model 94 the full gates passed: 625 tests passed and 4 were skipped with 94% coverage,
Ruff, mypy for Linux and Windows, both case validators, build and isolated wheel smoke.
All 360 default and world-members corpus reports are byte-identical to the previous
storage, and so is every report in the paired runs below. Exact seed-7 injections match
model 94 on development packages (534 of 721 reported) and holdout packages (964 of 1,565):
no identity or reported flag changed.

Paired fresh-process runs alternated the previous and the slotted storage on eight
modern-stack development inputs, with CPython 3.12.4 on Windows and both analyzers loaded
from fresh bytecode caches. Peak OS RSS never increased:

| Input | Peak RSS, text (MiB) | Ratio, text | Ratio, JSON |
| --- | ---: | ---: | ---: |
| Large FastAPI application A | 415.8 → 340.2 | 0.818 | 0.832 |
| Large FastAPI application B | 278.3 → 232.4 | 0.835 | 0.850 |
| FastAPI template | 58.0 → 52.5 | 0.904 | 0.913 |
| Asyncpg application | 37.8 → 36.9 | 0.977 | 0.983 |
| FastAPI 0.141.1 package | 54.1 → 51.9 | 0.959 | 0.960 |
| Dishka 1.10.1 package | 47.4 → 44.3 | 0.934 | 0.945 |
| Pydantic 2.13.5 package | 81.7 → 71.0 | 0.869 | 0.872 |
| Redis application | 34.0 → 34.0 | 1.000 | 0.996 |

Two-pair time ratios varied by about ±15% on this machine and are not a result. A
four-pair text repeat on the two large applications measured RSS ratios 0.821 and
0.834 with time ratios 1.057 and 1.078, consistent with the earlier model-93 series
(time +7.5–9.7%, RSS −17.8%).

## Consequences

- Large inputs use about 17–18% less peak memory and about 6–8% more time; small inputs
  are essentially unchanged in memory. The conversion cost is accepted, as ADR-0115
  accepted a comparable tradeoff; reducing it is separate work.
- Code that dispatches on exact AST node types must use `ast_storage.native_type`.
  Code must not read grammar fields through `vars(node)` or `__dict__`.
- Paired runtime measurements must compile both analyzers' bytecode first: with
  `PYTHONDONTWRITEBYTECODE` set, a stale cache on one side recompiles that analyzer in
  every sample and distorts both time and small-input memory.

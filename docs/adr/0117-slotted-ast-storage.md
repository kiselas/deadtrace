# ADR-0117: Store parsed AST fields in slots

**Status:** Proposed, 2026-10-13. Internal storage change; model revision remains 93.

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

## Decision under evaluation

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
projects the grammar fields. This supersedes those storage guarantees of ADR-0115
if accepted. Analysis passes still must not mutate the published tree.

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

## Verification and acceptance requirements

Owned syntax tests compare dumps, locations, type names, standard-library subtype
checks, optional defaults, serialization and weak-reference release. Static data
verification of 549 source/corpus/fixture files (127,638 nodes) matched dumps,
deepcopy and pickle on CPython 3.12.4, 3.13.7 and 3.14.7 without importing target
modules. The 3.14 storage test includes template-string fields.

All default/world-members corpus reports and reviewed modern-stack text/JSON
reports must remain byte-identical. Seed-7 injection identities/outcomes and
runtime failure behavior must remain unchanged. Run all quality/build/wheel gates
and supported-platform CI. Accept only after paired fresh-process time/OS peak
RSS measurements show that the extra conversion is justified; neither synthetic
object sizes nor the existing dictionary-sharing measurements prove that.

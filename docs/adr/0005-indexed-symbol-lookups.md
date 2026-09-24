# ADR-0005: Indexed symbol lookups instead of linear scans

**Status:** Accepted, 2026-09-24.

## Context

The scale fixture has no edges, classes, imports, or framework objects, so its profile could not show
costs that grow with those counts. The framework-shaped service fixture and the installed third-party
sources described in `benchmarks/README.md` did. On `main`, going from the 20,000-line to the
50,000-line service fixture (2.5 times the lines) multiplied framework discovery by 5.3 and world
planning and finding construction by 7.5. Timing wrappers and a cProfile run attributed the growth to
lookups that scan a whole collection once per query:

- `PythonProgram.resolve_symbol` compared the query with the full name of every symbol. The framework
  capabilities call it for every decorator argument, annotation, base class, and dependency: 12,464
  calls on the 50k service fixture, about a third of that scan's time under timing wrappers.
- `_called_parameter_names` walked the whole body of the called function again at every call site
  that resolved to it: 13,709 walks and 14.5 of 56 seconds on mypy's sources.
- Dishka route wiring rebuilt, for every route, the list of bindings available in the application's
  container, testing membership in a tuple of every registered provider.
- Finding construction rebuilt the ownership-and-edge adjacency of the whole graph for every
  registered binding, and the node map for every test-only candidate.
- Framework objects were looked up by scanning every object key; routes, hooks, and includes by
  scanning every registration for each owner; constructors, members, and Pydantic hooks by
  filtering every symbol by owner. The pytest model built the tuple of all node identifiers once per
  collected test, and the solver sorted all node identifiers once per unlocalized boundary.

Each of these computes a pure function of data that no longer changes when the lookup runs: the
symbol table is complete when `PythonProgram` is built, framework objects are complete when
`_discover_objects` returns, registrations and provider bindings are complete before world plans are
built, and the graph is final when the solver and findings run.

## Decision

1. `deadtrace.python_frontend.SymbolIndex` is built once from the finished symbol table and shared by
   the frontend resolver and `PythonProgram.index`. `named`, `resolve`, and `members` list symbols in
   symbol-table order, so they return exactly what the scans returned, including which symbol wins a
   tie; `under` answers prefix queries from the sorted full names. `resolve_symbol` answers from it.
2. The frontend resolver memoizes `_called_parameter_names` per symbol for the duration of one
   `build_python_program` call. The result depends only on the immutable syntax of that function.
3. Framework modeling indexes object keys by dotted name once `_discover_objects` has returned,
   groups routes, hooks, and includes by owner when planning starts, and computes the bindings
   available in each container once per container during planning. It computes the callables each
   capability accounts for once, before filtering escaped-callable boundaries.
4. Finding construction builds the adjacency and node map once per `build_findings` call. The pytest
   model and the solver build the tuple of all node identifiers once per call.
5. These are indexes over immutable inputs within one analysis. Nothing is cached across analyses,
   written to disk, or keyed by anything other than the objects of the current run.

## Consequences

- Semantic and inventory reports and exit codes are byte-identical to the previous commit for every
  corpus and seed case, the scale and service fixtures, other generated FastAPI/Dishka applications,
  and the staged third-party sources. The comparison and the measurements are in
  `benchmarks/results/2026-09-24-indexed-lookups.md`: on the 50k service fixture the affected stages
  fall from 15.9 to 2.2 seconds at the median, and they no longer grow faster than the source.
- An index goes stale if its input changes after it is built. No code does that today; a future
  pass that adds symbols, framework objects, registrations, or bindings after these points must
  rebuild the corresponding index.
- The remaining cost is parsing, position resolution, and visitors over LibCST trees, which these
  changes do not touch, and memory is unchanged.

# ADR-0007: The analysis parses with the standard-library `ast` module

**Status:** Accepted, 2026-09-24. Supersedes the parser choice behind ADR-0004; its one-parse rule
stays.

## Context

After ADR-0004 and ADR-0005, the stages that parse and walk LibCST trees took 99% of a scan of
mypy's 129k lines, and peak memory grew by about 4.3 MiB per 1,000 lines because every module's
tree and position map stayed alive until the frontend finished. LibCST resolves positions by
regenerating the module's source, and every `visit` rebuilds the visited nodes even for read-only
visitors. On the same sources, `ast.parse` plus a full `ast.walk` took 1.07 seconds against 31.4
seconds for LibCST parse, position resolution, and one visit.

The analysis never rewrites source. It needs node kinds, names, and start and end positions, which
`ast` records on every node. A concrete syntax tree matters only for the future patch-preview
track, which is gated and has no code yet.

Before switching, the spans of all 29,612 function and class definitions in 1,071 files (the corpus,
the fixtures, the generated benchmark projects, five installed packages, and Deadtrace itself) were
compared: LibCST's start and end positions equal `ast`'s `lineno`, `col_offset`, `end_lineno`, and
`end_col_offset` in every case once UTF-8 byte offsets are converted to character columns.

## Decision

1. `deadtrace.inventory.parse_source` parses with `ast.parse` of the running interpreter and keeps
   the module text in a `SourceText` for character columns and source segments. LibCST is no longer
   a dependency. Compiler warnings about the target program, such as invalid escape sequences, are
   suppressed during parsing.
2. The frontend, framework capabilities, and pytest model read `ast` nodes. Where the `ast` shape
   differs from the facts the analysis consumes, helpers restore those facts, each covered by
   `tests/test_syntax_facts.py`:
   - `True`, `False`, and `None` are constants in `ast`; facts keep spelling them as names.
   - Call arguments come back in source order with their keyword and `*`/`**` kind
     (`call_arguments`), not as separate positional and keyword lists.
   - `x[a, b]` has two index items and `x[(a, b)]` has one (`subscript_items`); when positions
     cannot tell `x[(a, b)]` from `x[(a), b]`, the source segment is tokenized.
   - A body on the header line, as in `class P(Provider): x = provide(A)`, contributes no block
     statements (`simple_block_statements`), matching the earlier statement-line rule.
   - A pytest name is read only from a single plain string literal, not from implicitly
     concatenated strings (`single_string_literal`).
   - Flow extraction visits statements in source order, each before the expressions it contains,
     and never enters nested definitions (`flow_nodes`). The order of expression nodes within one
     statement is not significant to any consumer.
3. A module that does not parse raises `SyntaxError`. Its `DT1001` issue reads
   `syntax error at line L, column C: <message>`, so the message text of unparseable files changes.
4. The accepted grammar is that of the interpreter Deadtrace runs on, which `requires-python` pins
   to 3.12. Widening `requires-python` must add the parser grammar to report descriptors in the same
   change, because the same source may parse differently on another minor version.
5. The benchmark artifact moves to schema 4: `descriptor.libcst_version` becomes
   `descriptor.parser`, for example `ast/3.12`.

## Consequences

- Semantic and inventory reports and exit codes are byte-identical for 36 targets (144 of 144
  files). Canonical dumps of every parser-independent fact (symbols, parameters, imports,
  statement lines, both graphs, framework objects and registrations, bindings, plans, worlds,
  derivations, findings, and inventory) are identical for 51 targets under a fixed hash seed,
  including a 29.7 MB dump of mypy with configured worlds. Without a fixed seed, only the order of
  `WorldPlan.root_provenance`, which is built from a set and sorted by the solver, differs between
  any two runs. The known-violation pins of ADR-0006 are unchanged.
- Measured speed and memory are in `benchmarks/results/2026-09-24-stdlib-ast.md`.
- Source that LibCST accepted but CPython 3.12 rejects now produces `DT1001`; this includes syntax
  newer than 3.12.
- Trees are still retained until the frontend finishes. Extracting compact per-module facts and
  releasing each tree afterwards is the next memory lever and is not part of this change.
- The patch-preview track needs a concrete syntax tree. It will bring its own dependency, confined
  to preview, under its own decision record.

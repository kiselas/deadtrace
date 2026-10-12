# ADR-0079: A compact semantic report

**Status:** Accepted, 2026-10-12. Changes the semantic report; no model revision (analysis unchanged).

On the largest project of the public cohorts (1,581 files, 859,000 lines, 32 worlds) the JSON report
was 340 MB: every world listed every definition it reaches (about 40,000 names, 32 times) and every
guard origin (about 100,000 `DT2002` entries per world). The beta criterion is 30 MB. No consumer in
deadtrace reads the member lists; comparison reads limitations.

The report now:

- gives `resolved_count` and `conservative_count` for each world; `resolved_may_run` and
  `conservative_may_run` are written only with `deadtrace scan --world-members`;
- lists limitations that every world has once, in a top-level `shared_limitations`, and in each
  world only its own;
- groups `DT2002` guard limitations by message with an `origins` count and a null `origin`, unless
  `--world-members` asks for every origin.

`compare` expands `shared_limitations` into every world and compares guards by world, code and message,
so reports written before and after this change, and with or without `--world-members`, compare alike.
The schema version stays 1: alpha schemas may change between releases, and the fields that remain keep
their meaning. On the largest project the report is now 24.5 MB and the scan 103 seconds; peak memory
is 2.3 GiB, above the 1 GiB beta criterion, which needs separate work.

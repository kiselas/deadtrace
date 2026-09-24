# Package re-exports

`pkg/__init__.py` re-exports `helper` and, under the alias `PublicService`, the class
`Service` from the private module `pkg._impl`. `main` calls `helper` through
`from pkg import helper` and through the package, `pkg.helper()`, and calls `run` on a
`PublicService`. Reporting `helper`, `Service`, or `Service.run` as unreached is unsafe.
`pkg._impl.unused` is not re-exported or called and must stay a candidate.

Recorded as a known violation of the analysis contract (ADR-0006) and met from model
revision `python-fastapi-dishka/7` (ADR-0010).

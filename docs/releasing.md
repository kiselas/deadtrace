# Release acceptance and publication

0.1.0a1 is the first public read-only alpha, scanner model 31 (ADR-0049). Freeze semantics during
release preparation. Future semantic changes require their own independent cases, ADR and model
revision. The selected object-store refinement is outside this release.

| Acceptance | Required evidence |
| --- | --- |
| Quality | Locked sync, Ruff check/format, strict mypy, pytest --cov >=90% |
| Independent cases | Seed and corpus validators; known-violation and recall-gap ratchets in pytest |
| Packaging | Wheel + sdist with matching name/version, SHA-256 and byte counts |
| Installed behavior | The same built wheel smoke on Linux and Windows outside the source tree |
| Trust boundary | Smoke's no-target-execution sentinel and unit/corpus/oracle tests |
| Publication identity | Successful ci.yml push run on main at the exact immutable version tag |
| Public delivery | GitHub prerelease with receipt/artifacts; pinned PyPI install and wheel smoke |

This is release acceptance for the existing alpha, not completion of the historical roadmap's
future A01-A40 matrix. Record the exact release commit and hosted CI/publish run URLs in GitHub
Release. Local results cannot substitute for missing platform jobs.

Local candidate checks on Windows, 2026-10-05: Ruff check/format (585 files), mypy Windows/Linux
targets (61 files), pytest 517 passed with two expected Windows/empty-case skips, coverage 93.21%,
seed validator 6 cases/12 targets and corpus validator 123 semantic cases/426 targets. Offline
locked sync, lock check and wheel/sdist build pass. Isolated wheel smoke passes including exact
version, deterministic reports and no target execution. Actionlint validates both release workflows.
Hosted verification and public installation are recorded in the tagged GitHub Release after they pass.

Run CONTRIBUTING.md's local gates, both validators, build and isolated installed-wheel smoke.
CI's build job seals dist/release-receipt.json and uploads deadtrace-COMMIT-distributions; both
operating systems consume those bytes. After all checks pass, merge the release PR and wait for
the main push CI to pass. Create v0.1.0a1 at that commit, then dispatch publish.yml from main with
tag v0.1.0a1 and ci_run_id from that successful main run. The verifier checks GitHub run identity,
tag/version/ancestry, metadata and receipt hashes before an OIDC-enabled job publishes without
rebuilding. The owner's PyPI pending publisher must authorize kiselas/deadtrace and publish.yml.

Download that CI artifact for GitHub Release attachments, then verify installation with:

```console
uv run --isolated --no-project --python 3.12 --with "deadtrace==0.1.0a1" deadtrace --version
uv run --isolated --no-project --python 3.12 --with "deadtrace==0.1.0a1" python scripts/wheel_smoke.py
```

Do not move a published tag or replace a PyPI file. Correct a failed alpha with a new version;
retain receipts and CI logs for the published bytes.

# Security policy

## Supported versions

Deadtrace is pre-alpha. Security fixes are applied to the latest development release; older
pre-alpha versions are not maintained.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting for this repository. Do not open a public
issue for vulnerabilities involving arbitrary code execution, path traversal, unintended writes,
secret disclosure, dependency compromise, or unsafe analysis of untrusted repositories.

Include a minimal reproduction, affected version or commit, expected impact, and any known
workaround. Maintainers will acknowledge a complete report as soon as practical and coordinate
disclosure after a fix is available.

## Trust boundary

The static scanner is designed not to import or execute target projects and not to use the
network. This promise does not automatically apply to future opt-in oracle or verification
environments; those must have separate threat models and explicit user consent.

"""Deadtrace command-line interface."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from deadtrace import __version__
from deadtrace.analysis import analyze
from deadtrace.artifacts import (
    MAX_REPORT_BYTES,
    ArtifactError,
    read_json_artifact,
    render_json_artifact,
)
from deadtrace.baseline import (
    apply_baseline,
    create_baseline,
    render_baseline_json,
    update_baseline,
)
from deadtrace.benchmark import benchmark, render_benchmark_json, render_benchmark_text
from deadtrace.case_validator import CaseValidationError, validate_cases
from deadtrace.comparison import (
    Comparability,
    compare_reports,
    render_comparison_json,
    render_comparison_text,
)
from deadtrace.config import ConfigurationError, discover_config, load_config
from deadtrace.diagnostics import render_troubleshooting_json, render_troubleshooting_text
from deadtrace.report import render_json, render_text
from deadtrace.scanner import scan as inventory_scan
from deadtrace.semantic_report import (
    doctor_text,
    explain_fingerprint,
    render_semantic_json,
    render_semantic_text,
    semantic_report_dict,
)

app = typer.Typer(
    add_completion=False,
    help="Explainable, framework-aware dead-code analysis without target execution.",
    no_args_is_help=True,
)
cases_app = typer.Typer(help="Validate development case fixtures.", no_args_is_help=True)
baseline_app = typer.Typer(help="Manage explicit reviewed-finding baselines.", no_args_is_help=True)
app.add_typer(cases_app, name="cases")
app.add_typer(baseline_app, name="baseline")


class OutputFormat(StrEnum):
    TEXT = "text"
    JSON = "json"


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"deadtrace {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Show version."),
    ] = None,
) -> None:
    """Deadtrace never imports or executes the project being scanned."""

    del version


@app.command("scan")
def scan_command(
    path: Annotated[Path, typer.Argument(help="Python file or project directory to inventory.")],
    output_format: Annotated[
        OutputFormat,
        typer.Option("--format", help="Output format for stdout."),
    ] = OutputFormat.TEXT,
    config: Annotated[
        Path | None,
        typer.Option("--config", help="Explicit pyproject.toml path."),
    ] = None,
    inventory_only: Annotated[
        bool,
        typer.Option("--inventory-only", help="Stop after lexical inventory."),
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Write the selected report format to this file."),
    ] = None,
    fail_on_findings: Annotated[
        bool,
        typer.Option("--fail-on-findings", help="Exit 1 when review findings are emitted."),
    ] = False,
    require_complete: Annotated[
        bool,
        typer.Option("--require-complete", help="Exit 2 when any required world is incomplete."),
    ] = False,
    baseline_path: Annotated[
        Path | None,
        typer.Option("--baseline", help="Annotate findings using a reviewed baseline JSON file."),
    ] = None,
    fail_on_new: Annotated[
        bool,
        typer.Option("--fail-on-new", help="Exit 1 when findings are not accepted by baseline."),
    ] = False,
) -> None:
    """Analyze a project without importing or executing it."""

    try:
        settings = load_config(discover_config(path, config))
    except ConfigurationError as error:
        typer.echo(f"configuration error: {error}", err=True)
        raise typer.Exit(code=2) from error

    if inventory_only:
        report = inventory_scan(path, settings)
        rendered = (
            render_json(report) if output_format is OutputFormat.JSON else render_text(report)
        )
        _emit_report(rendered, output)
        for issue in report.issues:
            typer.echo(f"{issue.path}: {issue.code}: {issue.message}", err=True)
        if report.has_errors:
            raise typer.Exit(code=2)
        return

    result = analyze(path, settings)
    baseline_result = None
    if baseline_path is not None:
        try:
            baseline_result = apply_baseline(
                semantic_report_dict(result), read_json_artifact(baseline_path)
            )
        except ArtifactError as error:
            typer.echo(f"baseline error: {error}", err=True)
            raise typer.Exit(code=2) from error
    if output_format is OutputFormat.JSON:
        rendered = (
            render_json_artifact(baseline_result.payload)
            if baseline_result is not None
            else render_semantic_json(result)
        )
    else:
        rendered = render_semantic_text(result)
        if baseline_result is not None:
            rendered += (
                f"Baseline: {'comparable' if baseline_result.comparable else 'incomparable'} | "
                f"accepted={baseline_result.accepted} | new={baseline_result.new} | "
                f"stale={baseline_result.stale}\n"
            )
    _emit_report(rendered, output)
    for issue in result.inventory.issues:
        typer.echo(f"{issue.path}: {issue.code}: {issue.message}", err=True)
    if result.has_operational_errors or (
        (require_complete or settings.require_complete) and not result.complete
    ):
        raise typer.Exit(code=2)
    if fail_on_new:
        if baseline_result is None:
            typer.echo("--fail-on-new requires --baseline", err=True)
            raise typer.Exit(code=2)
        if not baseline_result.comparable:
            typer.echo(
                "baseline is not comparable with this analysis method: "
                f"{'; '.join(baseline_result.reasons)}; review the report and refresh it with "
                "`deadtrace baseline update`",
                err=True,
            )
            raise typer.Exit(code=2)
        if baseline_result.new:
            raise typer.Exit(code=1)
    if fail_on_findings and result.findings:
        raise typer.Exit(code=1)


@app.command()
def compare(
    before: Annotated[Path, typer.Argument(help="Earlier semantic report JSON.")],
    after: Annotated[Path, typer.Argument(help="Later semantic report JSON.")],
    output_format: Annotated[
        OutputFormat,
        typer.Option("--format", help="Output format for stdout."),
    ] = OutputFormat.TEXT,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Write the comparison artifact to this file."),
    ] = None,
    fail_on_new: Annotated[
        bool,
        typer.Option("--fail-on-new", help="Exit 1 when comparable reports add findings."),
    ] = False,
    require_comparable: Annotated[
        bool,
        typer.Option("--require-comparable", help="Exit 2 unless methods are comparable."),
    ] = False,
) -> None:
    """Compare two saved reports without scanning source or invoking Git."""

    try:
        comparison = compare_reports(read_json_artifact(before), read_json_artifact(after))
    except ArtifactError as error:
        typer.echo(f"comparison error: {error}", err=True)
        raise typer.Exit(code=2) from error
    rendered = (
        render_comparison_json(comparison)
        if output_format is OutputFormat.JSON
        else render_comparison_text(comparison)
    )
    _emit_report(rendered, output)
    if (require_comparable or fail_on_new) and comparison.status is not Comparability.COMPARABLE:
        raise typer.Exit(code=2)
    if fail_on_new and comparison.status is Comparability.COMPARABLE and comparison.added:
        raise typer.Exit(code=1)


@app.command("benchmark")
def benchmark_command(
    path: Annotated[Path, typer.Argument(help="Project directory to benchmark.")],
    runs: Annotated[
        int,
        typer.Option("--runs", min=1, max=100, help="Number of full static analyses."),
    ] = 3,
    output_format: Annotated[
        OutputFormat,
        typer.Option("--format", help="Output format for stdout."),
    ] = OutputFormat.TEXT,
    config: Annotated[
        Path | None,
        typer.Option("--config", help="Explicit pyproject.toml path."),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Write benchmark artifact to this file."),
    ] = None,
) -> None:
    """Measure parse, model, solve, and total time without executing the target."""

    try:
        settings = load_config(discover_config(path, config))
        result = benchmark(path, settings, runs)
    except (ConfigurationError, ValueError, RuntimeError) as error:
        typer.echo(f"benchmark error: {error}", err=True)
        raise typer.Exit(code=2) from error
    rendered = (
        render_benchmark_json(result)
        if output_format is OutputFormat.JSON
        else render_benchmark_text(result)
    )
    _emit_report(rendered, output)


@app.command("support-bundle")
def support_bundle_command(
    path: Annotated[Path, typer.Argument(help="Project directory to inspect statically.")],
    output_format: Annotated[
        OutputFormat,
        typer.Option("--format", help="Output format."),
    ] = OutputFormat.JSON,
    config: Annotated[
        Path | None,
        typer.Option("--config", help="Explicit pyproject.toml path."),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Write the inspected troubleshooting bundle."),
    ] = None,
) -> None:
    """Create aggregate diagnostics without source, paths, symbols, or configuration values."""

    try:
        settings = load_config(discover_config(path, config))
        result = analyze(path, settings)
    except ConfigurationError as error:
        typer.echo(f"configuration error: {error}", err=True)
        raise typer.Exit(code=2) from error
    rendered = (
        render_troubleshooting_json(result)
        if output_format is OutputFormat.JSON
        else render_troubleshooting_text(result)
    )
    if output is not None:
        typer.echo(render_troubleshooting_text(result), err=True, nl=False)
    _emit_report(rendered, output)
    if result.has_operational_errors:
        raise typer.Exit(code=2)


@app.command()
def doctor(
    path: Annotated[Path, typer.Argument(help="Project directory to inspect.")],
    config: Annotated[
        Path | None,
        typer.Option("--config", help="Explicit pyproject.toml path."),
    ] = None,
) -> None:
    """Show roots, capabilities, assembly state, and blockers."""

    try:
        settings = load_config(discover_config(path, config))
    except ConfigurationError as error:
        typer.echo(f"configuration error: {error}", err=True)
        raise typer.Exit(code=2) from error
    typer.echo(doctor_text(analyze(path, settings)), nl=False)


@app.command()
def explain(
    fingerprint: Annotated[str, typer.Argument(help="Finding fingerprint from the report.")],
    report: Annotated[Path, typer.Option("--report", help="Existing JSON report file.")],
) -> None:
    """Explain a saved finding without silently re-analyzing changed source."""

    try:
        payload = read_json_artifact(report)
        typer.echo(explain_fingerprint(payload, fingerprint), nl=False)
    except (ArtifactError, ValueError) as error:
        typer.echo(f"report error: {error}", err=True)
        raise typer.Exit(code=2) from error
    except KeyError as error:
        typer.echo(f"finding not present in report: {fingerprint}", err=True)
        raise typer.Exit(code=2) from error


@cases_app.command("validate")
def validate_case_fixtures(
    path: Annotated[Path, typer.Argument(help="Directory containing seed-case folders.")],
) -> None:
    """Check case manifests and ensure their lexical targets exist."""

    try:
        result = validate_cases(path)
    except CaseValidationError as error:
        typer.echo(f"case validation error: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(
        f"Validated {result.cases} cases, {result.targets} lexical targets, "
        f"and {result.semantic_cases} semantic cases."
    )


@baseline_app.command("create")
def create_baseline_command(
    report: Annotated[Path, typer.Argument(help="Reviewed semantic report JSON.")],
    output: Annotated[Path, typer.Option("--output", help="New baseline JSON file.")],
    reason: Annotated[
        str,
        typer.Option("--reason", help="Why the current findings are accepted for later review."),
    ],
) -> None:
    """Record current findings as reviewed debt; never updates an existing file implicitly."""

    if output.exists():
        typer.echo(f"baseline output already exists: {output}", err=True)
        raise typer.Exit(code=2)
    try:
        rendered = render_baseline_json(create_baseline(read_json_artifact(report), reason))
    except ArtifactError as error:
        typer.echo(f"baseline error: {error}", err=True)
        raise typer.Exit(code=2) from error
    _emit_report(rendered, output)


@baseline_app.command("update")
def update_baseline_command(
    baseline: Annotated[Path, typer.Argument(help="Existing baseline JSON file.")],
    report: Annotated[Path, typer.Argument(help="Current semantic report JSON.")],
    output: Annotated[Path, typer.Option("--output", help="New updated baseline JSON file.")],
    accept_new: Annotated[
        bool,
        typer.Option("--accept-new", help="Explicitly accept findings absent from the baseline."),
    ] = False,
    reason: Annotated[
        str | None,
        typer.Option("--reason", help="Required review reason when --accept-new is used."),
    ] = None,
) -> None:
    """Rebase reviewed entries without accepting new findings by default."""

    if output.exists():
        typer.echo(f"baseline output already exists: {output}", err=True)
        raise typer.Exit(code=2)
    try:
        rendered = render_baseline_json(
            update_baseline(
                read_json_artifact(baseline),
                read_json_artifact(report),
                accept_new=accept_new,
                reason=reason,
            )
        )
    except ArtifactError as error:
        typer.echo(f"baseline error: {error}", err=True)
        raise typer.Exit(code=2) from error
    _emit_report(rendered, output)


def _emit_report(rendered: str, output: Path | None) -> None:
    if output is None:
        typer.echo(rendered, nl=False)
        return
    try:
        output.write_text(rendered, encoding="utf-8", newline="\n")
    except OSError as error:
        typer.echo(f"cannot write report {output}: {error}", err=True)
        raise typer.Exit(code=2) from error
    typer.echo(f"Wrote report to {output}", err=True)
    size = len(rendered.encode("utf-8"))
    if size > MAX_REPORT_BYTES:
        typer.echo(
            f"report {output} is {size} bytes; baseline, compare, and explain read at most "
            f"{MAX_REPORT_BYTES} bytes",
            err=True,
        )

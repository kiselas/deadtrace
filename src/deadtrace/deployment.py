"""Read execution roots from deployment commands and configuration files as text (ADR-0023).

Deployments start Python programs by name outside Python: ``uvicorn svc.main:app`` in a Compose
file, ``arq svc.worker.WorkerSettings`` in a Dockerfile, ``python -m svc.tasks`` in a
``Procfile``, a logging configuration naming ``class: pkg.Formatter``. These files are read as
bounded text; nothing in them is executed, and a name that matches no project module adds
nothing.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Protocol

from deadtrace.artifacts import InputTooLargeError, read_bounded_bytes
from deadtrace.scanner import is_skipped_directory

MAX_DEPLOYMENT_FILE_BYTES = 1024 * 1024
"""Deployment files and logging configurations are small; larger files are data and skipped."""

COMMAND_FILE_PATTERNS = (
    "docker-compose*.yml",
    "docker-compose*.yaml",
    "compose*.yml",
    "compose*.yaml",
    "Dockerfile*",
    "*.Dockerfile",
    "*.dockerfile",
    "Containerfile*",
    "Procfile",
    "Procfile.*",
    "Makefile",
    "makefile",
    "GNUmakefile",
    "*.mk",
    "justfile",
    "Justfile",
    "*.sh",
    "*.conf",
    "*.ini",
    "*.service",
    ".gitlab-ci.yml",
    "app.yaml",
    "fly.toml",
    "pyproject.toml",
)
"""Files whose commands start programs: containers, process managers, and build scripts."""
CONFIGURATION_SUFFIXES = (".conf", ".ini", ".cfg", ".yaml", ".yml", ".json", ".toml")
"""Logging configurations: files of these types whose name mentions ``log``, or that a
command passes as ``--log-config``."""

SERVERS = frozenset({"uvicorn", "gunicorn", "hypercorn", "daphne", "granian"})
"""Servers whose ``module:attribute`` argument names the application they run."""
_DEFAULT_APPLICATION = {"gunicorn": "application", "hypercorn": "app"}
"""The attribute a server runs when its target names only a module."""
_SERVER_VALUE_OPTIONS = frozenset(
    {"-b", "--bind", "--insecure-bind", "--quic-bind", "-c", "--config", "--uds", "--fd"}
)
"""Server options whose ``scheme:value`` arguments look like targets."""
_WORKER_SUBCOMMANDS = frozenset({"worker", "scheduler", "run", "serve", "docs"})
_INTERPRETER = re.compile(r"python[\d.]*|PYTHON\w*")
_PYTHON_OPTIONS_WITH_VALUE = frozenset({"-X", "-W", "--check-hash-based-pycs"})
_TOKEN_SEPARATORS = re.compile(r"[\s\"'`,\[\]{}()\\]+")
_ATTACHED_BREAKS = re.compile(r"(&&|\|\||;|\|)")
_COMMAND_BREAKS = frozenset({"&&", "||", ";", "|", "&", "then", "do", "exec"})
_STATEMENT_KEY = re.compile(r"^\s+(?:-\s+)?[A-Za-z_][\w.-]*\s*[:=](?:\s|$)")
"""An indented line that starts a new key of a Compose, INI, or YAML file."""
_TARGET = re.compile(r"^[A-Za-z_][\w.]*(:[A-Za-z_][\w.]*)?$")
_ASSIGNMENT = re.compile(r"^[A-Za-z_]\w*=")
_CONFIGURED_CLASS = re.compile(
    r"""(?:^|[\s,{])["']?(?:class|\(\)|factory|format_class|handler_class)["']?\s*[:=]\s*"""
    r"""["']?([A-Za-z_][\w]*(?:\.[A-Za-z_]\w*)+)""",
    re.MULTILINE,
)


class _Add(Protocol):
    def __call__(self, kind: str, target: str, *, exposed: bool = False) -> None: ...


@dataclass(frozen=True, slots=True)
class DeploymentReference:
    """A program or object that a deployment file names.

    ``kind`` is ``module`` for ``module`` or ``module:attribute`` targets, ``script`` for a path
    run by ``python``, ``object`` for a dotted class or callable a configuration names, and
    ``discovery`` for the leaf name of modules a worker imports by searching its directory.
    ``exposed`` marks a module whose top-level definitions the program reads by name, as
    gunicorn reads hooks from its configuration and locust reads user classes from a locustfile.
    """

    kind: str
    target: str
    source: str
    exposed: bool = False


def read_deployment_references(
    root: Path, exclude: tuple[str, ...] = ()
) -> tuple[DeploymentReference, ...]:
    """Commands and configured object names in the deployment files below ``root``."""

    if not root.is_dir():
        return ()
    commands: list[tuple[Path, str]] = []
    configurations: list[tuple[Path, str]] = []
    for current, directory_names, file_names in os.walk(root, followlinks=False):
        current_path = Path(current)
        directory_names[:] = sorted(
            name for name in directory_names if not is_skipped_directory(current_path, name)
        )
        for name in sorted(file_names):
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            if any(fnmatchcase(relative, pattern) for pattern in exclude):
                continue
            if any(fnmatchcase(name, pattern) for pattern in COMMAND_FILE_PATTERNS):
                commands.append((path, relative))
            if name.lower().endswith(CONFIGURATION_SUFFIXES):
                configurations.append((path, relative))
    found: set[DeploymentReference] = set()
    log_configurations: set[str] = set()
    for path, relative in commands:
        text = _read_text(path)
        if text is not None:
            found.update(_command_references(text, relative, log_configurations))
    for path, relative in configurations:
        named = "log" in path.name.lower() or any(
            relative == item or relative.endswith(f"/{item}") for item in log_configurations
        )
        text = _read_text(path) if named else None
        if text is not None:
            found.update(
                DeploymentReference("object", match.group(1), relative)
                for match in _CONFIGURED_CLASS.finditer(text)
            )
    return tuple(
        sorted(found, key=lambda item: (item.kind, item.target, item.source, item.exposed))
    )


def _read_text(path: Path) -> str | None:
    try:
        if path.is_symlink():
            return None
        text = read_bounded_bytes(path, limit=MAX_DEPLOYMENT_FILE_BYTES).decode(
            "utf-8", errors="replace"
        )
        return text.replace("\r\n", "\n").replace("\r", "\n")
    except (OSError, InputTooLargeError):
        return None


def _statements(text: str) -> str:
    """The text with comments removed and a break before every line that starts a statement.

    A line starts a statement when it is not indented, as a shell or Dockerfile line, or starts
    an indented key; indented lines and lines after a trailing backslash continue it, as a YAML
    folded command or a flow list over several lines does. A Dockerfile ``CMD`` right after an
    ``ENTRYPOINT`` continues it, since Docker appends the two.
    """

    lines: list[str] = []
    previous = ""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        continued = previous.endswith("\\") or (
            stripped.startswith("CMD") and previous.startswith("ENTRYPOINT")
        )
        if not continued and (not line[:1].isspace() or _STATEMENT_KEY.match(line)):
            lines.append(";")
        lines.append(stripped.removeprefix("CMD") if continued else stripped)
        previous = stripped
    return _ATTACHED_BREAKS.sub(r" \1 ", "\n".join(lines))


def _command_references(
    text: str, source: str, log_configurations: set[str]
) -> set[DeploymentReference]:
    tokens = [token for token in _TOKEN_SEPARATORS.split(_statements(text)) if token]
    found: set[DeploymentReference] = set()

    def add(kind: str, target: str, *, exposed: bool = False) -> None:
        found.add(DeploymentReference(kind, target, source, exposed))

    for index, token in enumerate(tokens):
        if _ASSIGNMENT.match(token):
            token = token.split("=", 1)[1]
        program = token.rsplit("/", 1)[-1]
        arguments = _arguments(tokens, index + 1)
        if program in SERVERS:
            _server_references(program, arguments, add, log_configurations)
        elif _INTERPRETER.fullmatch(program):
            _python_reference(arguments, add)
        elif program in {"faststream", "taskiq", "arq", "dramatiq", "huey_consumer"} or (
            program == "huey_consumer.py"
        ):
            positional, values = _split_options(arguments)
            if positional[:1] and positional[0] in _WORKER_SUBCOMMANDS:
                positional = positional[1:]
            targets = [item for item in positional if _TARGET.match(item)]
            if not targets:
                targets = [
                    value
                    for _, value in values
                    if _TARGET.match(value) and ("." in value or ":" in value)
                ]
            for target in targets:
                add("module", target)
            if program == "taskiq" and {"--fs-discover", "-fsd"} & set(arguments):
                pattern = _option_value(arguments, ("--tasks-pattern", "-tp")) or "tasks.py"
                leaf = pattern.rsplit("/", 1)[-1].removesuffix(".py")
                if leaf.isidentifier():
                    add("discovery", leaf)
        elif program == "celery":
            application = _option_value(arguments, ("-A", "--app"))
            if application is not None and _TARGET.match(application):
                add("module", application)
        elif program == "locust":
            path = _option_value(arguments, ("-f", "--locustfile"))
            if path is not None and path.endswith(".py"):
                add("script", path, exposed=True)
    return found


def _server_references(
    program: str,
    arguments: list[str],
    add: _Add,
    log_configurations: set[str],
) -> None:
    positional, values = _split_options(arguments)
    targets = [item for item in positional if ":" in item and _TARGET.match(item)]
    if not targets:
        targets = [
            value
            for option, value in values
            if option not in _SERVER_VALUE_OPTIONS and ":" in value and _TARGET.match(value)
        ]
    default = _DEFAULT_APPLICATION.get(program)
    if not targets and default is not None:
        targets = [f"{item}:{default}" for item in positional[-1:] if _TARGET.match(item)]
    for target in targets[:1]:
        add("module", target)
    configuration = _option_value(arguments, ("-c", "--config"))
    if configuration is None and program == "gunicorn":
        configuration = "gunicorn.conf.py"
    if configuration is not None:
        scheme, _, rest = configuration.partition(":")
        if scheme == "python" and _TARGET.match(rest):
            add("module", rest, exposed=True)
        elif configuration.endswith(".py"):
            add("script", rest if scheme == "file" else configuration, exposed=True)
    log_configuration = _option_value(arguments, ("--log-config", "--log-config-json"))
    if log_configuration is not None:
        log_configurations.add(log_configuration.rpartition(":")[2].lstrip("./"))


def _python_reference(arguments: list[str], add: _Add) -> None:
    position = 0
    while position < len(arguments):
        argument = arguments[position]
        if argument == "-m":
            if position + 1 < len(arguments) and _TARGET.match(arguments[position + 1]):
                add("module", arguments[position + 1])
            return
        if argument == "-c" or not argument.startswith("-"):
            break
        position += 2 if argument in _PYTHON_OPTIONS_WITH_VALUE else 1
    if position < len(arguments) and arguments[position].endswith(".py"):
        add("script", arguments[position])


def _arguments(tokens: list[str], start: int) -> list[str]:
    """The arguments of a command, up to the next command separator or 32 tokens."""

    arguments: list[str] = []
    for token in tokens[start : start + 32]:
        if token in _COMMAND_BREAKS:
            break
        arguments.append(token)
    return arguments


def _split_options(arguments: list[str]) -> tuple[list[str], list[tuple[str, str]]]:
    """Positional arguments, and the values of options that may take one.

    An option without ``=`` is taken to consume the next argument, since most options of these
    programs take values; a target that follows a flag is still found among the values.
    """

    positional: list[str] = []
    values: list[tuple[str, str]] = []
    position = 0
    while position < len(arguments):
        argument = arguments[position]
        if argument.startswith("-"):
            option, equals, value = argument.partition("=")
            if equals:
                values.append((option, value))
            elif position + 1 < len(arguments) and not arguments[position + 1].startswith("-"):
                values.append((argument, arguments[position + 1]))
                position += 1
        else:
            positional.append(argument)
        position += 1
    return positional, values


def _option_value(arguments: list[str], names: tuple[str, ...]) -> str | None:
    for position, argument in enumerate(arguments):
        for name in names:
            if argument == name and position + 1 < len(arguments):
                return arguments[position + 1]
            if argument.startswith(f"{name}="):
                return argument.split("=", 1)[1]
    return None

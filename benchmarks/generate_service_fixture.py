"""Generate a deterministic, non-executable FastAPI/Dishka/Pydantic service for benchmarking.

The scale fixture from ``generate_scale_fixture.py`` holds one function per module and produces no
edges, classes, imports, or framework objects, so it measures parsing only. This fixture repeats a
service-shaped domain package instead: Pydantic models with validators, a repository and a service
class, module-level helpers, a shared utility module, a Dishka provider, and a DishkaRoute router
whose endpoints use ``FromDishka`` and ``Depends``. Every domain also carries one unused function.
It is a performance guard only and says nothing about precision.
"""

from __future__ import annotations

import argparse
from pathlib import Path

MODELS_PER_DOMAIN = 5
METHODS_PER_CLASS = 10
HELPERS_PER_DOMAIN = 5
ENDPOINTS_PER_DOMAIN = 10

COMMON = '''"""Utilities shared by every domain."""

import logging

logger = logging.getLogger(__name__)


def audit(event: str, value: int) -> int:
    logger.debug("%s %s", event, value)
    return clamp(value)


def clamp(value: int) -> int:
    return max(0, min(value, 1_000_000))
'''


def domain_source(index: int) -> str:
    name = f"d{index:04d}"
    lines = [
        f'"""Service domain {name}."""',
        "",
        "import logging",
        "",
        "from dishka import Provider, Scope, provide",
        "from dishka.integrations.fastapi import DishkaRoute, FromDishka",
        "from fastapi import APIRouter, Depends",
        "from pydantic import BaseModel, field_validator",
        "",
        "from app.common import audit",
        "",
        "logger = logging.getLogger(__name__)",
        "router = APIRouter(route_class=DishkaRoute)",
        "",
    ]
    for model in range(MODELS_PER_DOMAIN):
        lines += [
            "",
            f"class Item{model}(BaseModel):",
            "    name: str",
            "    value: int",
            "",
            '    @field_validator("name")',
            "    @classmethod",
            "    def check_name(cls, value: str) -> str:",
            "        return value.strip()",
            "",
        ]
    lines += ["", "class Repo:"]
    for method in range(METHODS_PER_CLASS):
        lines += [
            f"    def op{method}(self, value: int) -> int:",
            f"        return helper{method % HELPERS_PER_DOMAIN}(value)",
            "",
        ]
    lines += [
        "",
        "class Service:",
        "    def __init__(self, repo: Repo) -> None:",
        "        self.repo = repo",
        "",
    ]
    for method in range(METHODS_PER_CLASS):
        lines += [
            f"    def run{method}(self, value: int) -> int:",
            f"        result = self.repo.op{method}(value)",
            f'        return audit("{name}.run{method}", normalize(result))',
            "",
        ]
    for helper in range(HELPERS_PER_DOMAIN):
        lines += [
            "",
            f"def helper{helper}(value: int) -> int:",
            f"    return normalize(value) * {helper + 1}",
            "",
        ]
    lines += [
        "",
        "def normalize(value: int) -> int:",
        "    return abs(value)",
        "",
        "",
        "def current_user() -> str:",
        '    return "user"',
        "",
        "",
        "class DomainProvider(Provider):",
        "    scope = Scope.REQUEST",
        "    repo = provide(Repo)",
        "    service = provide(Service)",
        "",
    ]
    for endpoint in range(ENDPOINTS_PER_DOMAIN):
        model = endpoint % MODELS_PER_DOMAIN
        lines += [
            "",
            f'@router.post("/{name}/op{endpoint}")',
            f"def endpoint{endpoint}(",
            f"    body: Item{model},",
            "    service: FromDishka[Service],",
            "    user: str = Depends(current_user),",
            f") -> Item{model}:",
            f"    service.run{endpoint}(body.value)",
            "    return body",
            "",
        ]
    lines += [
        "",
        "def legacy_unused() -> int:",
        "    return helper0(1)",
    ]
    return "\n".join(lines) + "\n"


def main_source(domains: int) -> str:
    names = [f"d{index:04d}" for index in range(domains)]
    lines = [
        "from dishka import make_async_container",
        "from dishka.integrations.fastapi import FastapiProvider, setup_dishka",
        "from fastapi import FastAPI",
        "",
        *(f"from app.domains import {name}" for name in names),
        "",
        "container = make_async_container(",
        *(f"    {name}.DomainProvider()," for name in names),
        "    FastapiProvider(),",
        ")",
        "app = FastAPI()",
        *(f"app.include_router({name}.router)" for name in names),
        "setup_dishka(container, app)",
    ]
    return "\n".join(lines) + "\n"


def _line_count(source: str) -> int:
    return source.count("\n")


def _total_lines(domains: int) -> int:
    package_markers = 2
    return (
        package_markers
        + _line_count(COMMON)
        + _line_count(main_source(domains))
        + domains * _line_count(domain_source(0))
    )


def domains_for(target_lines: int) -> int:
    """Return the smallest domain count whose generated sources reach ``target_lines``."""

    count = 1
    while _total_lines(count) < target_lines:
        count += 1
    return count


def generate(root: Path, target_lines: int = 50_000) -> int:
    if target_lines < 1_000:
        raise ValueError("target_lines must be at least 1000")
    domains = domains_for(target_lines)
    package = root / "app"
    (package / "domains").mkdir(parents=True, exist_ok=True)
    files = {
        package / "__init__.py": "\n",
        package / "domains" / "__init__.py": "\n",
        package / "common.py": COMMON,
        package / "main.py": main_source(domains),
        **{
            package / "domains" / f"d{index:04d}.py": domain_source(index)
            for index in range(domains)
        },
    }
    for path, contents in files.items():
        path.write_text(contents, encoding="utf-8", newline="\n")
    (root / "pyproject.toml").write_text(
        """[project]
name = "deadtrace-service-fixture"
version = "0.0.0"
dependencies = ["dishka==1.10.1", "fastapi==0.141.1"]
""",
        encoding="utf-8",
        newline="\n",
    )
    return sum(_line_count(contents) for contents in files.values())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--lines", type=int, default=50_000)
    arguments = parser.parse_args()
    generated = generate(arguments.output, arguments.lines)
    print(f"Generated {generated} Python LOC in {arguments.output}")


if __name__ == "__main__":
    main()

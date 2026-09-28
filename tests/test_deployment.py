from __future__ import annotations

from pathlib import Path

import pytest

from deadtrace.deployment import DeploymentReference, read_deployment_references


def _write(root: Path, path: str, text: str) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _targets(root: Path, exclude: tuple[str, ...] = ()) -> set[tuple[str, str]]:
    return {(item.kind, item.target) for item in read_deployment_references(root, exclude)}


def test_commands_of_servers_workers_and_scripts_are_read(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "docker-compose.yml",
        """services:
  api:
    command: gunicorn svc.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
  queue:
    command: ["faststream", "run", "svc.run_faststream:app"]
  beat:
    command: celery -A proj beat -l info
  jobs:
    command: taskiq worker svc.broker:broker svc.jobs && echo done
""",
    )
    _write(tmp_path, "svc/Dockerfile", 'CMD ["python3.12", "-m", "svc.tasks"]\n')
    _write(tmp_path, "Makefile", "load:\n\tlocust -f loadtest/locustfile.py --host http://x\n")
    _write(tmp_path, "scripts/start.sh", "exec hypercorn --bind :80 app.asgi:application\n")
    _write(tmp_path, "Procfile", "seed: python tools/seed.py\ntest: python -m pytest tests\n")

    references = read_deployment_references(tmp_path)

    assert {(item.kind, item.target) for item in references} == {
        ("module", "svc.main:app"),
        ("module", "svc.run_faststream:app"),
        ("module", "proj"),
        ("module", "svc.broker:broker"),
        ("module", "svc.jobs"),
        ("module", "svc.tasks"),
        ("script", "loadtest/locustfile.py"),
        ("script", "gunicorn.conf.py"),
        ("module", "app.asgi:application"),
        ("script", "tools/seed.py"),
        ("module", "pytest"),
    }
    assert DeploymentReference("module", "svc.tasks", "svc/Dockerfile") in references
    assert DeploymentReference("script", "loadtest/locustfile.py", "Makefile", True) in references


def test_option_values_are_no_targets(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "deploy/app.service",
        "[Service]\nExecStart=/srv/venv/bin/gunicorn --workers 3 --bind unix:app.sock "
        "-m 007 wsgi:app\n",
    )
    _write(tmp_path, "hyper.sh", "hypercorn --config python:svc.hconf svc.alt:app\n")
    _write(tmp_path, "arq.sh", "arq --watch svc svc.worker.WorkerSettings\n")
    _write(tmp_path, "dramatiq.sh", "dramatiq -Q default svc.broker svc.tasks\n")
    _write(tmp_path, "burst.sh", "arq --burst svc.cron.Settings\n")
    _write(tmp_path, "reload.sh", "uvicorn --reload svc.dev:app\n")
    _write(tmp_path, "wsgi.sh", "gunicorn -c conf/gunicorn.py svc.wsgi\n")

    assert _targets(tmp_path) == {
        ("module", "wsgi:app"),
        ("script", "gunicorn.conf.py"),
        ("module", "svc.hconf"),
        ("module", "svc.alt:app"),
        ("module", "svc.worker.WorkerSettings"),
        ("module", "svc.broker"),
        ("module", "svc.tasks"),
        ("module", "svc.cron.Settings"),
        ("module", "svc.dev:app"),
        ("script", "conf/gunicorn.py"),
        ("module", "svc.wsgi:application"),
    }


def test_interpreters_assignments_and_statement_breaks(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "supervisor/conf.d/tasks.conf",
        "[program:tasks]\ncommand=python -u -X dev -m svc.tasks\n",
    )
    _write(tmp_path, "Makefile", "PYTHON ?= python3\nrun:\n\t$(PYTHON) -m svc.make;\n")
    _write(
        tmp_path,
        "Dockerfile",
        'ENTRYPOINT ["python"]\nCMD ["-m", "svc.entry"]\n# CMD python -m svc.old\n'
        "RUN python -m pip install -e . \\\n    && python -c 'import x'\n",
    )
    _write(
        tmp_path,
        "compose.yaml",
        "services:\n  api:\n    command: uvicorn ${APP}\n    image: redis:alpine\n"
        "  web:\n    command: >\n      uvicorn\n      svc.folded:app\n",
    )
    _write(tmp_path, "run.sh", "python -OO scripts/run.py; taskiq worker -fsd svc.broker:b\n")

    assert _targets(tmp_path) == {
        ("module", "svc.tasks"),
        ("module", "svc.make"),
        ("module", "svc.entry"),
        ("module", "pip"),
        ("module", "svc.folded:app"),
        ("script", "scripts/run.py"),
        ("module", "svc.broker:b"),
        ("discovery", "tasks"),
    }


def test_logging_configurations_name_objects_and_ignored_files_add_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path, "logging.conf", "formatters:\n  json:\n    class: pkg.logs.Json\n")
    _write(tmp_path, "log.ini", "[formatter_json]\nclass=pkg.logs.Plain\n")
    _write(tmp_path, "svc/formats.json", '{"handler": {"()": "pkg.logs.make_handler"}}\n')
    _write(tmp_path, "run.sh", "uvicorn svc.main:app --log-config=./svc/formats.json\n")
    _write(tmp_path, "tests/fixtures/data.json", '{"class": "pkg.models.User"}\n')
    _write(tmp_path, "notes.txt", "uvicorn other.main:app\n")
    _write(tmp_path, "corpus/docker-compose.yml", "command: uvicorn excluded.main:app\n")
    _write(tmp_path, ".venv/pyvenv.cfg", "home = x\n")
    _write(tmp_path, ".venv/Dockerfile", "CMD uvicorn hidden.main:app\n")
    _write(tmp_path, "big/Dockerfile", "# " + "x" * 80 + "\nCMD uvicorn large.main:app\n")
    monkeypatch.setattr("deadtrace.deployment.MAX_DEPLOYMENT_FILE_BYTES", 70)

    assert _targets(tmp_path, ("corpus/**",)) == {
        ("object", "pkg.logs.Json"),
        ("object", "pkg.logs.Plain"),
        ("object", "pkg.logs.make_handler"),
        ("module", "svc.main:app"),
    }
    assert read_deployment_references(tmp_path / "missing") == ()

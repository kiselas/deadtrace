from __future__ import annotations

import asyncio
import sys
from importlib import import_module
from pathlib import Path

import httpx
import pytest


@pytest.mark.oracle
def test_reference_route_and_selected_providers(project_root: Path) -> None:
    fixture_root = project_root / "corpus" / "reference" / "fastapi_dishka_basic"
    sys.path.insert(0, str(fixture_root))
    try:
        main = import_module("app.main")
        domain = import_module("app.domain")
        domain.EVENTS.clear()

        async def exercise() -> httpx.Response:
            transport = httpx.ASGITransport(app=main.app)
            try:
                async with httpx.AsyncClient(
                    transport=transport, base_url="http://deadtrace.test"
                ) as client:
                    return await client.get("/dish")
            finally:
                await main.container.close()

        response = asyncio.run(exercise())

        assert response.status_code == 200
        assert response.json() == {"dish": "borsch"}
        assert domain.EVENTS == [
            "provider.repository",
            "provider.service",
            "service.get",
            "repository.load",
        ]
        assert "/dish" in main.app.openapi()["paths"]
    finally:
        sys.path.remove(str(fixture_root))
        for module_name in tuple(sys.modules):
            if module_name == "app" or module_name.startswith("app."):
                del sys.modules[module_name]

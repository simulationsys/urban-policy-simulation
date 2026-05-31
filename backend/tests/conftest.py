"""Test fixtures: a TestClient backed by a throwaway SQLite DB and a fast tick interval."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path) -> Iterator[TestClient]:
    # Configure settings via env BEFORE the app (and its cached settings) is built.
    os.environ["BACKEND_METADATA_DB_PATH"] = str(tmp_path / "meta.sqlite")
    os.environ["BACKEND_TICK_INTERVAL_SECONDS"] = "0.01"
    os.environ["BACKEND_SIM_ENGINE"] = "fake"

    from app.config import get_settings

    get_settings.cache_clear()

    from app.main import create_app

    app = create_app()
    with TestClient(app) as c:  # triggers lifespan startup/shutdown
        yield c


def make_scenario(client: TestClient, name: str = "scenario_a_monsoon") -> dict:
    resp = client.post(
        "/api/v1/scenarios",
        json={"config": {"name": name, "city": "delhi", "population": 1000, "seed": 7}},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()

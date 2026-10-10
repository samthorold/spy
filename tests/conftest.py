from pathlib import Path

import pytest
from starlette.testclient import TestClient

from main import app


@pytest.fixture(autouse=True)
def notebook_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """This test's own notebook file, named in `SPY_NOTEBOOK` the way a deployment names it.

    Autouse, so no test can reach the learner's real notebook.
    """
    path = tmp_path / "notebook.sqlite3"
    monkeypatch.setenv("SPY_NOTEBOOK", str(path))
    return path


@pytest.fixture
def client() -> TestClient:
    """A browser on the app as `uvicorn main:app` serves it."""
    return TestClient(app)

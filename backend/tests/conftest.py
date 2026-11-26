import json
from pathlib import Path

import pytest

from app.boostcamp import import_history
from app.db import connect, init_schema

FIXTURE = Path(__file__).parent / "fixtures" / "history_sample.json"


@pytest.fixture
def history() -> dict:
    return json.loads(FIXTURE.read_text())


@pytest.fixture
def conn(history):
    c = connect(":memory:")
    init_schema(c)
    import_history(c, history)
    yield c
    c.close()


def find_session(history: dict, day: str) -> dict:
    sessions = history["data"][day]
    assert len(sessions) == 1
    return sessions[0]

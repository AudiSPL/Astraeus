import copy

import pytest
from fastapi.testclient import TestClient

from app.main import app

DEFAULT_PROFILE = {
    "birth": {
        "date": "1984-07-24",
        "time": "05:10:00",
        "time_accuracy": "exact",
        "place_label": "Belgrade, Serbia",
    },
    "settings": {"zodiac": "tropical", "house_system": "placidus", "node_type": "true"},
}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def default_profile():
    return copy.deepcopy(DEFAULT_PROFILE)

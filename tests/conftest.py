import pytest
from fastapi.testclient import TestClient

from helpers import TODAY
from planner.app import create_app
from planner.config import Settings


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(Settings(), today=lambda: TODAY))

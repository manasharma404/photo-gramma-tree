"""Shared test setup: sign-in (auth/core.py) is off unless a test turns it on (tests/test_auth.py does)."""
import pytest


@pytest.fixture(autouse=True)
def _auth_off_by_default(monkeypatch):
    monkeypatch.setenv("VORTEX_AUTH", "off")

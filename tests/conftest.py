"""Shared pytest fixtures and configuration for all tests."""
import os
import pytest


@pytest.fixture(autouse=True)
def configure_testing_environment():
    """Configure environment variables for testing before app import."""
    os.environ['TESTING'] = '1'
    yield
    # Cleanup is optional since tests run in isolation


@pytest.fixture(autouse=True)
def disable_csrf(monkeypatch):
    """Disable CSRF protection for all tests."""
    from app import app
    app.config['WTF_CSRF_ENABLED'] = False
    yield

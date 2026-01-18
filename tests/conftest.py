"""Shared pytest fixtures and configuration for all tests."""
import os
import pytest


def pytest_configure(config):
    """Set TESTING environment variable before test collection."""
    os.environ['TESTING'] = '1'


@pytest.fixture(autouse=True)
def disable_csrf_and_rate_limiting():
    """Disable CSRF protection and rate limiting for all tests."""
    from app import app, limiter
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['RATELIMIT_ENABLED'] = False
    limiter.enabled = False
    yield
    limiter.enabled = True

"""Fixtures and utilities for tests."""

from datetime import datetime
from typing import Any, Dict

import pytest

# Constants for test data
TEST_SSL_EXPIRY_DATE = "2025-12-31T23:59:59.000Z"


@pytest.fixture
def sample_monitor_data() -> Dict[str, Any]:
    """Sample monitor data from UptimeRobot API."""
    return {
        "friendlyName": "Test Monitor",
        "type": "http",
        "url": "https://example.com",
        "status": "UP",
        "sslExpiryDateTime": TEST_SSL_EXPIRY_DATE,
    }


@pytest.fixture
def sample_api_response() -> Dict[str, Any]:
    """Sample API response from UptimeRobot."""
    return {
        "data": [
            {
                "friendlyName": "Test Monitor 1",
                "type": "http",
                "url": "https://example.com",
                "status": "UP",
                "sslExpiryDateTime": TEST_SSL_EXPIRY_DATE,
            },
            {
                "friendlyName": "Test Monitor 2",
                "type": "ping",
                "url": "1.1.1.1",
                "status": "DOWN",
                "sslExpiryDateTime": None,
            },
        ]
    }


@pytest.fixture
def sample_paginated_response() -> Dict[str, Any]:
    """Sample paginated API response."""
    return {
        "data": [
            {
                "friendlyName": "Test Monitor Page 1",
                "type": "http",
                "url": "https://page1.com",
                "status": "UP",
            }
        ],
        "nextLink": "https://api.uptimerobot.com/v3/monitors/?page=2",
    }


@pytest.fixture
def test_api_key() -> str:
    """Test API key."""
    return "ur12345-abcdef123456789"


@pytest.fixture
def invalid_datetime_string() -> str:
    """Invalid datetime string for testing."""
    return "invalid-datetime"


@pytest.fixture
def valid_datetime_string() -> str:
    """Valid datetime string for testing."""
    return TEST_SSL_EXPIRY_DATE


@pytest.fixture
def expected_timestamp() -> float:
    """Expected timestamp from valid datetime string."""
    dt = datetime.fromisoformat("2025-12-31T23:59:59.000+00:00")
    return dt.timestamp()

"""Tests for error handling and edge cases."""

from unittest.mock import MagicMock, patch

import pytest
import requests
import responses

from ws.prometheus_uptimerobot.web import (API_BASE_URL, UptimeRobotAPIError,
                                           UptimeRobotCollector, create_app,
                                           main)


class TestErrorHandling:
    """Test cases for error handling scenarios."""

    def test_uptimerobot_api_error_inheritance(self):
        """Test that UptimeRobotAPIError inherits from Exception."""
        error = UptimeRobotAPIError("Test error")
        assert isinstance(error, Exception)
        assert str(error) == "Test error"

    @responses.activate
    def test_api_timeout_handling(self, test_api_key):
        """Test handling of API timeout."""
        responses.add(
            responses.GET,
            f"{API_BASE_URL}/monitors/",
            body=requests.exceptions.Timeout("Request timed out"),
        )

        collector = UptimeRobotCollector(test_api_key, timeout=1)

        with pytest.raises(UptimeRobotAPIError, match="API request failed"):
            collector._get_paginated()

    @responses.activate
    def test_api_connection_error_handling(self, test_api_key):
        """Test handling of API connection error."""
        responses.add(
            responses.GET,
            f"{API_BASE_URL}/monitors/",
            body=requests.exceptions.ConnectionError("Connection failed"),
        )

        collector = UptimeRobotCollector(test_api_key)

        with pytest.raises(UptimeRobotAPIError, match="API request failed"):
            collector._get_paginated()

    @responses.activate
    def test_malformed_json_response(self, test_api_key):
        """Test handling of malformed JSON response."""
        responses.add(
            responses.GET,
            f"{API_BASE_URL}/monitors/",
            body="invalid json",
            status=200,
            content_type="application/json",
        )

        collector = UptimeRobotCollector(test_api_key)

        with pytest.raises(UptimeRobotAPIError):
            collector._get_paginated()

    def test_monitor_processing_with_malformed_data(self, test_api_key):
        """Test processing monitor with completely malformed data."""
        malformed_monitor = {
            "friendlyName": None,  # Should be string
            "type": 123,  # Should be string
            "url": [],  # Should be string
            "status": {},  # Should be string
        }

        collector = UptimeRobotCollector(test_api_key)
        metrics = {key: value.clone() for key, value in collector.metrics.items()}

        # Should not raise exception
        collector._process_monitor(malformed_monitor, metrics)

        # Should still create some metrics
        assert len(metrics["up"].samples) > 0

    def test_ssl_expiry_with_various_invalid_dates(self, test_api_key):
        """Test SSL expiry handling with various invalid date formats."""
        invalid_dates = [
            "not-a-date",
            "2025-13-01T25:00:00.000Z",  # Invalid month/hour
            "2025/12/31 23:59:59",  # Wrong format
            "",  # Empty string
            None,  # None value
        ]

        collector = UptimeRobotCollector(test_api_key)

        for invalid_date in invalid_dates:
            result = (
                collector._parse_iso_datetime(invalid_date) if invalid_date else None
            )
            if invalid_date:
                # Should return None for invalid dates
                assert result is None

    @responses.activate
    def test_pagination_with_broken_next_link(self, test_api_key):
        """Test pagination handling when next link is broken."""
        # First page with broken next link
        first_page = {
            "data": [{"friendlyName": "Monitor 1", "status": "UP"}],
            "nextLink": "https://broken-url-that-does-not-exist.com/monitors/?page=2",
        }

        responses.add(
            responses.GET, f"{API_BASE_URL}/monitors/", json=first_page, status=200
        )

        # Broken next link returns error
        responses.add(
            responses.GET,
            "https://broken-url-that-does-not-exist.com/monitors/?page=2",
            body=requests.exceptions.ConnectionError("Host not found"),
        )

        collector = UptimeRobotCollector(test_api_key)

        # Should raise UptimeRobotAPIError when next link fails
        with pytest.raises(UptimeRobotAPIError, match="API request failed"):
            collector._get_monitors()

    @responses.activate
    def test_collect_with_partial_monitor_failures(self, test_api_key):
        """Test collection when some monitors fail to process."""
        api_response = {
            "data": [
                {
                    "friendlyName": "Good Monitor",
                    "type": "http",
                    "url": "https://example.com",
                    "status": "UP",
                },
                {
                    # Missing required fields - will cause processing error
                    "friendlyName": "Bad Monitor"
                    # Missing type, url, status
                },
            ]
        }

        responses.add(
            responses.GET, f"{API_BASE_URL}/monitors/", json=api_response, status=200
        )

        collector = UptimeRobotCollector(test_api_key)

        # Should not raise exception despite partial failures
        metrics = collector.collect()
        assert len(metrics) == 4  # All metric types should be returned

    def test_flask_app_error_routes(self):
        """Test Flask app behavior with error conditions."""
        app = create_app()

        with app.test_client() as client:
            # Test non-existent route
            response = client.get("/nonexistent")
            assert response.status_code == 404

    @patch("ws.prometheus_uptimerobot.web.logger")
    def test_main_function_missing_api_key(self, mock_logger):
        """Test main function behavior when API key is missing."""
        with patch("ws.prometheus_uptimerobot.web.parse_arguments") as mock_parse:
            mock_parse.return_value = MagicMock(config=None)

            with patch.dict("os.environ", {}, clear=True):
                main()

                # Should log error about missing API key
                mock_logger.error.assert_called_with(
                    "UptimeRobot API key not found in environment or config file"
                )

    @patch("ws.prometheus_uptimerobot.web.logger")
    @patch("ws.prometheus_uptimerobot.web.create_app")
    def test_main_function_successful_startup(
        self, mock_create_app, mock_logger, test_api_key
    ):
        """Test main function successful startup."""
        mock_app = MagicMock()
        mock_create_app.return_value = mock_app

        with patch("ws.prometheus_uptimerobot.web.parse_arguments") as mock_parse:
            mock_parse.return_value = MagicMock(
                config=None, host="localhost", port=9429
            )

            with patch.dict("os.environ", {"UPTIMEROBOT_API_KEY": test_api_key}):
                main()

                # Should create app and run it
                mock_create_app.assert_called_once_with(test_api_key)
                mock_app.run.assert_called_once_with(host="localhost", port=9429)

                # Should log startup message
                mock_logger.info.assert_called_with("Starting server on localhost:9429")

    def test_edge_case_empty_api_response(self, test_api_key):
        """Test handling of completely empty API response."""
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                f"{API_BASE_URL}/monitors/",
                json={},  # Empty response without 'data' key
                status=200,
            )

            collector = UptimeRobotCollector(test_api_key)
            monitors = collector._get_monitors()

            # Should return empty list
            assert monitors == []

    def test_monitor_with_unicode_characters(self, test_api_key):
        """Test processing monitor with unicode characters."""
        unicode_monitor = {
            "friendlyName": "测试监控器 🚀",
            "type": "http",
            "url": "https://例え.テスト",
            "status": "UP",
        }

        collector = UptimeRobotCollector(test_api_key)
        metrics = {key: value.clone() for key, value in collector.metrics.items()}

        # Should handle unicode without issues
        collector._process_monitor(unicode_monitor, metrics)

        assert len(metrics["up"].samples) == 1
        labels = metrics["up"].samples[0].labels
        assert labels["monitor_name"] == "测试监控器 🚀"
        assert labels["monitor_url"] == "https://例え.テスト"

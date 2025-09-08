"""Tests for Flask web application."""

from unittest.mock import MagicMock, patch

import responses

from ws.prometheus_uptimerobot.web import API_BASE_URL, MIMETYPE_TEXT_PLAIN, create_app


class TestFlaskApp:
    """Test cases for Flask application."""

    def test_create_app(self):
        """Test app creation without API key."""
        app = create_app()
        assert app is not None
        assert "UPTIMEROBOT_API_KEY" not in app.config

    def test_create_app_with_api_key(self, test_api_key):
        """Test app creation with API key."""
        app = create_app(test_api_key)
        assert app.config["UPTIMEROBOT_API_KEY"] == test_api_key

    def test_health_endpoint(self):
        """Test health check endpoint."""
        app = create_app()
        with app.test_client() as client:
            response = client.get("/health")
            assert response.status_code == 200
            assert response.data == b"OK\n"
            assert response.mimetype == MIMETYPE_TEXT_PLAIN

    def test_metrics_endpoint_no_api_key(self):
        """Test metrics endpoint without API key."""
        app = create_app()
        with app.test_client() as client:
            response = client.get("/metrics")
            assert response.status_code == 500
            assert b"Error: UptimeRobot API key not configured" in response.data
            assert response.mimetype == MIMETYPE_TEXT_PLAIN

    @responses.activate
    def test_metrics_endpoint_success(self, test_api_key, sample_api_response):
        """Test successful metrics endpoint."""
        responses.add(
            responses.GET,
            f"{API_BASE_URL}/monitors/",
            json=sample_api_response,
            status=200,
        )

        app = create_app(test_api_key)
        with app.test_client() as client:
            response = client.get("/metrics")
            assert response.status_code == 200
            assert response.mimetype == MIMETYPE_TEXT_PLAIN

            # Check that Prometheus metrics are in the response
            response_text = response.data.decode("utf-8")
            assert "uptimerobot_up" in response_text
            assert "uptimerobot_status" in response_text
            assert "uptimerobot_scrape_duration_seconds" in response_text

    @responses.activate
    def test_metrics_endpoint_api_error(self, test_api_key):
        """Test metrics endpoint with API error."""
        responses.add(responses.GET, f"{API_BASE_URL}/monitors/", status=401)

        app = create_app(test_api_key)
        with app.test_client() as client:
            response = client.get("/metrics")
            assert response.status_code == 503
            assert b"UptimeRobot API Error" in response.data
            assert response.mimetype == MIMETYPE_TEXT_PLAIN

    @patch("ws.prometheus_uptimerobot.web.UptimeRobotCollector.configure")
    def test_metrics_endpoint_unexpected_error(self, mock_configure, test_api_key):
        """Test metrics endpoint with unexpected error."""
        mock_collector = MagicMock()
        mock_collector.collect.side_effect = Exception("Unexpected error")
        mock_configure.return_value = mock_collector

        app = create_app(test_api_key)
        with app.test_client() as client:
            response = client.get("/metrics")
            assert response.status_code == 500
            assert b"Error collecting metrics" in response.data
            assert b"Unexpected error" in response.data
            assert response.mimetype == MIMETYPE_TEXT_PLAIN

    def test_metrics_endpoint_with_labels(self, test_api_key):
        """Test that metrics contain proper labels."""
        sample_response = {
            "data": [
                {
                    "friendlyName": "Example Site",
                    "type": "http",
                    "url": "https://example.com",
                    "status": "UP",
                }
            ]
        }

        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                f"{API_BASE_URL}/monitors/",
                json=sample_response,
                status=200,
            )

            app = create_app(test_api_key)
            with app.test_client() as client:
                response = client.get("/metrics")
                assert response.status_code == 200

                response_text = response.data.decode("utf-8")
                # Check that labels are included
                assert 'monitor_name="Example Site"' in response_text
                assert 'monitor_type="http"' in response_text
                assert 'monitor_url="https://example.com"' in response_text
                assert 'monitor_paused="false"' in response_text

    @responses.activate
    def test_metrics_endpoint_multiple_monitors(
        self, test_api_key, sample_api_response
    ):
        """Test metrics endpoint with multiple monitors."""
        responses.add(
            responses.GET,
            f"{API_BASE_URL}/monitors/",
            json=sample_api_response,
            status=200,
        )

        app = create_app(test_api_key)
        with app.test_client() as client:
            response = client.get("/metrics")
            assert response.status_code == 200

            response_text = response.data.decode("utf-8")
            # Should have metrics for both monitors
            assert 'monitor_name="Test Monitor 1"' in response_text
            assert 'monitor_name="Test Monitor 2"' in response_text

    def test_app_routes_exist(self):
        """Test that required routes exist."""
        app = create_app()

        # Get all routes
        routes = [rule.rule for rule in app.url_map.iter_rules()]

        assert "/metrics" in routes
        assert "/health" in routes

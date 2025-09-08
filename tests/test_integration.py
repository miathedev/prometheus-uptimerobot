"""Integration tests for the complete application."""

import time

import pytest
import responses

from ws.prometheus_uptimerobot.web import API_BASE_URL, UptimeRobotCollector, create_app


class TestIntegration:
    """Integration tests for the complete UptimeRobot exporter."""

    @responses.activate
    def test_complete_metrics_flow(self, test_api_key):
        """Test the complete flow from API to Prometheus metrics."""
        # Mock the UptimeRobot API response
        api_response = {
            "data": [
                {
                    "friendlyName": "Production Website",
                    "type": "http",
                    "url": "https://example.com",
                    "status": "UP",
                    "sslExpiryDateTime": "2025-12-31T23:59:59.000Z",
                },
                {
                    "friendlyName": "API Endpoint",
                    "type": "http",
                    "url": "https://api.example.com",
                    "status": "DOWN",
                    "sslExpiryDateTime": None,
                },
                {
                    "friendlyName": "Database Server",
                    "type": "port",
                    "url": "db.example.com:5432",
                    "status": "PAUSED",
                    "sslExpiryDateTime": None,
                },
            ]
        }

        responses.add(
            responses.GET, f"{API_BASE_URL}/monitors/", json=api_response, status=200
        )

        # Create the Flask app
        app = create_app(test_api_key)

        with app.test_client() as client:
            # Test health endpoint
            health_response = client.get("/health")
            assert health_response.status_code == 200
            assert health_response.data == b"OK\n"

            # Test metrics endpoint
            metrics_response = client.get("/metrics")
            assert metrics_response.status_code == 200

            metrics_text = metrics_response.data.decode("utf-8")

            # Verify all expected metrics are present
            assert "uptimerobot_up" in metrics_text
            assert "uptimerobot_status" in metrics_text
            assert "uptimerobot_ssl_expire" in metrics_text
            assert "uptimerobot_scrape_duration_seconds" in metrics_text

            # Verify specific monitor data
            assert 'monitor_name="Production Website"' in metrics_text
            assert 'monitor_name="API Endpoint"' in metrics_text
            assert 'monitor_name="Database Server"' in metrics_text

            # Verify status values
            lines = metrics_text.split("\n")
            up_metrics = [line for line in lines if line.startswith("uptimerobot_up{")]

            # Should have one up metric per monitor
            assert len(up_metrics) == 3

            # Check specific status values
            production_up = [
                line for line in up_metrics if "Production Website" in line
            ][0]
            assert production_up.endswith(" 1.0")  # UP

            api_up = [line for line in up_metrics if "API Endpoint" in line][0]
            assert api_up.endswith(" 0.0")  # DOWN

            db_up = [line for line in up_metrics if "Database Server" in line][0]
            assert db_up.endswith(" 0.0")  # PAUSED (treated as down)

            # Verify paused label
            assert 'monitor_paused="true"' in metrics_text  # Database server
            assert 'monitor_paused="false"' in metrics_text  # Production and API

    @responses.activate
    def test_collector_standalone(self, test_api_key):
        """Test the collector can be used standalone without Flask."""
        api_response = {
            "data": [
                {
                    "friendlyName": "Standalone Test",
                    "type": "http",
                    "url": "https://standalone.example.com",
                    "status": "UP",
                }
            ]
        }

        responses.add(
            responses.GET, f"{API_BASE_URL}/monitors/", json=api_response, status=200
        )

        # Use collector directly
        collector = UptimeRobotCollector.configure(test_api_key)

        start_time = time.time()
        metrics = collector.collect()
        collection_time = time.time() - start_time

        # Should have all 5 metric types
        assert len(metrics) == 4

        # Find the scrape duration metric
        scrape_metric = next(
            m for m in metrics if m.name.endswith("scrape_duration_seconds")
        )
        assert len(scrape_metric.samples) == 1
        # Allow small margin
        assert scrape_metric.samples[0].value <= collection_time + 0.1

        # Find the up metric
        up_metric = next(m for m in metrics if m.name.endswith("_up"))
        assert len(up_metric.samples) == 1
        assert abs(up_metric.samples[0].value - 1.0) < 1e-10
        assert up_metric.samples[0].labels["monitor_name"] == "Standalone Test"

    @responses.activate
    def test_error_recovery(self, test_api_key):
        """Test that the application handles and recovers from errors."""
        # First request fails
        responses.add(responses.GET, f"{API_BASE_URL}/monitors/", status=500)

        app = create_app(test_api_key)

        with app.test_client() as client:
            # First request should return error
            response = client.get("/metrics")
            assert response.status_code == 503
            assert b"UptimeRobot API Error" in response.data

            # Health endpoint should still work
            health_response = client.get("/health")
            assert health_response.status_code == 200

        # Clear responses and add successful response
        responses.reset()
        responses.add(
            responses.GET,
            f"{API_BASE_URL}/monitors/",
            json={"data": [{"friendlyName": "Recovery Test", "status": "UP"}]},
            status=200,
        )

        with app.test_client() as client:
            # Second request should succeed
            response = client.get("/metrics")
            assert response.status_code == 200
            assert b"uptimerobot_up" in response.data
            assert b"Recovery Test" in response.data

    def test_configuration_priority(self):
        """Test that configuration priority works correctly."""
        import os
        from configparser import ConfigParser
        from unittest.mock import patch

        from ws.prometheus_uptimerobot.web import get_api_key

        # Create config with API key
        config = ConfigParser()
        config.add_section("default")
        config.set("default", "api_key", "config-key")

        # Test environment variable takes priority
        with patch.dict(os.environ, {"UPTIMEROBOT_API_KEY": "env-key"}):
            api_key = get_api_key(config)
            assert api_key == "env-key"

        # Test config file fallback
        with patch.dict(os.environ, {}, clear=True):
            api_key = get_api_key(config)
            assert api_key == "config-key"

        # Test no source
        with patch.dict(os.environ, {}, clear=True):
            api_key = get_api_key(None)
            assert api_key is None

    @pytest.mark.slow
    @responses.activate
    def test_pagination_performance(self, test_api_key):
        """Test that pagination works efficiently with large datasets."""
        # Simulate large dataset with pagination
        page1_response = {
            "data": [
                {
                    "friendlyName": f"Monitor {i}",
                    "type": "http",
                    "url": f"https://example{i}.com",
                    "status": "UP",
                }
                for i in range(50)  # 50 monitors on first page
            ],
            "nextLink": f"{API_BASE_URL}/monitors/?page=2",
        }

        page2_response = {
            "data": [
                {
                    "friendlyName": f"Monitor {i}",
                    "type": "http",
                    "url": f"https://example{i}.com",
                    "status": "UP",
                }
                for i in range(50, 75)  # 25 monitors on second page
            ]
        }

        responses.add(
            responses.GET, f"{API_BASE_URL}/monitors/", json=page1_response, status=200
        )

        responses.add(
            responses.GET,
            f"{API_BASE_URL}/monitors/?page=2",
            json=page2_response,
            status=200,
        )

        collector = UptimeRobotCollector.configure(test_api_key)

        start_time = time.time()
        monitors = collector._get_monitors()
        collection_time = time.time() - start_time

        # Should have collected all monitors
        assert len(monitors) == 75

        # Should be reasonably fast (less than 1 second for mocked requests)
        assert collection_time < 1.0

        # Verify we made the expected API calls
        assert len(responses.calls) == 2
        assert responses.calls[0].request.url == f"{API_BASE_URL}/monitors/"
        assert responses.calls[1].request.url == f"{API_BASE_URL}/monitors/?page=2"

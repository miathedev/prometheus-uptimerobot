"""UptimeRobot Prometheus Exporter.

A Flask application that exports UptimeRobot monitor metrics in Prometheus format.
"""

import argparse
import logging
import os
import traceback
from configparser import ConfigParser
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Union

import requests
from flask import Flask, Response
from prometheus_client import CollectorRegistry, core, generate_latest
from prometheus_client.metrics_core import Metric
from prometheus_client.registry import Collector

# Constants
API_BASE_URL = "https://api.uptimerobot.com/v3"
DEFAULT_HOST = os.environ.get("UPTIMEROBOT_HOST", "127.0.0.1")
DEFAULT_PORT = 9429
LOG_FORMAT = "%(asctime)s %(levelname)-5.5s [%(name)s] %(message)s"
NAMESPACE = "uptimerobot"
MIMETYPE_TEXT_PLAIN = "text/plain"

# Configure logging
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)


class UptimeRobotAPIError(Exception):
    """Exception raised for UptimeRobot API errors."""

    pass


class PrometheusGauge(core.GaugeMetricFamily):
    """Custom Gauge metric family with namespace support."""

    def __init__(
        self, name: str, documentation: str, namespace: str = NAMESPACE
    ) -> None:
        """Initialize a new gauge metric.

        Args:
            name: The metric name (without namespace)
            documentation: Description of the metric
            namespace: Metric namespace (default: uptimerobot)
        """
        super().__init__(f"{namespace}_{name}", documentation)
        self._name = name
        self._namespace = namespace

    def __call__(
        self, value: Union[int, float], labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Add a sample to the metric.

        Args:
            value: The metric value
            labels: Optional labels for the metric
        """
        if labels is None:
            labels = {}
        self.samples.append(core.Sample(self.name, labels, value))

    def clone(self) -> "PrometheusGauge":
        """Create a clone of this gauge."""
        return type(self)(self._name, self.documentation, self._namespace)


class UptimeRobotCollector(Collector):
    """Prometheus collector for UptimeRobot metrics."""

    STATUS_UP = "UP"
    STATUS_DOWN = "DOWN"
    STATUS_PAUSED = "PAUSED"

    def __init__(self, api_key: str, timeout: int = 30) -> None:
        """Initialize the collector.

        Args:
            api_key: UptimeRobot API key
            timeout: Request timeout in seconds

        Raises:
            ValueError: If API key is empty
            TypeError: If API key is not a string
        """
        if not api_key:
            raise ValueError("API key is required")
        if not isinstance(api_key, str):
            raise TypeError("API key must be a string")
        if timeout <= 0:
            raise ValueError("Timeout must be positive")

        self.api_key = api_key
        self.timeout = timeout
        # Cache metrics to ensure consistency
        self._metrics = {
            "up": PrometheusGauge("up", "Is the monitor up?"),
            "status": PrometheusGauge("status", "Numeric status of the monitor"),
            "ssl_expire": PrometheusGauge("ssl_expire", "Date of cert expiration"),
            "scrape_duration_seconds": PrometheusGauge(
                "scrape_duration_seconds", "Duration of uptimerobot.com scrape"
            ),
        }

    @staticmethod
    def _parse_iso_datetime(iso_string: str) -> Optional[float]:
        """Convert ISO datetime string to Unix timestamp.

        Args:
            iso_string: ISO 8601 formatted datetime string

        Returns:
            Unix timestamp or None if parsing fails
        """
        if not iso_string:
            return None

        try:
            # Parse ISO 8601 format: 2025-11-28T21:31:54.000Z
            dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
            return dt.timestamp()
        except (ValueError, AttributeError) as e:
            logger.error(f"Failed to parse datetime '{iso_string}': {e}")
            return None

    @classmethod
    def configure(cls, api_key: str, timeout: int = 30) -> "UptimeRobotCollector":
        """Factory method to create a configured collector.

        Args:
            api_key: UptimeRobot API key
            timeout: Request timeout in seconds

        Returns:
            Configured UptimeRobotCollector instance
        """
        return cls(api_key, timeout)

    @property
    def metrics(self) -> Dict[str, PrometheusGauge]:
        """Define available metrics."""
        return self._metrics

    def describe(self) -> List[PrometheusGauge]:
        """Return metric descriptions."""
        return list(self.metrics.values())

    def collect(self) -> Iterable[Metric]:
        """Collect and return all metrics.

        This method fetches data from UptimeRobot API and updates metrics.

        Returns:
            List of configured PrometheusGauge instances.
        """
        start_time = datetime.now()
        try:
            # Get fresh metrics dictionary
            metrics = self.metrics

            # Fetch monitors and update metrics
            monitors = self._get_monitors()
            for monitor in monitors:
                self._process_monitor(monitor, metrics)

            # Record scrape duration
            duration = (datetime.now() - start_time).total_seconds()
            metrics["scrape_duration_seconds"](duration, {})

        except UptimeRobotAPIError:
            # Re-raise API errors to be handled by the web app
            raise
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")

        return list(self.metrics.values())

    def _process_monitor(
        self, monitor: Dict[str, Any], metrics: Dict[str, PrometheusGauge]
    ) -> None:
        """Process a single monitor and update metrics.

        Args:
            monitor: Monitor data from API
            metrics: Dictionary of metric collectors
        """
        try:
            status = monitor.get("status")
            labels = {
                "monitor_name": monitor.get("friendlyName", ""),
                "monitor_type": monitor.get("type", ""),
                "monitor_url": monitor.get("url", ""),
                "monitor_paused": "true" if status == self.STATUS_PAUSED else "false",
            }

            # Set monitor up/down status
            is_up = status == self.STATUS_UP
            metrics["up"](1 if is_up else 0, labels)

            # Set numeric status
            status_value = 1 if is_up else 0
            metrics["status"](status_value, labels)

            # Handle SSL expiry date
            ssl_info = monitor.get("sslExpiryDateTime")
            if ssl_info:
                ssl_timestamp = self._parse_iso_datetime(ssl_info)
                if ssl_timestamp is not None:
                    metrics["ssl_expire"](ssl_timestamp, labels)

        except Exception as e:
            logger.error(
                f"Error processing monitor {monitor.get('friendlyName', 'unknown')}: {e}"
            )

    def _get_monitors(self) -> List[Dict[str, Any]]:
        """Fetch all monitors from UptimeRobot API with pagination.

        Returns:
            List of monitor data dictionaries

        Raises:
            UptimeRobotAPIError: If API request fails
        """
        monitors = []
        response = self._get_paginated()
        if response:
            monitors.extend(response.get("data", []))

            page_count = 0
            while "nextLink" in response and response.get("nextLink"):
                response = self._get_paginated(response["nextLink"])
                if response:
                    monitors.extend(response.get("data", []))
                    page_count += 1
                    logger.info(
                        f"Fetched page {page_count} with {len(response.get('data', []))} monitors"
                    )
                else:
                    break

        logger.info(f"Fetched {len(monitors)} total monitors")
        return monitors

    def _get_paginated(
        self, next_link: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Fetch a page of monitors from the API.

        Args:
            next_link: URL for next page, if None uses base URL

        Returns:
            API response data or None if request fails

        Raises:
            UptimeRobotAPIError: If API request fails
        """
        url = next_link if next_link else f"{API_BASE_URL}/monitors/"
        headers = {
            "accept": "application/json",
            "authorization": f"Bearer {self.api_key}",
        }

        try:
            response = requests.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            logger.error(f"Failed to fetch monitors from {url}: {e}")
            raise UptimeRobotAPIError(f"API request failed: {e}") from e


def create_app(api_key: Optional[str] = None) -> Flask:
    """Create and configure Flask application.

    Args:
        api_key: Optional API key to configure the app with

    Returns:
        Configured Flask application
    """
    app = Flask(__name__)

    if api_key:
        app.config["UPTIMEROBOT_API_KEY"] = api_key

    @app.route("/metrics")
    def metrics() -> Response:
        """Endpoint to serve Prometheus metrics.

        Returns:
            Response with metrics in Prometheus format or error message
        """
        try:
            configured_api_key = app.config.get("UPTIMEROBOT_API_KEY")
            if not configured_api_key:
                return Response(
                    "# Error: UptimeRobot API key not configured\n",
                    mimetype=MIMETYPE_TEXT_PLAIN,
                    status=500,
                )

            collector = UptimeRobotCollector.configure(configured_api_key)

            registry = CollectorRegistry(auto_describe=True)
            registry.register(collector)
            data = generate_latest(registry)

            return Response(data, mimetype=MIMETYPE_TEXT_PLAIN)

        except UptimeRobotAPIError as e:
            logger.error(f"UptimeRobot API error: {e}")
            return Response(
                f"# UptimeRobot API Error: {e}\n",
                mimetype=MIMETYPE_TEXT_PLAIN,
                status=503,
            )
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            trace = traceback.format_exc()
            return Response(
                f"# Error collecting metrics\n{trace}",
                mimetype=MIMETYPE_TEXT_PLAIN,
                status=500,
            )

    @app.route("/health")
    def health() -> Response:
        """Health check endpoint.

        Returns:
            Simple health check response
        """
        return Response("OK\n", mimetype=MIMETYPE_TEXT_PLAIN)

    return app


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed command line arguments
    """
    parser = argparse.ArgumentParser(description="UptimeRobot Prometheus Exporter")
    parser.add_argument(
        "--host", default=DEFAULT_HOST, help=f"Bind host (default: {DEFAULT_HOST})"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Bind port (default: {DEFAULT_PORT})",
    )
    parser.add_argument("--config", help="Path to the configuration file")
    return parser.parse_args()


def load_config(config_path: str) -> Optional[ConfigParser]:
    """Load configuration from file.

    Args:
        config_path: Path to the configuration file

    Returns:
        ConfigParser instance or None if loading fails
    """
    try:
        config = ConfigParser()
        config.read(os.path.expanduser(config_path))
        return config
    except Exception as e:
        logger.error(f"Failed to read configuration file: {e}")
        return None


def get_api_key(config: Optional[ConfigParser]) -> Optional[str]:
    """Get API key from environment or config file.

    Args:
        config: Optional ConfigParser instance

    Returns:
        API key string or None if not found
    """
    # Try environment variable first
    api_key = os.environ.get("UPTIMEROBOT_API_KEY")
    if api_key:
        return api_key

    # Try config file
    if config:
        try:
            return config.get("default", "api_key")
        except Exception as e:
            logger.warning(f"Failed to get api_key from config: {e}")

    return None


def serve() -> None:
    """Entry point for serving the application."""
    main()


def cgi() -> None:
    """Entry point for CGI deployment."""
    # For CGI deployment, we'd need to handle the request differently
    # This is a placeholder for now
    raise NotImplementedError("CGI deployment not yet implemented")


def main() -> None:
    """Main entry point for the application."""
    options = parse_arguments()

    # Load configuration if specified
    config = None
    if options.config:
        config = load_config(options.config)

    # Get API key
    api_key = get_api_key(config)
    if not api_key:
        logger.error("UptimeRobot API key not found in environment or config file")
        return

    # Create and configure Flask app
    app = create_app(api_key)

    logger.info(f"Starting server on {options.host}:{options.port}")
    app.run(host=options.host, port=options.port)


if __name__ == "__main__":
    main()

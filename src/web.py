from configparser import ConfigParser
import os
import argparse
import requests
import time
from prometheus_client import core, generate_latest
from flask import Flask, Response

# Import Flask logging
import logging

log = logging.getLogger("werkzeug")
LOG_FORMAT = "%(asctime)s %(levelname)-5.5s [%(name)s] %(message)s"

app = Flask(__name__)


class Gauge(core.GaugeMetricFamily):
    NAMESPACE = "uptimerobot"

    def __init__(self, name, documentation):
        super().__init__("%s_%s" % (self.NAMESPACE, name), documentation)
        self._name = name

    def __call__(self, value, labels=None):
        if labels is None:
            labels = {}
        self.samples.append(core.Sample(self.name, labels, value))

    def clone(self):
        return type(self)(self._name, self.documentation)


class UptimeRobotCollector:
    API_URL = "https://api.uptimerobot.com/v2"
    STATUS_UP = 2
    MONITOR_TYPES = {1: "http", 2: "http keyword", 3: "ping", 4: "port"}
    STATUS_TYPES = {
        0: "paused",
        1: "not checked yet",
        2: "up",
    }

    def __init__(self, api_key):
        self.api_key = api_key

    @staticmethod
    def configure(api_key):
        return UptimeRobotCollector(api_key)

    METRICS = {
        "up": Gauge("up", "Is the monitor up?"),
        "status": Gauge("status", "Numeric status of the monitor"),
        "responsetime": Gauge("responsetime", "Most recent monitor responsetime"),
        "ssl_expire": Gauge("ssl_expire", "Date of cert expiration"),
        "scrape_duration_seconds": Gauge(
            "scrape_duration_seconds", "Duration of uptimerobot.com scrape"
        ),
    }

    def describe(self):
        return self.METRICS.values()

    def collect(self):
        try:
            start = time.time()
            metrics = {key: value.clone() for key, value in self.METRICS.items()}
            monitors = self._get_monitors()
            for monitor in monitors:
                try:
                    status = monitor.get("status", 1)
                    labels = {
                        "monitor_name": monitor["friendly_name"],
                        "monitor_type": self.MONITOR_TYPES[monitor["type"]],
                        "monitor_url": monitor["url"],
                        "monitor_paused": "true" if status == 0 else "false",
                    }

                    # metrics['paused'] = status == 0
                    metrics["up"](int(status == self.STATUS_UP), labels)
                    metrics["status"](status, labels)
                    if "response_times" in monitor and monitor["response_times"]:
                        responsetime = monitor.get("response_times", [{}])[0].get(
                            "value"
                        )
                        if responsetime is not None:
                            metrics["responsetime"](responsetime, labels)
                    ssl_info = monitor.get("attributes", {}).get(
                        "ssl_status_expiration_date_int"
                    )
                    if ssl_info:
                        metrics["ssl_expire"](ssl_info, labels)
                except Exception as e:
                    log.error(
                        f"Error processing monitor {monitor['friendly_name']}: {e}"
                    )

            # Adding scrape duration metric
            metrics["scrape_duration_seconds"](time.time() - start)

            return list(metrics.values())

        except Exception as e:
            log.error(f"Error collecting data from UptimeRobot: {e}")
            raise e

    def _get_monitors(self):
        result = []
        response = self._get_paginated(0)
        result.extend(response.get("monitors", ()))
        seen = response["pagination"]["limit"]
        while response["pagination"]["total"] > seen:
            response = self._get_paginated(seen)
            result.extend(response.get("monitors", ()))
            seen += response["pagination"]["limit"]
        return result

    def _get_paginated(self, offset):
        return requests.post(
            self.API_URL + "/getMonitors",
            data={
                "api_key": self.api_key,
                "format": "json",
                "offset": offset,
                "response_times": "1",  # enable
                # BROKEN            'response_times_limit': '1',  # just the latest one
            },
        ).json()


@app.route("/metrics")
def metrics():
    collector = UptimeRobotCollector.configure(
        api_key=app.config["UPTIMEROBOT_API_KEY"]
    )
    try:
        registry = core.CollectorRegistry(auto_describe=True)
        registry.register(collector)
        data = generate_latest(registry)

        return Response(data, mimetype="text/plain")

    except Exception as e:
        log.error(f"Error collecting metrics: {e}")


def main():
    parser = argparse.ArgumentParser(description="Uptime Robot Metrics Exporter")
    parser.add_argument(
        "--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=9429, help="Bind port (default: 9429)"
    )
    parser.add_argument(
        "--config", required=False, help="Path to the configuration file"
    )
    options = parser.parse_args()

    if options.config:
        try:
            config = ConfigParser()
            config.read(os.path.expanduser(options.config))
            get = lambda x: config.get("default", x)  # noqa
        except ConfigParser.Error as e:
            log.error(f"Failed to read configuration file: {str(e)}")

    api_key = os.environ.get("UPTIMEROBOT_API_KEY") or (
        get("api_key") if "config" in locals() else None
    )

    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    app.config["UPTIMEROBOT_API_KEY"] = api_key

    log.info(f"Starting server on {options.host}:{options.port}")
    app.run(host=options.host, port=options.port)


if __name__ == "__main__":
    main()

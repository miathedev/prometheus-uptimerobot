======================================
prometheus metrics for uptimerobot.com
======================================

This package exports `Uptime Robot`_ monitor results as `Prometheus`_ metrics.
The exporter is built with Python 3.7+ support and follows modern Python best practices
including type hints, proper error handling, and comprehensive logging.

.. _`Uptime Robot`: https://uptimerobot.com
.. _`Prometheus`: https://prometheus.io


Features
========

* **API Key Security**: Supports both environment variables and config files
* **Pagination Support**: Handles large numbers of monitors automatically
* **SSL Certificate Monitoring**: Tracks SSL certificate expiration dates
* **Docker Ready**: Easy deployment with Docker containers


Usage
=====

Installation
------------

1. Clone the repository::

    git clone https://github.com/miathedev/prometheus-uptimerobot.git
    cd prometheus-uptimerobot

2. Create a virtual environment and install dependencies::

    python -m venv env
    source env/bin/activate  # On Windows: env\Scripts\activate
    pip install -r requirements.txt

Configure API Key
-----------------

**Option 1: Environment Variable (Recommended)**

Set your UptimeRobot API key as an environment variable::

    export UPTIMEROBOT_API_KEY=ur12345-abcdef123456789

**Option 2: Configuration File**

Create a configuration file ``config.ini``::

    [default]
    api_key = ur12345-abcdef123456789

.. warning::
   Never commit your API key to version control. Add ``config.ini`` to your ``.gitignore`` file.

Get your API key from the `Uptime Robot API documentation`_.

Run the Exporter
----------------

**Using Environment Variable:**

.. code-block:: bash

    python src/ws/prometheus_uptimerobot/web.py --host 0.0.0.0 --port 9429

**Using Configuration File:**

.. code-block:: bash

    python src/ws/prometheus_uptimerobot/web.py --config config.ini --host 0.0.0.0 --port 9429

**Command Line Options:**

* ``--host``: Bind host (default: 0.0.0.0)
* ``--port``: Bind port (default: 9429)  
* ``--config``: Path to configuration file (optional if using environment variable)


Ready-to-Use Docker Images
--------------------------

Pre-built images are available on GitHub Container Registry. You can pull and run the latest build directly:

.. code-block:: bash

  docker pull ghcr.io/miathedev/prometheus-uptimerobot:main
  docker run --rm -p 9429:9429 \
    -e UPTIMEROBOT_API_KEY=ur12345-abcdef123456789 \
    ghcr.io/miathedev/prometheus-uptimerobot:main

You can also use a config file with the pre-built image:

.. code-block:: bash

  docker run --rm -p 9429:9429 \
    -v /path/to/config.ini:/config.ini \
    ghcr.io/miathedev/prometheus-uptimerobot:main \
    python src/ws/prometheus_uptimerobot/web.py --config /config.ini

=================

Build and Run with Config File
-------------------------------

.. code-block:: bash

    # Build the Docker image
    docker build -t uptimerobot-exporter .
    
    # Run with config file
    docker run --rm -p 9429:9429 \
        -v /path/to/config.ini:/config.ini \
        uptimerobot-exporter \
        python src/ws/prometheus_uptimerobot/web.py --config /config.ini

Run with Environment Variable
-----------------------------

.. code-block:: bash

    # Run with environment variable (recommended)
    docker run --rm -p 9429:9429 \
        -e UPTIMEROBOT_API_KEY=ur12345-abcdef123456789 \
        uptimerobot-exporter \
        python src/ws/prometheus_uptimerobot/web.py

Docker Compose
--------------

Create a ``docker-compose.yml`` file::

    version: '3.8'
    services:
      uptimerobot-exporter:
        build: .
        ports:
          - "9429:9429"
        environment:
          - UPTIMEROBOT_API_KEY=ur12345-abcdef123456789
        restart: unless-stopped

Then run::

    docker-compose up -d

Prometheus Configuration
========================

Add the following to your ``prometheus.yml`` configuration::

    scrape_configs:
      - job_name: 'uptimerobot'
        scrape_interval: 300s  # 5 minutes (recommended to avoid API rate limits)
        scrape_timeout: 30s
        static_configs:
          - targets: ['localhost:9429']
        metrics_path: /metrics

For multiple instances or dynamic discovery, you can use service discovery::

    scrape_configs:
      - job_name: 'uptimerobot'
        scrape_interval: 300s
        dns_sd_configs:
          - names:
            - 'uptimerobot-exporter.example.com'
            type: 'A'
            port: 9429

Exported Metrics
================

The exporter provides the following metrics, each labeled with monitor information:

**Labels Applied to All Metrics:**

* ``monitor_name``: Friendly name of the monitor (e.g., "example.com")
* ``monitor_type``: Type of monitor (e.g., "http", "ping", "port") 
* ``monitor_url``: URL being monitored
* ``monitor_paused``: "true" if monitor is paused, "false" otherwise

**Available Metrics:**

* ``uptimerobot_up`` (gauge): Monitor status (1=up, 0=down)
* ``uptimerobot_status`` (gauge): Numeric status code from UptimeRobot API
* ``uptimerobot_ssl_expire`` (gauge): SSL certificate expiration as Unix timestamp (when applicable)
* ``uptimerobot_scrape_duration_seconds`` (gauge): Time taken to collect all metrics

**Example Prometheus Queries:**

.. code-block:: promql

    # Monitors that are down
    uptimerobot_up == 0
    
    # SSL certificates expiring in 30 days
    (uptimerobot_ssl_expire - time()) / 86400 < 30

Monitoring and Alerting
=======================

**Sample Alerting Rules:**

.. code-block:: yaml

    groups:
      - name: uptimerobot
        rules:
          - alert: MonitorDown
            expr: uptimerobot_up == 0
            for: 5m
            labels:
              severity: critical
            annotations:
              summary: "Monitor {{ $labels.monitor_name }} is down"
              description: "Monitor {{ $labels.monitor_name }} ({{ $labels.monitor_url }}) has been down for more than 5 minutes."
          
          - alert: SSLCertificateExpiringSoon
            expr: (uptimerobot_ssl_expire - time()) / 86400 < 30
            for: 1h
            labels:
              severity: warning
            annotations:
              summary: "SSL certificate for {{ $labels.monitor_name }} expires soon"
              description: "SSL certificate for {{ $labels.monitor_url }} will expire in {{ $value }} days."

Troubleshooting
===============

**Common Issues:**

1. **API Key Issues:**
   
   * Verify your API key is correct and has proper permissions
   * Check the UptimeRobot API documentation for current key format
   * Ensure the key is properly set in environment or config file

2. **Network Issues:**
   
   * Verify connectivity to ``api.uptimerobot.com``
   * Check firewall rules if running in restricted environments
   * Monitor logs for HTTP errors and timeouts

3. **Performance Issues or missing monitors:**
   
   * Increase scrape intervals if you have many monitors
   * Monitor the ``uptimerobot_scrape_duration_seconds`` metric
   * Consider API rate limits (UptimeRobot allows 10 requests per minute)

**Logging:**

The application provides comprehensive logging. To increase log level::

    import logging
    logging.getLogger().setLevel(logging.DEBUG)

**Health Check:**

Verify the exporter is working::

    curl http://localhost:9429/metrics

API Documentation
=================

For detailed information about UptimeRobot API endpoints, status codes, and monitor types, 
see the official `Uptime Robot API documentation <https://uptimerobot.com/api/v3/#get-/monitors>`_.

**Status Values:**

* ``UP``: Monitor is responding normally
* ``DOWN``: Monitor is not responding  
* ``PAUSED``: Monitor is temporarily paused

**Monitor Types:**

* ``http``: HTTP(s) monitoring
* ``keyword``: HTTP(s) with keyword monitoring
* ``ping``: Ping monitoring
* ``port``: Port monitoring

Contributing
============

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure code follows Python best practices
5. Submit a pull request

Development Setup
-----------------

.. code-block:: bash

    # Clone and setup development environment
    git clone https://github.com/miathedev/prometheus-uptimerobot.git
    cd prometheus-uptimerobot
    python -m venv env
    source env/bin/activate
    pip install -r requirements.txt
    
    # Run tests (if available)
    make test
    
    # Run with development config
    make run

License
=======

This project is licensed under the BSD-3-Clause License.

.. _`Uptime Robot API documentation`: https://uptimerobot.com/api

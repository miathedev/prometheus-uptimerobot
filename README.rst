======================================
prometheus metrics for uptimerobot.com
======================================

This packages exports `Uptime Robot`_ monitor results as `Prometheus`_ metrics.

.. _`Uptime Robot`: https://uptimerobot.com
.. _`Prometheus`: https://prometheus.io


Usage
=====

Configure API key
-----------------

You'll need to provide the API key of your uptimerobot.com account using a
configuration file::

    [default]
    api_key = 123456789

See the `Uptime Robot API documentation`_ for details.


Set up as docker container
-------------------

You can run the exporter as a docker container.
Either use a config file:

.. code-block:: bash
    $ docker build -t uptimerobot_exporter .
    $ docker run --rm -p 9429:9429 -v /path/to/config.ini:/config.ini uptimerobot_exporter uptime_robot_exporter --config /config.ini

Or use environment variables:
.. code-block:: bash
    $ docker run --rm -p 9429:9429 -e UPTIMEROBOT_API_KEY=123456789 uptimerobot_exporter uptime_robot_exporter

Configure Prometheus
--------------------

::

    scrape_configs:
      - job_name: 'uptimerobot'
        scrape_interval: 300s
        static_configs:
          - targets: ['localhost:9429']

The following metrics are exported, each with labels ``{monitor_name="example.com",monitor_type="http",monitor_url="https://example.com"}``:

* ``uptimerobot_up`` gauge (1=up, 0=down)
* ``uptimerobot_status`` gauge
* ``uptimerobot_responsetime`` gauge
* ``uptimerobot_ssl_expire`` gauge (unix timestamp), if applicable

See the `Uptime Robot API documentation`_ section "Parameters" for details on
the possible ``status`` values. The ``monitor_type`` is translated from its
numeric code to one of ``http``, ``http keyword``, ``ping``, or ``port``.

Additionally, a ``uptimerobot_scrape_duration_seconds`` gauge is exported.


.. _`Uptime Robot API documentation`: https://uptimerobot.com/api

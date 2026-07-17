==========================
scrapy-prometheus-exporter
==========================

.. image:: https://img.shields.io/pypi/v/scrapy-prometheus-exporter.svg
   :target: https://pypi.org/project/scrapy-prometheus-exporter/
   :alt: PyPI version

.. image:: https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-blue.svg
   :target: https://pypi.org/project/scrapy-prometheus-exporter/
   :alt: Supported Python versions

.. image:: https://img.shields.io/badge/license-MIT-blue.svg
   :target: https://github.com/rangertaha/scrapy-prometheus-exporter/blob/master/LICENSE
   :alt: License: MIT

.. image:: https://github.com/rangertaha/scrapy-prometheus-exporter/actions/workflows/ci.yml/badge.svg
   :target: https://github.com/rangertaha/scrapy-prometheus-exporter/actions/workflows/ci.yml
   :alt: CI status

A Scrapy_ extension that exports crawler stats as Prometheus_ metrics. It
runs a small web server inside your crawl process and serves the standard
Prometheus text format at ``/metrics``, so you can scrape, alert on, and
graph your spiders (for example with Grafana).

.. _Scrapy: https://scrapy.org/
.. _Prometheus: https://prometheus.io/

Installation
============

Install scrapy-prometheus-exporter using ``pip``::

    $ pip install scrapy-prometheus-exporter

Usage
=====

Enable the extension in your project's ``settings.py``::

    EXTENSIONS = {
        'scrapy_prometheus_exporter.prometheus.WebService': 500,
    }

That's it. While the crawler runs, metrics are available at::

    http://0.0.0.0:9410/metrics

The extension is enabled by default (set `PROMETHEUS_ENABLED`_ to ``False``
to disable it) and listens on the port from `PROMETHEUS_PORT`_ (default
9410). Scrapy stats are copied into the Prometheus gauges every
`PROMETHEUS_UPDATE_INTERVAL`_ seconds.

Exposed metrics
===============

All metrics are gauges labelled with ``spider`` (the ``BOT_NAME``):

===========================================  ====================================================
Metric                                       Source / meaning
===========================================  ====================================================
``spr_items_scraped``                        Items scraped (``item_scraped`` signal)
``spr_items_dropped``                        Items dropped (``item_dropped`` signal)
``spr_response_received``                    Responses received (``response_received`` signal)
``spr_opened``                               Spider opened (``spider_opened`` signal)
``spr_closed``                               Spider closed; extra ``reason`` label
``spr_downloader_request_total``             ``downloader/request_count``
``spr_downloader_request``                   ``downloader/request_method_count/*``; ``method`` label
``spr_downloader_request_bytes``             ``downloader/request_bytes``
``spr_downloader_response``                  ``downloader/response_count``
``spr_downloader_response_status``           ``downloader/response_status_count/*``; ``code`` label
``spr_downloader_response_bytes``            ``downloader/response_bytes``
``spr_log``                                  ``log_count/*``; ``level`` label
``spr_duplicate_filtered``                   ``dupefilter/filtered``
``spr_memdebug_gc_garbage``                  ``memdebug/gc_garbage_count``
``spr_memdebug_live_refs``                   ``memdebug/live_refs/*``
``spr_memusage_max``                         ``memusage/max``
``spr_memusage_startup``                     ``memusage/startup``
``spr_scheduler_dequeued``                   ``scheduler/dequeued``
``spr_scheduler_enqueued``                   ``scheduler/enqueued``
``spr_scheduler_enqueued_memory``            ``scheduler/enqueued/memory``
``spr_scheduler_dequeued_memory``            ``scheduler/dequeued/memory``
``spr_offsite_domains``                      ``offsite/domains``
``spr_offsite_filtered``                     ``offsite/filtered``
``spr_request_depth``                        ``request_depth_count/*``
``spr_request_depth_max``                    ``request_depth_max``
===========================================  ====================================================

Settings
========

These are the settings that control the metrics exporter:

PROMETHEUS_ENABLED
------------------

Default: ``True``

A boolean which specifies if the exporter will be enabled (provided its
extension is also enabled).

PROMETHEUS_PORT
---------------

Default: ``[9410]``

The port to use for the web service. If set to ``None`` or ``0``, a
dynamically assigned port is used.

PROMETHEUS_HOST
---------------

Default: ``'0.0.0.0'``

The interface the web service should listen on.

PROMETHEUS_PATH
---------------

Default: ``'metrics'``

The url path to access exported metrics. Example::

    http://0.0.0.0:9410/metrics

PROMETHEUS_UPDATE_INTERVAL
--------------------------

Default: ``30``

This extension periodically collects stats for exporting. The interval in
seconds between metrics updates can be controlled with this setting.

Grafana dashboard
=================

An example Grafana dashboard built from these metrics is available in the
`grafana/ <grafana/>`_ directory.

.. image:: /grafana/grafana.png
   :height: 100px
   :width: 200 px
   :scale: 50 %
   :alt: Grafana dashboard of the exported data
   :align: center

Development
===========

Run the checks locally::

    $ pip install -e '.[test]'
    $ pytest
    $ ruff check . && ruff format --check .
    $ mypy

See `CHANGELOG.md <CHANGELOG.md>`_ for release history. Licensed under the
`MIT license <LICENSE>`_.

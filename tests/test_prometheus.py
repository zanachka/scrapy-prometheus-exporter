"""Tests for the scrapy-prometheus-exporter extension."""

from unittest.mock import Mock

import pytest
from prometheus_client import REGISTRY, generate_latest
from scrapy import Spider, signals
from scrapy.exceptions import DropItem, NotConfigured
from scrapy.settings import Settings
from scrapy.utils.test import get_crawler
from twisted.web.wsgi import WSGIResource

import scrapy_prometheus_exporter
from scrapy_prometheus_exporter.prometheus import WebService

BOT = "testbot"


def make_service(settings_dict=None):
    settings = {"BOT_NAME": BOT}
    settings.update(settings_dict or {})
    crawler = get_crawler(settings_dict=settings)
    return WebService.from_crawler(crawler)


def sample(name, labels=None):
    """Read a gauge value from the default registry (0 if never labelled)."""
    return REGISTRY.get_sample_value(name, labels or {"spider": BOT}) or 0


def test_import():
    assert WebService is not None


def test_version_is_exposed():
    assert scrapy_prometheus_exporter.__version__ == "1.0.2"


def test_settings_type():
    # Ensure the settings object is usable (guards the import surface).
    assert isinstance(Settings(), Settings)


def test_from_crawler_builds_webservice():
    service = make_service()
    assert service.name == BOT
    assert service.path == "metrics"
    assert service.host == "0.0.0.0"
    assert service.port == [9410]
    assert service.interval == 30


def test_custom_settings_are_honoured():
    service = make_service(
        {
            "PROMETHEUS_PORT": [9999],
            "PROMETHEUS_HOST": "127.0.0.1",
            "PROMETHEUS_PATH": "stats",
            "PROMETHEUS_UPDATE_INTERVAL": 5,
        }
    )
    assert service.port == [9999]
    assert service.host == "127.0.0.1"
    assert service.path == "stats"
    assert service.interval == 5


def test_disabled_raises_not_configured():
    crawler = get_crawler(settings_dict={"PROMETHEUS_ENABLED": False})
    with pytest.raises(NotConfigured):
        WebService.from_crawler(crawler)


def test_metrics_registered_in_default_registry():
    make_service()
    exposition = generate_latest(REGISTRY).decode()
    for metric in (
        "spr_items_scraped",
        "spr_items_dropped",
        "spr_response_received",
        "spr_opened",
        "spr_closed",
        "spr_downloader_request_total",
        "spr_downloader_response_status",
        "spr_log",
        "spr_scheduler_dequeued",
        "spr_request_depth_max",
    ):
        assert f"# HELP {metric} " in exposition, metric


def test_item_scraped_increments_scraped_counter():
    service = make_service()
    spider = Spider(name=BOT)
    service.item_scraped({"a": 1}, spider)
    service.item_scraped({"b": 2}, spider)
    assert sample("spr_items_scraped") == 2
    assert sample("spr_items_dropped") == 0


def test_item_dropped_increments_dropped_counter():
    """Regression test: item_dropped must increment spr_items_dropped,
    not spr_items_scraped."""
    service = make_service()
    spider = Spider(name=BOT)
    service.item_dropped({"a": 1}, spider, DropItem("bad item"))
    assert sample("spr_items_dropped") == 1
    assert sample("spr_items_scraped") == 0


def test_item_dropped_signal_dispatch():
    """The bug fix also holds when the signal is sent through Scrapy's
    signal manager, as during a real crawl."""
    settings = {"BOT_NAME": BOT}
    crawler = get_crawler(settings_dict=settings)
    # Keep a strong reference: the signal manager holds weak references.
    service = WebService.from_crawler(crawler)
    assert service is not None
    spider = Spider(name=BOT)
    crawler.signals.send_catch_log(
        signal=signals.item_dropped,
        item={"a": 1},
        response=None,
        exception=DropItem("bad item"),
        spider=spider,
    )
    assert sample("spr_items_dropped") == 1
    assert sample("spr_items_scraped") == 0


def test_response_received_increments():
    service = make_service()
    service.response_received(Spider(name=BOT))
    assert sample("spr_response_received") == 1


def test_spider_opened_and_closed_increment():
    service = make_service()
    spider = Spider(name=BOT)
    service.spider_opened(spider)
    service.spider_closed(spider, reason="finished")
    assert sample("spr_opened") == 1
    assert sample("spr_closed", {"spider": BOT, "reason": "finished"}) == 1


def test_update_maps_stats_to_gauges():
    service = make_service()
    stats = service.stats
    stats.set_value("downloader/request_count", 7)
    stats.set_value("downloader/request_bytes", 1024)
    stats.set_value("downloader/request_method_count/GET", 5)
    stats.set_value("downloader/response_count", 6)
    stats.set_value("downloader/response_bytes", 2048)
    stats.set_value("downloader/response_status_count/200", 4)
    stats.set_value("downloader/response_status_count/404", 2)
    stats.set_value("log_count/ERROR", 3)
    stats.set_value("dupefilter/filtered", 9)
    stats.set_value("memusage/max", 111)
    stats.set_value("memusage/startup", 100)
    stats.set_value("memdebug/gc_garbage_count", 5)
    stats.set_value("memdebug/live_refs/SomeSpider", 6)
    stats.set_value("scheduler/dequeued", 12)
    stats.set_value("scheduler/enqueued", 13)
    stats.set_value("scheduler/enqueued/memory", 21)
    stats.set_value("scheduler/dequeued/memory", 17)
    stats.set_value("offsite/domains", 2)
    stats.set_value("offsite/filtered", 8)
    stats.set_value("request_depth_max", 3)
    stats.set_value("request_depth_count/2", 4)

    service.update()

    assert sample("spr_downloader_request_total") == 7
    assert sample("spr_downloader_request_bytes") == 1024
    assert sample("spr_downloader_request", {"spider": BOT, "method": "GET"}) == 5
    assert sample("spr_downloader_response") == 6
    assert sample("spr_downloader_response_bytes") == 2048
    assert sample("spr_downloader_response_status", {"spider": BOT, "code": "200"}) == 4
    assert sample("spr_downloader_response_status", {"spider": BOT, "code": "404"}) == 2
    assert sample("spr_log", {"spider": BOT, "level": "ERROR"}) == 3
    assert sample("spr_duplicate_filtered") == 9
    assert sample("spr_memusage_max") == 111
    assert sample("spr_memusage_startup") == 100
    assert sample("spr_memdebug_gc_garbage") == 5
    assert sample("spr_memdebug_live_refs") == 6
    assert sample("spr_scheduler_dequeued") == 12
    assert sample("spr_scheduler_enqueued") == 13
    # Regression: enqueued/memory and dequeued/memory must land on DISTINCT
    # gauges; the dequeued value used to overwrite the enqueued gauge.
    assert sample("spr_scheduler_enqueued_memory") == 21
    assert sample("spr_scheduler_dequeued_memory") == 17
    assert sample("spr_offsite_domains") == 2
    assert sample("spr_offsite_filtered") == 8
    assert sample("spr_request_depth_max") == 3
    assert sample("spr_request_depth") == 4


def test_scheduler_memory_gauges_are_distinct():
    """Regression test: scheduler/dequeued/memory used to overwrite the
    spr_scheduler_enqueued_memory gauge instead of setting its own gauge."""
    service = make_service()
    service.stats.set_value("scheduler/enqueued/memory", 40)
    service.stats.set_value("scheduler/dequeued/memory", 30)
    service.update()
    assert sample("spr_scheduler_enqueued_memory") == 40
    assert sample("spr_scheduler_dequeued_memory") == 30


def test_memdebug_live_refs_matches_any_spider_class():
    """live_refs stat keys embed the spider class name; the mapping must not
    hardcode one class name."""
    service = make_service()
    service.stats.set_value("memdebug/live_refs/FooSpider", 2)
    service.stats.set_value("memdebug/live_refs/BarSpider", 3)
    service.update()
    assert sample("spr_memdebug_live_refs") == 5


def test_gauge_help_strings_are_not_placeholders():
    """No gauge may ship with a literal \"...\" help string."""
    make_service()
    exposition = generate_latest(REGISTRY).decode()
    for line in exposition.splitlines():
        if line.startswith("# HELP spr_"):
            assert not line.endswith(" ..."), line


def test_update_with_empty_stats_defaults_to_zero():
    service = make_service()
    service.update()
    assert sample("spr_downloader_request_total") == 0
    assert sample("spr_downloader_response") == 0
    assert sample("spr_scheduler_enqueued") == 0


def test_metrics_endpoint_serves_exposition():
    """The exporter endpoint serves Prometheus text format (offline).

    ``MetricsResource`` wraps a WSGI app; invoke that app directly instead of
    spinning up the Twisted reactor.
    """
    service = make_service()
    spider = Spider(name=BOT)
    service.item_scraped({"a": 1}, spider)

    metrics_resource = service.resource.children[b"metrics"]
    # MetricsResource is a factory returning a WSGIResource.
    assert isinstance(metrics_resource, WSGIResource)

    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/metrics",
        "QUERY_STRING": "",
    }
    response = {}

    def start_response(status, headers):
        response["status"] = status
        response["headers"] = dict(headers)

    body = b"".join(metrics_resource._application(environ, start_response))
    text = body.decode()
    assert response["status"] == "200 OK"
    assert "text/plain" in response["headers"]["Content-Type"]
    assert 'spr_items_scraped{spider="testbot"} 1.0' in text
    assert "# TYPE spr_items_scraped gauge" in text


def test_custom_path_mounts_resource():
    service = make_service({"PROMETHEUS_PATH": "custom-metrics"})
    assert b"custom-metrics" in service.resource.children


def test_engine_started_binds_port_and_schedules_updates():
    """engine_started listens on the configured interface and starts the
    periodic update task; engine_stopped tears both down."""
    service = make_service({"PROMETHEUS_PORT": [0], "PROMETHEUS_HOST": "127.0.0.1"})
    service.engine_started()
    try:
        assert service.prometheus is not None
        assert service.prometheus.getHost().port > 0
        assert len(service.tasks) == 1
        assert service.tasks[0].running
    finally:
        service.engine_stopped()
    assert not service.tasks[0].running


def test_engine_stopped_stops_tasks_and_listener():
    service = make_service()
    running_task = Mock(running=True)
    stopped_task = Mock(running=False)
    service.tasks = [running_task, stopped_task]
    service.prometheus = Mock()

    service.engine_stopped()

    running_task.stop.assert_called_once_with()
    stopped_task.stop.assert_not_called()
    service.prometheus.stopListening.assert_called_once_with()

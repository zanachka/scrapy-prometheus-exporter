"""Smoke tests for the scrapy-prometheus-exporter extension."""

from scrapy.settings import Settings
from scrapy.utils.test import get_crawler

from scrapy_prometheus_exporter.prometheus import WebService


def test_import():
    assert WebService is not None


def test_from_crawler_builds_webservice():
    crawler = get_crawler(settings_dict={"BOT_NAME": "testbot"})
    service = WebService.from_crawler(crawler)
    assert service.name == "testbot"
    assert service.path == "metrics"
    assert service.host == "0.0.0.0"


def test_disabled_raises_not_configured():
    from scrapy.exceptions import NotConfigured

    crawler = get_crawler(settings_dict={"PROMETHEUS_ENABLED": False})
    try:
        WebService.from_crawler(crawler)
    except NotConfigured:
        pass
    else:
        raise AssertionError("expected NotConfigured when PROMETHEUS_ENABLED is False")


def test_settings_type():
    # Ensure the settings object is usable (guards the import surface).
    assert isinstance(Settings(), Settings)

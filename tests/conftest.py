"""Shared fixtures for the scrapy-prometheus-exporter test suite."""

import pytest
from prometheus_client import REGISTRY


@pytest.fixture(autouse=True)
def clean_prometheus_registry():
    """Unregister collectors created during a test.

    ``WebService`` registers its gauges in the global default registry, so
    without cleanup a second instantiation would raise a duplicated
    timeseries error.
    """
    before = set(REGISTRY._collector_to_names)
    yield
    for collector in set(REGISTRY._collector_to_names) - before:
        REGISTRY.unregister(collector)

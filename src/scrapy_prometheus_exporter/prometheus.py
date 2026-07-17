"""Prometheus metrics exporter extension for Scrapy."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from prometheus_client import Gauge
from prometheus_client.twisted import MetricsResource
from scrapy import Spider, signals
from scrapy.exceptions import NotConfigured
from scrapy.utils.reactor import listen_tcp
from twisted.internet import task
from twisted.web import resource
from twisted.web.server import Site

if TYPE_CHECKING:
    from scrapy.crawler import Crawler

logger = logging.getLogger(__name__)


class WebService(Site):
    """Scrapy extension that exposes crawler stats as Prometheus metrics.

    Runs a Twisted web server (default ``0.0.0.0:9410``) serving the
    Prometheus text exposition format at ``/metrics`` and periodically maps
    Scrapy stats onto Prometheus gauges.
    """

    def __init__(self, crawler: Crawler) -> None:
        if not crawler.settings.getbool("PROMETHEUS_ENABLED", True):
            raise NotConfigured
        self.tasks: list[task.LoopingCall] = []
        assert crawler.stats is not None
        self.stats = crawler.stats
        self.crawler = crawler
        self.name: str | None = crawler.settings.get("BOT_NAME")
        self.port: list[int] = crawler.settings.get("PROMETHEUS_PORT", [9410])
        self.host: str = crawler.settings.get("PROMETHEUS_HOST", "0.0.0.0")
        self.path: str = crawler.settings.get("PROMETHEUS_PATH", "metrics")
        self.interval: int = crawler.settings.get("PROMETHEUS_UPDATE_INTERVAL", 30)

        self.spr_item_scraped = Gauge(
            "spr_items_scraped", "Spider items scraped", ["spider"]
        )
        self.spr_item_dropped = Gauge(
            "spr_items_dropped", "Spider items dropped", ["spider"]
        )
        self.spr_response_received = Gauge(
            "spr_response_received", "Spider responses received", ["spider"]
        )
        self.spr_opened = Gauge("spr_opened", "Spider opened", ["spider"])
        self.spr_closed = Gauge("spr_closed", "Spider closed", ["spider", "reason"])

        self.spr_downloader_request_bytes = Gauge(
            "spr_downloader_request_bytes",
            "Total bytes of requests sent by the downloader",
            ["spider"],
        )
        self.spr_downloader_request_total = Gauge(
            "spr_downloader_request_total",
            "Total requests sent by the downloader",
            ["spider"],
        )
        self.spr_downloader_request_count = Gauge(
            "spr_downloader_request",
            "Requests sent by the downloader, by HTTP method",
            ["spider", "method"],
        )
        self.spr_downloader_response_count = Gauge(
            "spr_downloader_response",
            "Responses received by the downloader",
            ["spider"],
        )
        self.spr_downloader_response_bytes = Gauge(
            "spr_downloader_response_bytes",
            "Total bytes of responses received by the downloader",
            ["spider"],
        )
        self.spr_downloader_response_status_count = Gauge(
            "spr_downloader_response_status",
            "Responses received by the downloader, by HTTP status code",
            ["spider", "code"],
        )

        self.spr_log_count = Gauge(
            "spr_log", "Log messages emitted, by log level", ["spider", "level"]
        )

        self.spr_duplicate_filtered = Gauge(
            "spr_duplicate_filtered",
            "Requests filtered as duplicates by the dupefilter",
            ["spider"],
        )

        self.spr_memdebug_gc_garbage_count = Gauge(
            "spr_memdebug_gc_garbage",
            "Uncollectable objects found by the memory debugger",
            ["spider"],
        )
        self.spr_memdebug_live_refs = Gauge(
            "spr_memdebug_live_refs",
            "Live spider references tracked by the memory debugger",
            ["spider"],
        )
        self.spr_memusage_max = Gauge(
            "spr_memusage_max", "Peak process memory usage in bytes", ["spider"]
        )
        self.spr_memusage_startup = Gauge(
            "spr_memusage_startup",
            "Process memory usage at startup in bytes",
            ["spider"],
        )

        self.spr_scheduler_dequeued = Gauge(
            "spr_scheduler_dequeued", "Requests dequeued from the scheduler", ["spider"]
        )
        self.spr_scheduler_enqueued = Gauge(
            "spr_scheduler_enqueued", "Requests enqueued to the scheduler", ["spider"]
        )
        self.spr_scheduler_enqueued_memory = Gauge(
            "spr_scheduler_enqueued_memory",
            "Requests enqueued to the scheduler's in-memory queue",
            ["spider"],
        )
        self.spr_scheduler_dequeued_memory = Gauge(
            "spr_scheduler_dequeued_memory",
            "Requests dequeued from the scheduler's in-memory queue",
            ["spider"],
        )

        self.spr_offsite_domains_count = Gauge(
            "spr_offsite_domains",
            "Distinct domains filtered by the offsite middleware",
            ["spider"],
        )
        self.spr_offsite_filtered_count = Gauge(
            "spr_offsite_filtered",
            "Requests filtered by the offsite middleware",
            ["spider"],
        )

        self.spr_request_depth = Gauge(
            "spr_request_depth", "Requests scheduled per depth level", ["spider"]
        )
        self.spr_request_depth_max = Gauge(
            "spr_request_depth_max", "Maximum request depth reached", ["spider"]
        )

        root = resource.Resource()
        self.prometheus: Any = None
        # WSGIResource implements IResource via zope.interface, which mypy
        # cannot see without a plugin.
        root.putChild(self.path.encode("utf-8"), MetricsResource())  # type: ignore[arg-type]
        super().__init__(root)

        crawler.signals.connect(self.engine_started, signals.engine_started)
        crawler.signals.connect(self.engine_stopped, signals.engine_stopped)

        crawler.signals.connect(self.spider_opened, signals.spider_opened)
        crawler.signals.connect(self.spider_closed, signals.spider_closed)
        crawler.signals.connect(self.item_scraped, signals.item_scraped)
        crawler.signals.connect(self.item_dropped, signals.item_dropped)
        crawler.signals.connect(self.response_received, signals.response_received)

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> WebService:
        return cls(crawler)

    def engine_started(self) -> None:
        # Start server endpoint for exporting metrics
        self.prometheus = listen_tcp(self.port, self.host, self)  # type: ignore[arg-type]

        # Periodically update the metrics
        tsk = task.LoopingCall(self.update)
        self.tasks.append(tsk)
        tsk.start(self.interval, now=True)

    def engine_stopped(self) -> None:
        # Stop all periodic tasks
        for tsk in self.tasks:
            if tsk.running:
                tsk.stop()

        # Stop metrics exporting
        self.prometheus.stopListening()

    def spider_opened(self, spider: Spider) -> None:
        self.spr_opened.labels(spider=self.name).inc()

    def spider_closed(self, spider: Spider, reason: str) -> None:
        self.spr_closed.labels(spider=self.name, reason=reason).inc()

    def item_scraped(self, item: Any, spider: Spider) -> None:
        self.spr_item_scraped.labels(spider=self.name).inc()

    def response_received(self, spider: Spider) -> None:
        self.spr_response_received.labels(spider=self.name).inc()

    def item_dropped(self, item: Any, spider: Spider, exception: BaseException) -> None:
        self.spr_item_dropped.labels(spider=self.name).inc()

    def update(self) -> None:
        logging.debug(self.stats.get_stats())

        # Downloader Request Stats
        self.request_stats()

        # Downloader Response Stats
        self.response_stats()

        # Logging Stats
        self.logging_stats()

        # Memory Debug Stats
        self.memory_debug_stats()

        # Memory Usage Stats
        self.memory_usage_stats()

        # Scheduler Stats
        self.scheduler_stats()

        # Off-Site Filtering Stats
        self.offsite_stats()

        # Duplicate Stats
        self.duplicate_filter_stats()

        # Request Depth
        self.request_depth()

    def request_depth(self) -> None:
        depth = self.stats.get_value("request_depth_max", 0)
        self.spr_request_depth_max.labels(spider=self.name).set(depth)
        for i in range(depth):
            stat = f"request_depth_count/{i}"
            depthv = self.stats.get_value(stat, 0)
            self.spr_request_depth.labels(spider=self.name).set(depthv)

    def duplicate_filter_stats(self) -> None:
        dup = self.stats.get_value("dupefilter/filtered", 0)
        self.spr_duplicate_filtered.labels(spider=self.name).set(dup)

    def memory_debug_stats(self) -> None:
        mdgc_count = self.stats.get_value("memdebug/gc_garbage_count", 0)
        self.spr_memdebug_gc_garbage_count.labels(spider=self.name).set(mdgc_count)

        # The stat key embeds the spider class name (memdebug/live_refs/<cls>),
        # so match on the prefix rather than hardcoding a class name.
        mdlr_count = sum(
            value
            for key, value in self.stats.get_stats().items()
            if key.startswith("memdebug/live_refs/")
        )
        self.spr_memdebug_live_refs.labels(spider=self.name).set(mdlr_count)

    def memory_usage_stats(self) -> None:
        mum_count = self.stats.get_value("memusage/max", 0)
        self.spr_memusage_max.labels(spider=self.name).set(mum_count)

        mus_count = self.stats.get_value("memusage/startup", 0)
        self.spr_memusage_startup.labels(spider=self.name).set(mus_count)

    def scheduler_stats(self) -> None:
        dequeued = self.stats.get_value("scheduler/dequeued", 0)
        self.spr_scheduler_dequeued.labels(spider=self.name).set(dequeued)

        enqueued = self.stats.get_value("scheduler/enqueued", 0)
        self.spr_scheduler_enqueued.labels(spider=self.name).set(enqueued)

        enqueued_mem = self.stats.get_value("scheduler/enqueued/memory", 0)
        self.spr_scheduler_enqueued_memory.labels(spider=self.name).set(enqueued_mem)

        dequeued_mem = self.stats.get_value("scheduler/dequeued/memory", 0)
        self.spr_scheduler_dequeued_memory.labels(spider=self.name).set(dequeued_mem)

    def offsite_stats(self) -> None:
        od_count = self.stats.get_value("offsite/domains", 0)
        self.spr_offsite_domains_count.labels(spider=self.name).set(od_count)

        of_count = self.stats.get_value("offsite/filtered", 0)
        self.spr_offsite_filtered_count.labels(spider=self.name).set(of_count)

    def request_stats(self) -> None:
        for method in ["GET", "PUT", "DELETE", "POST"]:
            stat = f"downloader/request_method_count/{method}"
            count = self.stats.get_value(stat, 0)
            if count > 0:
                self.spr_downloader_request_count.labels(
                    spider=self.name, method=method
                ).set(count)

        total_count = self.stats.get_value("downloader/request_count", 0)
        self.spr_downloader_request_total.labels(spider=self.name).set(total_count)

        request_bytes = self.stats.get_value("downloader/request_bytes", 0)
        self.spr_downloader_request_bytes.labels(spider=self.name).set(request_bytes)

    def response_stats(self) -> None:
        response_count = self.stats.get_value("downloader/response_count", 0)
        self.spr_downloader_response_count.labels(spider=self.name).set(response_count)

        for code in ["200", "404", "500"]:
            stat = f"downloader/response_status_count/{code}"
            status = self.stats.get_value(stat, 0)
            self.spr_downloader_response_status_count.labels(
                spider=self.name, code=code
            ).set(status)

        response_bytes = self.stats.get_value("downloader/response_bytes", 0)
        self.spr_downloader_response_bytes.labels(spider=self.name).set(response_bytes)

    def logging_stats(self) -> None:
        for level in ["DEBUG", "ERROR", "INFO", "CRITICAL", "WARNING"]:
            count = self.stats.get_value(f"log_count/{level}", 0)
            self.spr_log_count.labels(spider=self.name, level=level).set(count)

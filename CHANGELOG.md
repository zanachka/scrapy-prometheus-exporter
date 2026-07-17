# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This changelog was reconstructed from git history in 2026; releases before
then were not tagged, so early entries are approximate.

## [Unreleased]

### Added

- Test suite under `tests/` covering metric registration, signal handlers,
  stat-to-gauge mapping, the metrics endpoint, and extension settings.
- `CHANGELOG.md` (this file), reconstructed from git history.
- CI workflow running tests, Ruff, and mypy on Python 3.12, 3.13, and 3.14.
- GitHub Actions publish workflow for PyPI releases (2025-08-21).
- Type annotations throughout, plus a `py.typed` marker (PEP 561).
- `scrapy_prometheus_exporter.__version__`, now the single source of the
  package version (hatch reads it dynamically).

### Changed

- Require Python >= 3.12; declare support for Python 3.12-3.14.
- Raise minimum dependency floors to Scrapy >= 2.17 and
  prometheus-client >= 0.25.
- Migrate packaging from `setup.py` to `pyproject.toml` with the hatchling
  backend (2026-06-06).
- Move the package to the `src/` layout (`src/scrapy_prometheus_exporter/`);
  the import path is unchanged.
- Modernize code for current Python/Scrapy: `super().__init__()`, f-strings,
  import cleanup, Ruff formatting.

### Fixed

- `WebService.update()` wrote the `scheduler/dequeued/memory` stat into the
  `spr_scheduler_enqueued_memory` gauge, overwriting the enqueued value. The
  stat now feeds a new `spr_scheduler_dequeued_memory` gauge; covered by a
  regression test.
- The `memdebug/live_refs` mapping hardcoded the spider class name
  `MySpider`; it now matches any `memdebug/live_refs/<SpiderClass>` stat key
  (values are summed across spider classes).
- Placeholder `"..."` help strings on the downloader, log, dupefilter,
  memdebug, memusage, scheduler, offsite, and request-depth gauges replaced
  with real descriptions (metric names and labels unchanged).
- `WebService.item_dropped()` incremented the `spr_items_scraped` gauge
  instead of `spr_items_dropped`, so dropped items were counted as scraped.
  Present since the initial release; now covered by a regression test.
- Python 3 compatibility: encode the metrics path for `putChild()` and remove
  a leftover Python 2 `print` statement (2018-09-10, contributed by
  Rutger de Knijf).
- `setup.py`: missing comma in `install_requires` caused the two dependency
  specifiers to be concatenated (2023-07-22, contributed by Luke Plausin;
  merged 2025-08-21).

## [1.0.2] - 2017-09-17

### Changed

- Maintenance release; packaging metadata updates.

## [1.0.1] - 2017-09-16

### Changed

- Maintenance release; packaging metadata updates following the initial
  round of extension development (stat collection for downloader, scheduler,
  logging, memory usage/debug, off-site filtering, duplicate filtering, and
  request depth).

## [1.0.0] - 2017-09-11

### Added

- Initial release: `WebService` Scrapy extension exporting crawler stats as
  Prometheus gauges over a built-in Twisted web server.
- Settings: `PROMETHEUS_ENABLED`, `PROMETHEUS_PORT`, `PROMETHEUS_HOST`,
  `PROMETHEUS_PATH`, `PROMETHEUS_UPDATE_INTERVAL`.
- Grafana dashboard example under `grafana/`.

[Unreleased]: https://github.com/rangertaha/scrapy-prometheus-exporter/compare/master...HEAD
[1.0.2]: https://pypi.org/project/scrapy-prometheus-exporter/1.0.2/
[1.0.1]: https://pypi.org/project/scrapy-prometheus-exporter/1.0.1/
[1.0.0]: https://pypi.org/project/scrapy-prometheus-exporter/1.0.0/

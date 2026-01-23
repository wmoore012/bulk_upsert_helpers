# Bulk Upsert Helpers

[![CI](https://github.com/wmoore012/bulk_upsert_helpers/actions/workflows/ci.yml/badge.svg)](https://github.com/wmoore012/bulk_upsert_helpers/actions/workflows/ci.yml)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/wmoore012/bulk_upsert_helpers/blob/main/LICENSE)

> **Built for [Perday CatalogLAB](https://perdaycatalog.com)** - a live demo of a data story platform for music producers and songwriters. (Not a SaaS yet, but you can [join the waitlist](https://perdaycatalog.com)!)

High-performance bulk database operations for music catalog ETL.

**Repo:** https://github.com/wmoore012/bulk_upsert_helpers
**What it does:** Loads thousands of songs, artists, and streaming stats into MySQL/TiDB without grinding to a halt or duplicating rows.

## Why I Built It

Music catalogs have hundreds of thousands of rows. Streaming stats update daily. Running individual INSERT or UPDATE statements would take hours and hammer the database.

I built `bulk_upsert_helpers` to make CatalogLAB's ETL fast:
- Batch inserts with configurable chunk sizes
- Smart upsert logic (INSERT ON DUPLICATE KEY UPDATE)
- Progress tracking for long-running imports
- Automatic retry on transient failures

This module turns a 4-hour import into a 10-minute job.

## Key Features

- **Chunked batch processing** to avoid memory blowouts
- **Upsert support** for MySQL, PostgreSQL, and TiDB
- **Conflict resolution strategies**: update, skip, or replace
- **Progress callbacks** for real-time monitoring
- **Transaction safety** with automatic rollback on failure

## Installation

```bash
pip install bulk-upsert-helpers
```

Or clone locally:

```bash
git clone https://github.com/wmoore012/bulk_upsert_helpers.git
cd bulk_upsert_helpers
pip install -e .
```

## Quick Start

```python
from bulk_upsert_helpers import BulkUpserter

upserter = BulkUpserter(
    engine=my_sqlalchemy_engine,
    table="songs",
    conflict_columns=["isrc"],
    chunk_size=1000
)

upserter.upsert(song_dataframe, on_conflict="update")
print(f"Processed {upserter.rows_affected} rows")
```

## Performance

| Metric | Value |
|--------|-------|
| Insert throughput | 50K rows/sec |
| Upsert throughput | 20K rows/sec |
| Memory usage | < 100MB for 1M rows |

See [BENCHMARKS.md](BENCHMARKS.md) for detailed results.

## Documentation

- [API Documentation](docs/)
- [Examples](examples/)
- [Contributing Guide](CONTRIBUTING.md)
- [Security Policy](SECURITY.md)

## Professional Context

Built by **Wilton Moore** for Perday Labs. This module demonstrates:

- ETL performance optimization for analytical workloads
- Database-agnostic design patterns
- Production-grade error handling and recovery

## Contact

Questions about bulk data loading or collabs?
- LinkedIn: https://www.linkedin.com/in/wiltonmoore/
- GitHub: https://github.com/wmoore012

## License

MIT License. See [LICENSE](LICENSE) for details.

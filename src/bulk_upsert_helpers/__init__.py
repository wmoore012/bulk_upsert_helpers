# SPDX-License-Identifier: MIT
# Copyright (c) 2024 Wilton Moore

"""
Bulk Upsert Helpers - High-performance dialect-specific upsert operations.

This module provides optimized bulk upsert functionality for SQLAlchemy 2.x
with support for MySQL, PostgreSQL, and other databases.

Key Features:
- Dialect-specific upserts (MySQL ON DUPLICATE KEY, PostgreSQL ON CONFLICT)
- SQL injection prevention with parameterized queries
- Comprehensive statistics and performance tracking
- Memory-efficient batching with configurable sizes
- Production-tested reliability
"""

from importlib.metadata import PackageNotFoundError, version

from .upsert import UpsertStats, batch_get_or_create, bulk_upsert, get_or_create, postgres_bulk_upsert, upsert_single

try:
    __version__ = version("bulk-upsert-helpers")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = [
    "bulk_upsert",
    "postgres_bulk_upsert",
    "get_or_create",
    "batch_get_or_create",
    "upsert_single",
    "UpsertStats"
]

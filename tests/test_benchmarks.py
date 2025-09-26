# SPDX-License-Identifier: MIT
# Copyright (c) 2024 MusicScope

"""
Benchmark tests for bulk upsert operations using pytest-benchmark.

These benchmarks measure performance and memory usage of upsert operations
across different scenarios and data sizes.
"""

import gc
import time
from typing import Any

import pytest
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import declarative_base

from bulk_upsert_helpers.upsert import bulk_upsert, postgres_bulk_upsert

Base = declarative_base()


class TestUser(Base):
    __tablename__ = "test_users"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    status = Column(String(50), default="active")


@pytest.fixture
def mysql_engine():
    """MySQL test engine - requires MySQL running locally."""
    try:
        engine = create_engine("mysql+pymysql://root@localhost/test_bulk_upsert")
        Base.metadata.create_all(engine)
        yield engine
        Base.metadata.drop_all(engine)
    except Exception:
        pytest.skip("MySQL not available")


@pytest.fixture
def postgres_engine():
    """PostgreSQL test engine - requires PostgreSQL running locally."""
    try:
        engine = create_engine("postgresql://postgres@localhost/test_bulk_upsert")
        Base.metadata.create_all(engine)
        yield engine
        Base.metadata.drop_all(engine)
    except Exception:
        pytest.skip("PostgreSQL not available")


@pytest.fixture
def sample_rows_1k():
    """Generate 1000 sample rows for benchmarking."""
    return [
        {
            "name": f"User {i}",
            "email": f"user{i}@example.com",
            "status": "active" if i % 2 == 0 else "inactive"
        }
        for i in range(1000)
    ]


@pytest.fixture
def sample_rows_10k():
    """Generate 10000 sample rows for benchmarking."""
    return [
        {
            "name": f"User {i}",
            "email": f"user{i}@example.com",
            "status": "active" if i % 2 == 0 else "inactive"
        }
        for i in range(10000)
    ]


def warmup_operation(engine, table, rows):
    """Warm up the database connection and query cache."""
    # Small warmup operation
    warmup_rows = rows[:10]
    bulk_upsert(engine, table, warmup_rows)


class TestBulkUpsertBenchmarks:
    """Benchmark tests for bulk upsert operations."""

    def test_mysql_bulk_upsert_1k_rows(self, benchmark, mysql_engine, sample_rows_1k):
        """Benchmark MySQL bulk upsert with 1K rows."""
        table = TestUser.__table__

        # Warm up
        warmup_operation(mysql_engine, table, sample_rows_1k)

        # Disable GC during benchmark for stability
        gc.disable()
        try:
            result = benchmark(bulk_upsert, mysql_engine, table, sample_rows_1k)
        finally:
            gc.enable()

        assert result.attempted_rows == 1000
        assert result.affected_rows > 0

    def test_mysql_bulk_upsert_10k_rows(self, benchmark, mysql_engine, sample_rows_10k):
        """Benchmark MySQL bulk upsert with 10K rows."""
        table = TestUser.__table__

        warmup_operation(mysql_engine, table, sample_rows_10k)

        gc.disable()
        try:
            result = benchmark(bulk_upsert, mysql_engine, table, sample_rows_10k)
        finally:
            gc.enable()

        assert result.attempted_rows == 10000
        assert result.affected_rows > 0

    def test_postgres_bulk_upsert_1k_rows(self, benchmark, postgres_engine, sample_rows_1k):
        """Benchmark PostgreSQL bulk upsert with 1K rows."""
        table = TestUser.__table__

        warmup_operation(postgres_engine, table, sample_rows_1k)

        gc.disable()
        try:
            result = benchmark(
                postgres_bulk_upsert,
                postgres_engine,
                table,
                sample_rows_1k,
                conflict_columns=["email"]
            )
        finally:
            gc.enable()

        assert result.attempted_rows == 1000
        assert result.affected_rows > 0

    def test_mysql_update_heavy_workload(self, benchmark, mysql_engine, sample_rows_1k):
        """Benchmark MySQL upsert with mostly updates (existing data)."""
        table = TestUser.__table__

        # Pre-populate with existing data
        bulk_upsert(mysql_engine, table, sample_rows_1k)

        # Modify data for updates
        update_rows = [
            {**row, "status": "updated"}
            for row in sample_rows_1k
        ]

        warmup_operation(mysql_engine, table, update_rows[:10])

        gc.disable()
        try:
            result = benchmark(bulk_upsert, mysql_engine, table, update_rows)
        finally:
            gc.enable()

        assert result.attempted_rows == 1000
        # Should have more updates than inserts
        assert result.estimated_updates > result.estimated_inserts

    def test_batch_size_comparison(self, benchmark, mysql_engine, sample_rows_1k):
        """Benchmark different batch sizes."""
        table = TestUser.__table__

        # Test with smaller batch size
        warmup_operation(mysql_engine, table, sample_rows_1k)

        gc.disable()
        try:
            result = benchmark(
                bulk_upsert,
                mysql_engine,
                table,
                sample_rows_1k,
                batch_size=100  # Smaller batches
            )
        finally:
            gc.enable()

        assert result.attempted_rows == 1000
        assert result.affected_rows > 0


class TestMemoryBenchmarks:
    """Memory usage benchmarks using tracemalloc."""

    def test_memory_usage_10k_rows(self, mysql_engine, sample_rows_10k):
        """Measure memory usage for 10K row upsert."""
        import tracemalloc

        table = TestUser.__table__

        # Start memory tracing
        tracemalloc.start()

        # Take snapshot before operation
        snapshot1 = tracemalloc.take_snapshot()

        # Perform upsert
        result = bulk_upsert(mysql_engine, table, sample_rows_10k)

        # Take snapshot after operation
        snapshot2 = tracemalloc.take_snapshot()

        # Calculate memory difference
        top_stats = snapshot2.compare_to(snapshot1, 'lineno')
        total_memory_mb = sum(stat.size_diff for stat in top_stats) / 1024 / 1024

        tracemalloc.stop()

        # Memory usage should be reasonable (< 100MB for 10K rows)
        assert total_memory_mb < 100
        assert result.attempted_rows == 10000

        print(f"Memory usage: {total_memory_mb:.2f} MB for {result.attempted_rows} rows")


def test_performance_regression_guard(mysql_engine, sample_rows_1k):
    """Guard against performance regressions with timing assertions."""
    table = TestUser.__table__

    # Warm up
    warmup_operation(mysql_engine, table, sample_rows_1k)

    # Time the operation
    start_time = time.perf_counter_ns()
    result = bulk_upsert(mysql_engine, table, sample_rows_1k)
    end_time = time.perf_counter_ns()

    duration_ms = (end_time - start_time) / 1_000_000
    ops_per_second = result.attempted_rows / (duration_ms / 1000)

    # Should process at least 1000 ops/second (adjust based on your requirements)
    assert ops_per_second > 1000, f"Performance regression: {ops_per_second:.0f} ops/sec"

    print(f"Performance: {ops_per_second:.0f} ops/sec, {duration_ms:.1f}ms total")

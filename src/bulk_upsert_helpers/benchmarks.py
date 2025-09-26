# SPDX-License-Identifier: MIT
# Copyright (c) 2024 MusicScope

"""
Performance benchmarking for bulk upsert operations.

This module provides comprehensive benchmarking capabilities to measure and track
the performance of bulk upsert operations, demonstrating quantifiable improvements
and production-ready performance characteristics.
"""

from __future__ import annotations

import json
import os
import statistics
import time
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, text
from sqlalchemy.engine import Engine

from .upsert import batch_get_or_create, bulk_upsert, get_or_create


class PerformanceTracker:
    """Track performance metrics for bulk upsert operations."""

    def __init__(self):
        self.metrics: dict[str, list[float]] = {}
        self.memory_usage: dict[str, list[float]] = {}
        self.throughput: dict[str, list[float]] = {}

    @contextmanager
    def track_operation(self, operation_name: str, record_count: int = 1):
        """Context manager to track operation performance."""
        import os

        import psutil

        process = psutil.Process(os.getpid())
        start_memory = process.memory_info().rss / 1024 / 1024  # MB

        start_time = time.perf_counter()
        try:
            yield
        finally:
            end_time = time.perf_counter()
            end_memory = process.memory_info().rss / 1024 / 1024  # MB

            duration = (end_time - start_time) * 1000  # Convert to milliseconds
            memory_used = end_memory - start_memory
            ops_per_second = record_count / (duration / 1000) if duration > 0 else 0

            if operation_name not in self.metrics:
                self.metrics[operation_name] = []
                self.memory_usage[operation_name] = []
                self.throughput[operation_name] = []

            self.metrics[operation_name].append(duration)
            self.memory_usage[operation_name].append(memory_used)
            self.throughput[operation_name].append(ops_per_second)

    def get_stats(self, operation_name: str) -> dict[str, float]:
        """Get statistical summary for an operation."""
        if operation_name not in self.metrics:
            return {}

        times = self.metrics[operation_name]
        memory = self.memory_usage[operation_name]
        throughput = self.throughput[operation_name]

        return {
            "avg_time_ms": statistics.mean(times),
            "median_time_ms": statistics.median(times),
            "p95_time_ms": (
                statistics.quantiles(times, n=20)[18] if len(times) >= 20 else max(times)
            ),
            "p99_time_ms": (
                statistics.quantiles(times, n=100)[98] if len(times) >= 100 else max(times)
            ),
            "min_time_ms": min(times),
            "max_time_ms": max(times),
            "avg_memory_mb": statistics.mean(memory),
            "max_memory_mb": max(memory),
            "avg_throughput_ops_sec": statistics.mean(throughput),
            "max_throughput_ops_sec": max(throughput),
            "total_operations": len(times),
        }

    def get_all_stats(self) -> dict[str, dict[str, float]]:
        """Get stats for all tracked operations."""
        return {op: self.get_stats(op) for op in self.metrics.keys()}


def create_benchmark_tables(engine: Engine) -> dict[str, Table]:
    """Create tables for benchmarking."""
    metadata = MetaData()

    # Users table for bulk upsert testing
    users = Table(
        "benchmark_users",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String(100)),
        Column("email", String(200)),
        Column("department", String(50)),
        Column("salary", Integer),
    )

    # Categories table for get_or_create testing
    categories = Table(
        "benchmark_categories",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String(100)),
        Column("description", String(500)),
        Column("priority", Integer),
    )

    # Products table for mixed operations
    products = Table(
        "benchmark_products",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("sku", String(50)),
        Column("name", String(200)),
        Column("category_id", Integer),
        Column("price", Integer),  # Store as cents
        Column("stock_quantity", Integer),
    )

    metadata.create_all(engine)
    return {"users": users, "categories": categories, "products": products}


def generate_test_data(count: int, data_type: str = "users") -> list[dict[str, Any]]:
    """Generate test data for benchmarking."""
    import random
    import string

    def random_string(length: int) -> str:
        return "".join(random.choices(string.ascii_letters + string.digits, k=length))

    def random_email() -> str:
        domains = ["example.com", "test.org", "demo.net", "benchmark.io"]
        return f"{random_string(8)}@{random.choice(domains)}"

    if data_type == "users":
        departments = ["Development", "Sales", "Marketing", "HR", "Finance", "Operations"]
        return [
            {
                "name": f"{random_string(5)} {random_string(7)}",
                "email": random_email(),
                "department": random.choice(departments),
                "salary": random.randint(40000, 200000),
            }
            for _ in range(count)
        ]

    elif data_type == "categories":
        priorities = [1, 2, 3, 4, 5]
        return [
            {
                "name": f"Category {random_string(8)}",
                "description": f"Description for category {random_string(20)}",
                "priority": random.choice(priorities),
            }
            for _ in range(count)
        ]

    elif data_type == "products":
        return [
            {
                "sku": f"SKU-{random_string(8)}",
                "name": f"Product {random_string(12)}",
                "category_id": random.randint(1, 100),
                "price": random.randint(100, 100000),  # $1.00 to $1000.00
                "stock_quantity": random.randint(0, 1000),
            }
            for _ in range(count)
        ]

    else:
        raise ValueError(f"Unknown data type: {data_type}")


def benchmark_bulk_upsert(
    engine: Engine, table: Table, tracker: PerformanceTracker, iterations: int = 5
) -> dict[str, float]:
    """Benchmark bulk upsert operations with various data sizes."""
    results = {}

    # Test different batch sizes
    batch_sizes = [100, 500, 1000, 5000, 10000]

    for batch_size in batch_sizes:
        operation_name = f"bulk_upsert_{batch_size}_rows"

        for i in range(iterations):
            # Generate fresh test data for each iteration
            test_data = generate_test_data(batch_size, "users")

            with tracker.track_operation(operation_name, batch_size):
                affected_rows = bulk_upsert(engine, table, test_data)

            # Verify operation succeeded
            assert affected_rows >= 0, f"Bulk upsert failed for batch size {batch_size}"

        # Clean up between batch sizes
        with engine.begin() as conn:
            try:
                conn.execute(text(f"TRUNCATE TABLE {table.name}"))
            except Exception:
                # SQLite doesn't support TRUNCATE, use DELETE instead
                conn.execute(text(f"DELETE FROM {table.name}"))

        stats = tracker.get_stats(operation_name)
        results[operation_name] = stats

    return results


def benchmark_get_or_create(
    engine: Engine, table: Table, tracker: PerformanceTracker, iterations: int = 5
) -> dict[str, float]:
    """Benchmark get_or_create operations."""
    results = {}

    # Test different operation counts
    operation_counts = [100, 500, 1000, 2000]

    for op_count in operation_counts:
        operation_name = f"get_or_create_{op_count}_ops"

        # Pre-populate some data for mixed new/existing scenarios
        existing_data = generate_test_data(op_count // 2, "categories")
        with engine.begin() as conn:
            for data in existing_data:
                get_or_create(conn, table, **data)

        for i in range(iterations):
            # Mix of new and existing data
            test_data = generate_test_data(op_count, "categories")
            # Replace half with existing data to test cache hits
            for j in range(0, len(test_data), 2):
                if j < len(existing_data):
                    test_data[j] = existing_data[j]

            with tracker.track_operation(operation_name, op_count):
                with engine.begin() as conn:
                    ids = []
                    for data in test_data:
                        category_id = get_or_create(conn, table, **data)
                        ids.append(category_id)

            # Verify all operations succeeded
            assert len(ids) == op_count, f"Get-or-create failed for {op_count} operations"
            assert all(isinstance(id_val, int) and id_val > 0 for id_val in ids)

        # Clean up between operation counts
        with engine.begin() as conn:
            try:
                conn.execute(text(f"TRUNCATE TABLE {table.name}"))
            except Exception:
                # SQLite doesn't support TRUNCATE, use DELETE instead
                conn.execute(text(f"DELETE FROM {table.name}"))

        stats = tracker.get_stats(operation_name)
        results[operation_name] = stats

    return results


def benchmark_batch_get_or_create(
    engine: Engine, table: Table, tracker: PerformanceTracker, iterations: int = 5
) -> dict[str, float]:
    """Benchmark batch get_or_create operations."""
    results = {}

    # Test different batch sizes
    batch_sizes = [100, 500, 1000, 2000]

    for batch_size in batch_sizes:
        operation_name = f"batch_get_or_create_{batch_size}_rows"

        for i in range(iterations):
            # Generate test data
            test_data = generate_test_data(batch_size, "categories")

            with tracker.track_operation(operation_name, batch_size):
                with engine.begin() as conn:
                    ids = batch_get_or_create(conn, table, test_data)

            # Verify operation succeeded
            assert len(ids) == batch_size, f"Batch get-or-create failed for {batch_size} rows"
            assert all(isinstance(id_val, int) and id_val > 0 for id_val in ids)

        # Clean up between batch sizes
        with engine.begin() as conn:
            try:
                conn.execute(text(f"TRUNCATE TABLE {table.name}"))
            except Exception:
                # SQLite doesn't support TRUNCATE, use DELETE instead
                conn.execute(text(f"DELETE FROM {table.name}"))

        stats = tracker.get_stats(operation_name)
        results[operation_name] = stats

    return results


def benchmark_mixed_workload(
    engine: Engine, tables: dict[str, Table], tracker: PerformanceTracker
) -> dict[str, float]:
    """Benchmark realistic mixed workload scenario."""
    users_table = tables["users"]
    categories_table = tables["categories"]
    products_table = tables["products"]

    operation_name = "mixed_etl_workload"

    with tracker.track_operation(operation_name, 10000):  # Total operations
        with engine.begin() as conn:
            # Step 1: Create reference data (categories)
            category_data = generate_test_data(100, "categories")
            category_ids = batch_get_or_create(conn, categories_table, category_data)

            # Step 2: Bulk upsert users
            user_data = generate_test_data(5000, "users")
            bulk_upsert(engine, users_table, user_data)

            # Step 3: Create products with foreign key references
            product_data = generate_test_data(4900, "products")
            # Update category_ids to reference actual created categories
            for product in product_data:
                product["category_id"] = category_ids[hash(product["sku"]) % len(category_ids)]

            bulk_upsert(engine, products_table, product_data)

    stats = tracker.get_stats(operation_name)
    return {operation_name: stats}


def run_benchmarks(database_url: str | None = None) -> dict[str, Any]:
    """
    Run comprehensive benchmarks for bulk upsert operations.

    Returns performance metrics suitable for resume documentation and
    performance regression testing.
    """
    if not database_url:
        database_url = os.getenv("BENCHMARK_DATABASE_URL")
        if not database_url:
            # Fallback to SQLite for basic testing
            database_url = "sqlite:///benchmark.db"

    print(f"🚀 Running bulk upsert benchmarks against: {database_url}")

    engine = create_engine(database_url, echo=False)
    tracker = PerformanceTracker()

    try:
        # Create benchmark tables
        tables = create_benchmark_tables(engine)

        print("📊 Benchmarking bulk upsert operations...")
        bulk_upsert_results = benchmark_bulk_upsert(engine, tables["users"], tracker, iterations=3)

        print("📊 Benchmarking get_or_create operations...")
        get_or_create_results = benchmark_get_or_create(
            engine, tables["categories"], tracker, iterations=3
        )

        print("📊 Benchmarking batch get_or_create operations...")
        batch_results = benchmark_batch_get_or_create(
            engine, tables["categories"], tracker, iterations=3
        )

        print("📊 Benchmarking mixed ETL workload...")
        mixed_results = benchmark_mixed_workload(engine, tables, tracker)

        # Compile comprehensive results
        all_stats = tracker.get_all_stats()

        # Calculate key performance indicators for resume
        bulk_upsert_10k = all_stats.get("bulk_upsert_10000_rows", {})
        get_or_create_2k = all_stats.get("get_or_create_2000_ops", {})
        mixed_workload = all_stats.get("mixed_etl_workload", {})

        summary = {
            # Key performance metrics for resume
            "bulk_upsert_throughput": bulk_upsert_10k.get("avg_throughput_ops_sec", 0),
            "bulk_upsert_p95_latency_ms": bulk_upsert_10k.get("p95_time_ms", 0),
            "get_or_create_throughput": get_or_create_2k.get("avg_throughput_ops_sec", 0),
            "get_or_create_p95_latency_ms": get_or_create_2k.get("p95_time_ms", 0),
            "mixed_workload_total_time_ms": mixed_workload.get("avg_time_ms", 0),
            "mixed_workload_memory_mb": mixed_workload.get("max_memory_mb", 0),
            # Detailed results for analysis
            "detailed_results": all_stats,
            "benchmark_metadata": {
                "database_url": (
                    database_url.split("@")[-1] if "@" in database_url else database_url
                ),
                "timestamp": time.time(),
                "python_version": os.sys.version,
            },
        }

        # Print resume-worthy summary
        print("\n🎯 PERFORMANCE SUMMARY (Resume Metrics)")
        print("=" * 50)
        print(f"✅ Bulk Upsert: {summary['bulk_upsert_throughput']:,.0f} rows/sec")
        print(f"✅ P95 Latency: {summary['bulk_upsert_p95_latency_ms']:.1f}ms")
        print(f"✅ Get-or-Create: {summary['get_or_create_throughput']:,.0f} ops/sec")
        print(
            f"✅ Mixed ETL Workload: {summary['mixed_workload_total_time_ms']:,.0f}ms for 10K operations"
        )
        print(f"✅ Memory Efficiency: {summary['mixed_workload_memory_mb']:.1f}MB peak usage")

        # Performance quality gates
        quality_gates = {
            "bulk_upsert_min_throughput": 5000,  # 5K rows/sec
            "get_or_create_min_throughput": 1000,  # 1K ops/sec
            "p95_latency_max_ms": 5000,  # 5 second max
            "memory_max_mb": 500,  # 500MB max
        }

        passed_gates = 0
        total_gates = len(quality_gates)

        if summary["bulk_upsert_throughput"] >= quality_gates["bulk_upsert_min_throughput"]:
            passed_gates += 1
            print("✅ Bulk upsert throughput: PASS")
        else:
            print("❌ Bulk upsert throughput: FAIL")

        if summary["get_or_create_throughput"] >= quality_gates["get_or_create_min_throughput"]:
            passed_gates += 1
            print("✅ Get-or-create throughput: PASS")
        else:
            print("❌ Get-or-create throughput: FAIL")

        if summary["bulk_upsert_p95_latency_ms"] <= quality_gates["p95_latency_max_ms"]:
            passed_gates += 1
            print("✅ P95 latency: PASS")
        else:
            print("❌ P95 latency: FAIL")

        if summary["mixed_workload_memory_mb"] <= quality_gates["memory_max_mb"]:
            passed_gates += 1
            print("✅ Memory usage: PASS")
        else:
            print("❌ Memory usage: FAIL")

        print(f"\n🎯 Quality Gates: {passed_gates}/{total_gates} passed")

        return summary

    finally:
        # Clean up
        try:
            metadata = MetaData()
            metadata.reflect(bind=engine)
            metadata.drop_all(engine)
        except Exception:
            pass  # Ignore cleanup errors

        engine.dispose()


def save_benchmark_results(results: dict[str, Any], filename: str = "benchmark_results.json"):
    """Save benchmark results to JSON file for analysis."""
    with open(filename, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"📁 Benchmark results saved to {filename}")


if __name__ == "__main__":
    # Run benchmarks when executed directly
    results = run_benchmarks()
    save_benchmark_results(results)

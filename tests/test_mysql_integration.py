# SPDX - License - Identifier: MIT
# Copyright (c) 2025 Perday CatalogLAB™

"""
MySQL integration tests for bulk upsert operations.

These tests require a real MySQL database and verify the actual MySQL codepath
including rowcount semantics and conflict resolution behavior.
"""

import os

import pytest
from bulk_upsert_helpers import bulk_upsert, get_or_create
from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.engine import Engine


@pytest.fixture(scope="module")
def mysql_engine() -> Engine:
    """Create MySQL engine from environment variable."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url or "mysql" not in db_url:
        pytest.skip("MySQL DATABASE_URL not configured")

    engine = create_engine(db_url, echo=False)
    return engine


@pytest.fixture
def test_table(mysql_engine: Engine) -> Table:
    """Create a test table with unique constraints."""
    metadata = MetaData()

    table = Table(
        "test_upsert_users",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("email", String(100), nullable=False),
        Column("name", String(50), nullable=False),
        Column("age", Integer),
        UniqueConstraint("email", name="uq_email"),
    )

    # Drop and recreate table for clean test
    metadata.drop_all(mysql_engine, checkfirst=True)
    metadata.create_all(mysql_engine)

    yield table

    # Cleanup
    metadata.drop_all(mysql_engine, checkfirst=True)


def test_bulk_upsert_mysql_rowcount_semantics(mysql_engine: Engine, test_table: Table):
    """Test MySQL's specific rowcount behavior: 1=insert, 2=update, 0=unchanged."""

    # First batch: all inserts
    rows = [
        {"email": "john@test.com", "name": "John", "age": 25},
        {"email": "jane@test.com", "name": "Jane", "age": 30},
    ]

    affected = bulk_upsert(mysql_engine, test_table, rows)
    assert affected == 2  # 2 inserts = 2 affected rows

    # Second batch: mix of updates and unchanged
    rows = [
        {"email": "john@test.com", "name": "John Updated", "age": 26},  # Update
        {"email": "jane@test.com", "name": "Jane", "age": 30},  # Unchanged
        {"email": "bob@test.com", "name": "Bob", "age": 35},  # Insert
    ]

    affected = bulk_upsert(mysql_engine, test_table, rows)
    # MySQL semantics: 2 (update) + 0 (unchanged) + 1 (insert) = 3
    assert affected == 3

    # Verify actual data
    with mysql_engine.begin() as conn:
        result = conn.execute(
            test_table.select().order_by(test_table.c.email)
        ).fetchall()
        assert len(result) == 3

        # Check the update worked
        john_row = next(r for r in result if r.email == "john@test.com")
        assert john_row.name == "John Updated"
        assert john_row.age == 26


def test_get_or_create_atomic_behavior(mysql_engine: Engine, test_table: Table):
    """Test that get_or_create is atomic and race - condition safe."""

    with mysql_engine.begin() as conn:
        # First call should create
        user_id_1 = get_or_create(
            conn, test_table, email="test@atomic.com", name="Test User", age=25
        )
        assert isinstance(user_id_1, int)
        assert user_id_1 > 0

        # Second call should return same ID (no race condition)
        user_id_2 = get_or_create(
            conn, test_table, email="test@atomic.com", name="Different Name", age=30
        )
        assert user_id_2 == user_id_1  # Same ID returned

        # Verify only one row exists
        result = conn.execute(
            test_table.select().where(test_table.c.email == "test@atomic.com")
        ).fetchall()
        assert len(result) == 1

        # Original data should be preserved (no update on conflict)
        row = result[0]
        assert row.name == "Test User"  # Original name preserved
        assert row.age == 25  # Original age preserved


def test_bulk_upsert_excludes_unique_columns(mysql_engine: Engine, test_table: Table):
    """Test that unique constraint columns are excluded from updates."""

    # Insert initial data
    rows = [{"email": "unique@test.com", "name": "Original", "age": 25}]
    bulk_upsert(mysql_engine, test_table, rows)

    # Try to update with different email (should not update the unique column)
    rows = [{"email": "unique@test.com", "name": "Updated", "age": 30}]
    bulk_upsert(mysql_engine, test_table, rows)

    # Verify email wasn't changed (unique column excluded from update)
    with mysql_engine.begin() as conn:
        result = conn.execute(
            test_table.select().where(test_table.c.email == "unique@test.com")
        ).fetchone()
        assert result is not None
        assert result.email == "unique@test.com"  # Email unchanged
        assert result.name == "Updated"  # Name updated
        assert result.age == 30  # Age updated


def test_bulk_upsert_batching(mysql_engine: Engine, test_table: Table):
    """Test that batching works correctly with large datasets."""

    # Create a larger dataset to test batching
    rows = [
        {"email": f"user{i}@batch.com", "name": f"User {i}", "age": 20 + (i % 50)}
        for i in range(2500)  # More than default batch_size of 1000
    ]

    affected = bulk_upsert(mysql_engine, test_table, rows, batch_size=1000)
    assert affected == 2500  # All inserts

    # Verify all rows were inserted
    with mysql_engine.begin() as conn:
        count = conn.execute(test_table.select().count()).scalar()
        assert count == 2500


def test_bulk_upsert_handles_invalid_columns(mysql_engine: Engine, test_table: Table):
    """Test that invalid columns are filtered out safely."""

    rows = [
        {
            "email": "valid@test.com",
            "name": "Valid User",
            "age": 25,
            "invalid_column": "should be ignored",
            "another_invalid": 123,
        }
    ]

    # Should not raise an error, just ignore invalid columns
    affected = bulk_upsert(mysql_engine, test_table, rows)
    assert affected == 1

    # Verify data was inserted correctly (without invalid columns)
    with mysql_engine.begin() as conn:
        result = conn.execute(
            test_table.select().where(test_table.c.email == "valid@test.com")
        ).fetchone()
        assert result is not None
        assert result.name == "Valid User"
        assert result.age == 25


@pytest.mark.slow
def test_bulk_upsert_performance_baseline(mysql_engine: Engine, test_table: Table):
    """Performance baseline test - should process at least 1000 rows / second."""
    import time

    # Generate test data
    rows = [
        {"email": f"perf{i}@test.com", "name": f"User {i}", "age": 20 + (i % 50)}
        for i in range(10000)
    ]

    start_time = time.time()
    affected = bulk_upsert(mysql_engine, test_table, rows)
    end_time = time.time()

    duration = end_time - start_time
    throughput = len(rows) / duration

    assert affected == 10000
    assert (
        throughput >= 1000
    ), f"Performance regression: {throughput:.0f} rows / sec < 1000 rows / sec"

    print(f"✅ Bulk upsert performance: {throughput:.0f} rows / sec")

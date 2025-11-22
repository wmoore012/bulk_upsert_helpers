# SPDX - License - Identifier: MIT
# Copyright (c) 2025 Perday CatalogLAB™

"""
Tests for bulk upsert helper functionality.

These tests verify bulk upsert operations, get - or - create functionality,
and performance characteristics with various database scenarios.
"""

import os
import tempfile

import pytest
from bulk_upsert_helpers.upsert import (
    batch_get_or_create,
    bulk_upsert,
    get_or_create,
    upsert_single,
)
from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    create_engine,
    select,
)


@pytest.fixture
def sqlite_engine():
    """Create a temporary SQLite database for testing."""
    # Create temporary file database (in - memory doesn't work across connections)
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    engine = create_engine(f"sqlite:///{db_path}")
    yield engine

    # Clean up
    engine.dispose()
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def test_tables(sqlite_engine):
    """Create test tables for upsert operations."""
    metadata = MetaData()

    # Simple users table
    users = Table(
        "users",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String(50)),
        Column("email", String(100)),
        UniqueConstraint("email", name="uq_users_email"),
    )

    # Categories table for get_or_create testing
    categories = Table(
        "categories",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String(50)),
        Column("description", String(200)),
        UniqueConstraint("name", name="uq_categories_name"),
    )

    # Create tables
    metadata.create_all(sqlite_engine)

    return {"users": users, "categories": categories}


class TestBulkUpsert:
    """Test bulk upsert functionality."""

    def test_bulk_upsert_insert_new_rows(self, sqlite_engine, test_tables):
        """Test bulk upsert with all new rows."""
        users = test_tables["users"]

        rows = [
            {"name": "John Doe", "email": "john@example.com"},
            {"name": "Jane Smith", "email": "jane@example.com"},
            {"name": "Bob Johnson", "email": "bob@example.com"},
        ]

        # Now works with SQLite through GenericStrategy
        result = bulk_upsert(sqlite_engine, users, rows)
        assert result.attempted_rows == 3
        assert result.affected_rows == 3

    def test_bulk_upsert_empty_rows(self, sqlite_engine, test_tables):
        """Test bulk upsert with empty rows list."""
        users = test_tables["users"]

        result = bulk_upsert(sqlite_engine, users, [])
        assert result.attempted_rows == 0
        assert result.affected_rows == 0

    def test_bulk_upsert_invalid_rows(self, sqlite_engine, test_tables):
        """Test bulk upsert with invalid rows data."""
        users = test_tables["users"]

        with pytest.raises(ValueError, match="rows must be a list of dictionaries"):
            bulk_upsert(sqlite_engine, users, "invalid")

        with pytest.raises(ValueError, match="rows must be a list of dictionaries"):
            bulk_upsert(sqlite_engine, users, [1, 2, 3])

    def test_bulk_upsert_parameters(self, sqlite_engine, test_tables):
        """Test bulk upsert with deprecated parameters."""
        users = test_tables["users"]

        # Should handle deprecated parameters gracefully
        with pytest.raises(
            (ImportError, Exception)
        ):  # Will fail on SQLite, but parameters are handled
            bulk_upsert(
                sqlite_engine,
                users,
                [{"name": "Test", "email": "test@example.com"}],
                conflict_columns=["email"],
                update_columns=["name"],
            )


class TestGetOrCreate:
    """Test get_or_create functionality."""

    def test_get_or_create_new_record(self, sqlite_engine, test_tables):
        """Test get_or_create with new record."""
        categories = test_tables["categories"]

        with sqlite_engine.begin() as conn:
            category_id = get_or_create(
                conn, categories, name="Rock", description="Rock music genre"
            )

            assert isinstance(category_id, int)
            assert category_id > 0

            # Verify record was created
            result = conn.execute(
                select(categories).where(categories.c.id == category_id)
            ).first()

            assert result is not None
            assert result.name == "Rock"
            assert result.description == "Rock music genre"

    def test_get_or_create_existing_record(self, sqlite_engine, test_tables):
        """Test get_or_create with existing record."""
        categories = test_tables["categories"]

        with sqlite_engine.begin() as conn:
            # Create initial record
            first_id = get_or_create(
                conn, categories, name="Pop", description="Pop music genre"
            )

            # Try to create same record again
            second_id = get_or_create(
                conn, categories, name="Pop", description="Pop music genre"
            )

            # Should return same ID
            assert first_id == second_id

            # Verify only one record exists
            result = conn.execute(
                select(categories.c.id).where(categories.c.name == "Pop")
            ).fetchall()
            assert len(result) == 1

    def test_get_or_create_partial_match(self, sqlite_engine, test_tables):
        """Test get_or_create with partial field matching."""
        categories = test_tables["categories"]

        with sqlite_engine.begin() as conn:
            # Create record with specific description
            get_or_create(conn, categories, name="Jazz", description="Traditional jazz")

            # Try to get record with different description but same name
            # This should fail due to unique constraint on name
            with pytest.raises(Exception):  # SQLite will raise IntegrityError
                get_or_create(conn, categories, name="Jazz", description="Modern jazz")

    def test_get_or_create_no_primary_key(self, sqlite_engine):
        """Test get_or_create with table that has no primary key."""
        metadata = MetaData()

        # Table without primary key
        no_pk_table = Table(
            "no_pk", metadata, Column("name", String(50)), Column("value", String(100))
        )

        metadata.create_all(sqlite_engine)

        with sqlite_engine.begin() as conn:
            with pytest.raises(
                ValueError, match="must have exactly one primary key column"
            ):
                get_or_create(conn, no_pk_table, name="test", value="value")

    def test_get_or_create_composite_primary_key(self, sqlite_engine):
        """Test get_or_create with composite primary key."""
        metadata = MetaData()

        # Table with composite primary key
        composite_pk_table = Table(
            "composite_pk",
            metadata,
            Column("id1", Integer, primary_key=True),
            Column("id2", Integer, primary_key=True),
            Column("name", String(50)),
        )

        metadata.create_all(sqlite_engine)

        with sqlite_engine.begin() as conn:
            with pytest.raises(
                ValueError, match="must have exactly one primary key column"
            ):
                get_or_create(conn, composite_pk_table, id1=1, id2=2, name="test")


class TestBatchGetOrCreate:
    """Test batch get_or_create functionality."""

    def test_batch_get_or_create_new_records(self, sqlite_engine, test_tables):
        """Test batch get_or_create with all new records."""
        categories = test_tables["categories"]

        rows = [
            {"name": "Rock", "description": "Rock music"},
            {"name": "Pop", "description": "Pop music"},
            {"name": "Jazz", "description": "Jazz music"},
        ]

        with sqlite_engine.begin() as conn:
            ids = batch_get_or_create(conn, categories, rows)

            assert len(ids) == 3
            assert all(isinstance(id_val, int) and id_val > 0 for id_val in ids)
            assert len(set(ids)) == 3  # All IDs should be unique

    def test_batch_get_or_create_mixed_records(self, sqlite_engine, test_tables):
        """Test batch get_or_create with mix of new and existing records."""
        categories = test_tables["categories"]

        with sqlite_engine.begin() as conn:
            # Create one record first
            existing_id = get_or_create(
                conn, categories, name="Rock", description="Rock music"
            )

            # Batch with mix of new and existing
            rows = [
                {"name": "Rock", "description": "Rock music"},  # Existing
                {"name": "Pop", "description": "Pop music"},  # New
                {"name": "Jazz", "description": "Jazz music"},  # New
            ]

            ids = batch_get_or_create(conn, categories, rows)

            assert len(ids) == 3
            assert ids[0] == existing_id  # Should return existing ID
            assert ids[1] != existing_id  # Should be new ID
            assert ids[2] != existing_id  # Should be new ID
            assert ids[1] != ids[2]  # New IDs should be different

    def test_batch_get_or_create_empty_rows(self, sqlite_engine, test_tables):
        """Test batch get_or_create with empty rows."""
        categories = test_tables["categories"]

        with sqlite_engine.begin() as conn:
            ids = batch_get_or_create(conn, categories, [])
            assert ids == []

    def test_batch_get_or_create_custom_batch_size(self, sqlite_engine, test_tables):
        """Test batch get_or_create with custom batch size."""
        categories = test_tables["categories"]

        rows = [
            {"name": f"Genre{i}", "description": f"Genre {i} music"} for i in range(10)
        ]

        with sqlite_engine.begin() as conn:
            ids = batch_get_or_create(conn, categories, rows, batch_size=3)

            assert len(ids) == 10
            assert all(isinstance(id_val, int) and id_val > 0 for id_val in ids)


class TestUpsertSingle:
    """Test single row upsert functionality."""

    def test_upsert_single_mysql_not_available(self, sqlite_engine, test_tables):
        """Test upsert_single when MySQL dialect is not available."""
        users = test_tables["users"]

        with sqlite_engine.begin() as conn, pytest.raises((ImportError, Exception)):
            upsert_single(
                conn, users, {"name": "John Doe", "email": "john@example.com"}
            )


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_connection_handling(self, sqlite_engine, test_tables):
        """Test proper connection handling."""
        categories = test_tables["categories"]

        # Test with closed connection should raise appropriate error
        conn = sqlite_engine.connect()
        conn.close()

        with pytest.raises(Exception):  # Should raise some database error
            get_or_create(conn, categories, name="Test", description="Test")

    def test_transaction_rollback(self, sqlite_engine, test_tables):
        """Test behavior with transaction rollback."""
        categories = test_tables["categories"]

        try:
            with sqlite_engine.begin() as conn:
                # Create a record
                get_or_create(
                    conn, categories, name="Temp", description="Temporary category"
                )

                # Force an error to trigger rollback
                raise Exception("Forced error")

        except Exception:
            pass  # Expected

        # Verify record was rolled back
        with sqlite_engine.begin() as conn:
            result = conn.execute(
                select(categories).where(categories.c.name == "Temp")
            ).first()

            assert result is None


class TestIntegration:
    """Integration tests with realistic scenarios."""

    def test_etl_pipeline_simulation(self, sqlite_engine, test_tables):
        """Test simulating an ETL pipeline with reference data."""
        categories = test_tables["categories"]
        users = test_tables["users"]

        # Simulate ETL process
        with sqlite_engine.begin() as conn:
            # Step 1: Ensure reference data exists
            genre_data = [
                {"name": "Rock", "description": "Rock music"},
                {"name": "Pop", "description": "Pop music"},
                {"name": "Jazz", "description": "Jazz music"},
            ]

            genre_ids = batch_get_or_create(conn, categories, genre_data)
            assert len(genre_ids) == 3

            # Step 2: Create user data referencing genres
            # (In real scenario, users table would have foreign key to categories)
            user_data = [
                {"name": "John", "email": "john@example.com"},
                {"name": "Jane", "email": "jane@example.com"},
            ]

            for user in user_data:
                user_id = get_or_create(conn, users, **user)
                assert user_id > 0

            # Step 3: Verify all data was created
            category_result = conn.execute(select(categories.c.id)).fetchall()
            user_result = conn.execute(select(users.c.id)).fetchall()

            assert len(category_result) == 3
            assert len(user_result) == 2

    def test_duplicate_handling(self, sqlite_engine, test_tables):
        """Test handling of duplicate data in various scenarios."""
        categories = test_tables["categories"]

        with sqlite_engine.begin() as conn:
            # Create initial data
            initial_data = [
                {"name": "Rock", "description": "Rock music"},
                {"name": "Pop", "description": "Pop music"},
            ]

            first_ids = batch_get_or_create(conn, categories, initial_data)

            # Try to create same data again
            second_ids = batch_get_or_create(conn, categories, initial_data)

            # Should return same IDs
            assert first_ids == second_ids

            # Verify no duplicates were created
            total_result = conn.execute(select(categories.c.id)).fetchall()
            assert len(total_result) == 2

    def test_performance_characteristics(self, sqlite_engine, test_tables):
        """Test performance characteristics with larger datasets."""
        categories = test_tables["categories"]

        # Create larger dataset
        large_dataset = [
            {"name": f"Genre{i}", "description": f"Genre {i} description"}
            for i in range(100)
        ]

        with sqlite_engine.begin() as conn:
            import time

            start_time = time.perf_counter()
            ids = batch_get_or_create(conn, categories, large_dataset)
            end_time = time.perf_counter()

            # Verify all records were processed
            assert len(ids) == 100
            assert all(isinstance(id_val, int) and id_val > 0 for id_val in ids)

            # Performance should be reasonable (less than 1 second for 100 records)
            elapsed_time = end_time - start_time
            assert (
                elapsed_time < 1.0
            ), f"Operation took {elapsed_time:.2f}s, expected < 1.0s"

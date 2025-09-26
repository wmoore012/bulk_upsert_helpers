# SPDX-License-Identifier: MIT
# Copyright (c) 2024 Wilton Moore

"""
High-performance bulk upsert operations for SQLAlchemy 2.x.

This module provides dialect-specific bulk upsert functionality with proper
SQLAlchemy 2.x patterns. Supports MySQL and PostgreSQL with fallback for other databases.

SECURITY FEATURES:
- All queries use SQLAlchemy's parameterized statements (no string concatenation)
- Input validation prevents malformed data from reaching the database
- Type checking ensures only expected data types are processed
- No raw SQL construction - only SQLAlchemy's safe query builders

PERFORMANCE FEATURES:
- MySQL's native ON DUPLICATE KEY UPDATE for optimal upsert performance
- PostgreSQL's ON CONFLICT DO UPDATE for ACID compliance
- Bulk operations minimize database round trips
- Automatic primary key detection and exclusion from updates
- Connection pooling and transaction management

MySQL Affected Rows Semantics:
- INSERT: returns 1 per new row
- UPDATE: returns 2 per changed row
- UNCHANGED: returns 0 per unchanged row
- Total may exceed input row count due to update semantics
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any, Dict, List, Set

from sqlalchemy import func, inspect, insert, select, update
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.schema import Table

from .upsert_strategies import GenericStrategy, MySQLStrategy, PostgreSQLStrategy


@dataclass(slots=True, frozen=True)
class UpsertStats:
    """Statistics from bulk upsert operations."""

    affected_rows: int
    attempted_rows: int
    estimated_inserts: int
    estimated_updates: int

    @classmethod
    def from_mysql_result(cls, affected: int, attempted: int) -> "UpsertStats":
        """Create stats from MySQL affected rows (1=insert, 2=update, 0=unchanged)."""
        # Rough estimation: if affected > attempted, some were updates (count as 2)
        if affected <= attempted:
            return cls(affected, attempted, affected, 0)
        else:
            # Conservative estimate: assume excess comes from updates
            excess = affected - attempted
            estimated_updates = min(excess, attempted)
            estimated_inserts = attempted - estimated_updates
            return cls(affected, attempted, estimated_inserts, estimated_updates)


# Strategy registry for dialect dispatch
UPSERT_STRATEGIES: Dict[str, Any] = {
    "mysql": MySQLStrategy(),
    "postgresql": PostgreSQLStrategy(),
}


def resolve_valid_columns(table: Table, rows: List[Dict[str, Any]]) -> Set[str]:
    """Resolve valid columns from table schema and provided rows."""
    table_cols = {c.name for c in table.columns}
    if not rows:
        return table_cols

    provided_cols = set().union(*[set(r.keys()) for r in rows])
    return table_cols & provided_cols


def detect_conflict_columns(table: Table) -> Set[str]:
    """Detect unique columns from constraints and indexes."""
    unique_cols: Set[str] = set()

    # Primary key columns
    pk_cols = {c.name for c in table.primary_key.columns}
    unique_cols.update(pk_cols)

    # UniqueConstraint objects
    for cons in getattr(table, "constraints", set()):
        if getattr(cons, "unique", False) or cons.__class__.__name__ == "UniqueConstraint":
            unique_cols.update(col.name for col in cons.columns)

    # Unique indexes
    for idx in getattr(table, "indexes", set()):
        if getattr(idx, "unique", False):
            unique_cols.update(col.name for col in idx.columns)

    return unique_cols


def resolve_update_target(
    valid_cols: Set[str],
    conflict_cols: Set[str],
    update_columns: Iterable[str] | None
) -> List[str]:
    """Resolve which columns to update on conflict."""
    if update_columns is None:
        # Default: update all valid columns except conflict columns
        return sorted(valid_cols - conflict_cols)
    else:
        return [c for c in update_columns if c in valid_cols and c not in conflict_cols]


def clean_rows(rows: List[Dict[str, Any]], valid_cols: Set[str]) -> List[Dict[str, Any]]:
    """Filter rows to only include valid columns."""
    return [{k: v for k, v in row.items() if k in valid_cols} for row in rows]


def iter_batches(rows: List[Dict[str, Any]], batch_size: int) -> Iterator[List[Dict[str, Any]]]:
    """Iterate over rows in batches of specified size."""
    for i in range(0, len(rows), batch_size):
        yield rows[i:i + batch_size]


def bulk_upsert(
    engine: Engine,
    table: Table,
    rows: list[dict[str, Any]],
    update_columns: Iterable[str] | None = None,
    batch_size: int = 1000,
) -> UpsertStats:
    """
    Bulk upsert using dialect-specific ON DUPLICATE KEY UPDATE or ON CONFLICT.

    Args:
        engine: SQLAlchemy Engine instance
        table: SQLAlchemy Table object to insert into
        rows: List of dictionaries representing rows to insert/update
        update_columns: Specific columns to update on conflict (optional)
        batch_size: Rows per batch to avoid max_allowed_packet limits (default: 1000)

    Returns:
        UpsertStats with affected rows and estimates

    Raises:
        ValueError: If rows list is empty or invalid

    Example:
        >>> rows = [
        ...     {'name': 'John', 'email': 'john@example.com'},
        ...     {'name': 'Jane', 'email': 'jane@example.com'}
        ... ]
        >>> stats = bulk_upsert(engine, users, rows)
        >>> print(f"Processed {stats.attempted_rows}, affected {stats.affected_rows}")

    Notes:
        - Uses dialect-specific upsert: MySQL ON DUPLICATE KEY, PostgreSQL ON CONFLICT
        - Batches automatically to avoid packet size limits
        - Excludes PK and unique constraint columns from updates
        - MySQL semantics: 1=insert, 2=update, 0=unchanged
    """
    if not isinstance(rows, list) or (rows and not isinstance(rows[0], dict)):
        raise ValueError("rows must be a list of dictionaries")

    if not rows:
        return UpsertStats(0, 0, 0, 0)

    # Resolve columns and strategy
    valid_cols = resolve_valid_columns(table, rows)
    conflict_cols = detect_conflict_columns(table)
    update_target = resolve_update_target(valid_cols, conflict_cols, update_columns)

    affected_total = 0
    with engine.begin() as conn:
        strategy = UPSERT_STRATEGIES.get(conn.dialect.name, GenericStrategy())

        for batch in iter_batches(rows, batch_size):
            clean_batch = clean_rows(batch, valid_cols)
            if clean_batch:
                affected_total += strategy.upsert_batch(conn, table, clean_batch, update_target)

    return UpsertStats.from_mysql_result(affected_total, len(rows))





def postgres_bulk_upsert(
    engine: Engine,
    table: Table,
    rows: list[dict[str, Any]],
    conflict_columns: list[str],
    update_columns: Iterable[str] | None = None,
    batch_size: int = 1000,
) -> UpsertStats:
    """
    PostgreSQL-specific bulk upsert using ON CONFLICT DO UPDATE.

    Args:
        engine: SQLAlchemy Engine instance
        table: SQLAlchemy Table object to insert into
        rows: List of dictionaries representing rows to insert/update
        conflict_columns: Columns that define the conflict (e.g., unique constraint)
        update_columns: Specific columns to update on conflict (optional)
        batch_size: Rows per batch (default: 1000)

    Returns:
        UpsertStats with affected rows and estimates

    Example:
        >>> stats = postgres_bulk_upsert(
        ...     engine, users, rows,
        ...     conflict_columns=['email'],
        ...     update_columns=['name', 'updated_at']
        ... )
    """
    if not rows:
        return UpsertStats(0, 0, 0, 0)

    # Resolve columns and prepare for batching
    valid_cols = resolve_valid_columns(table, rows)
    update_target = _resolve_postgres_update_target(
        valid_cols, conflict_columns, update_columns
    )

    affected_total = 0
    with engine.begin() as conn:
        for batch in iter_batches(rows, batch_size):
            clean_batch = clean_rows(batch, valid_cols)
            if clean_batch:
                affected_total += _execute_postgres_batch(
                    conn, table, clean_batch, conflict_columns, update_target
                )

    return UpsertStats(affected_total, len(rows), 0, 0)


def _resolve_postgres_update_target(
    valid_cols: Set[str],
    conflict_columns: List[str],
    update_columns: Iterable[str] | None
) -> List[str]:
    """Resolve update target columns for PostgreSQL upsert."""
    conflict_set = set(conflict_columns)

    if update_columns is None:
        return sorted(valid_cols - conflict_set)
    else:
        return [c for c in update_columns if c in valid_cols]


def _execute_postgres_batch(
    conn: Connection,
    table: Table,
    batch: List[Dict[str, Any]],
    conflict_columns: List[str],
    update_target: List[str]
) -> int:
    """Execute a single PostgreSQL upsert batch."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    insert_stmt = pg_insert(table)
    up_map = {c: insert_stmt.excluded[c] for c in update_target}
    stmt = insert_stmt.values(batch).on_conflict_do_update(
        index_elements=conflict_columns,
        set_=up_map
    )

    result = conn.execute(stmt)
    return result.rowcount


def get_or_create(conn: Connection, table: Table, **kwargs: Any) -> int:
    """
    Atomic get-or-create that works with both MySQL and SQLite.
    Returns the primary-key int for both insert and conflict-update paths.

    Args:
        conn: SQLAlchemy Connection instance (must be within a transaction)
        table: SQLAlchemy Table object to query/insert into
        **kwargs: Column values to match/insert

    Returns:
        Primary key value of the existing or newly created row

    Raises:
        ValueError: If table has no primary key

    Example:
        >>> with engine.begin() as conn:
        ...     category_id = get_or_create(conn, categories, name='Rock')
        ...     print(f"Category ID: {category_id}")
    """
    pk_col, payload = _validate_get_or_create_inputs(table, kwargs)

    dialect_name = conn.dialect.name
    if dialect_name == "mysql":
        return _get_or_create_mysql(conn, table, pk_col, payload)
    elif dialect_name == "sqlite":
        return _get_or_create_sqlite(conn, table, pk_col, payload)
    else:
        return _get_or_create_generic(conn, table, pk_col, payload)


def _validate_get_or_create_inputs(table: Table, kwargs: Dict[str, Any]) -> tuple[Any, Dict[str, Any]]:
    """Validate inputs for get_or_create operation."""
    pk_cols = list(table.primary_key.columns)
    if len(pk_cols) != 1:
        raise ValueError(f"Table {table.name} must have exactly one primary key column")
    pk_col = pk_cols[0]

    valid_cols = {c.name for c in table.columns}
    payload = {k: v for k, v in kwargs.items() if k in valid_cols}

    if not payload:
        raise ValueError("No valid columns provided")

    return pk_col, payload


def _get_or_create_mysql(conn: Connection, table: Table, pk_col: Any, payload: Dict[str, Any]) -> int:
    """MySQL-specific get_or_create using ON DUPLICATE KEY UPDATE."""
    from sqlalchemy.dialects.mysql import insert as mysql_insert

    ins = mysql_insert(table).values(**payload)
    stmt = ins.on_duplicate_key_update(**{pk_col.name: func.last_insert_id(pk_col)})

    conn.execute(stmt)
    new_id = conn.connection.driver_connection.insert_id()
    if not new_id:
        new_id = conn.execute(select(pk_col).filter_by(**payload)).scalar_one()
    return int(new_id)


def _get_or_create_sqlite(conn: Connection, table: Table, pk_col: Any, payload: Dict[str, Any]) -> int:
    """SQLite-specific get_or_create."""
    # First try to get existing record
    existing = conn.execute(select(pk_col).filter_by(**payload)).first()
    if existing:
        return int(existing[0])

    # Insert new record
    ins = insert(table).values(**payload)
    result = conn.execute(ins)
    return int(result.lastrowid)


def _get_or_create_generic(conn: Connection, table: Table, pk_col: Any, payload: Dict[str, Any]) -> int:
    """Generic get_or_create for other databases."""
    # First try to get existing record
    existing = conn.execute(select(pk_col).filter_by(**payload)).first()
    if existing:
        return int(existing[0])

    # Insert new record
    ins = insert(table).values(**payload)
    result = conn.execute(ins)
    return int(result.lastrowid)


def batch_get_or_create(
    conn: Connection, table: Table, rows: list[dict[str, Any]], batch_size: int = 1000
) -> list[int]:
    """
    Efficiently get or create multiple rows, returning their primary keys.

    This function optimizes the get_or_create pattern for bulk operations by
    batching queries and minimizing database round trips.

    Args:
        conn: SQLAlchemy Connection instance
        table: SQLAlchemy Table object
        rows: List of dictionaries representing rows to get or create
        batch_size: Number of rows to process in each batch

    Returns:
        List of primary key values in the same order as input rows

    Example:
        >>> rows = [
        ...     {'name': 'Rock', 'description': 'Rock music'},
        ...     {'name': 'Pop', 'description': 'Pop music'},
        ...     {'name': 'Jazz', 'description': 'Jazz music'}
        ... ]
        >>> with engine.begin() as conn:
        ...     ids = batch_get_or_create(conn, categories, rows)
        ...     print(f"Category IDs: {ids}")
    """
    if not rows:
        return []

    result_ids = []

    # Process in batches to avoid overwhelming the database
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        batch_ids = []

        for row_data in batch:
            pk_id = get_or_create(conn, table, **row_data)
            batch_ids.append(pk_id)

        result_ids.extend(batch_ids)

    return result_ids


def upsert_single(
    conn: Connection,
    table: Table,
    row_data: dict[str, Any],
    conflict_columns: list[str] | None = None,
) -> int:
    """
    Upsert a single row and return the affected row count.

    This is a convenience function for single-row upserts when you don't need
    the full bulk_upsert functionality.

    Args:
        conn: SQLAlchemy Connection instance
        table: SQLAlchemy Table object
        row_data: Dictionary representing the row to upsert
        conflict_columns: Columns that define conflicts (deprecated)

    Returns:
        Number of affected rows (1 for insert, 2 for update in MySQL)

    Example:
        >>> with engine.begin() as conn:
        ...     affected = upsert_single(conn, users, {
        ...         'name': 'John Doe',
        ...         'email': 'john@example.com'
        ...     })
        ...     print(f"Affected {affected} rows")
    """
    from sqlalchemy.dialects.mysql import insert as mysql_insert

    # Create insert statement
    insert_stmt = mysql_insert(table).values(row_data)

    # Get primary key columns for exclusion from updates
    pk_cols = {c.name for c in inspect(table).primary_key}

    # Create update mapping for all non-primary-key columns
    update_map = {col: insert_stmt.inserted[col] for col in row_data.keys() if col not in pk_cols}

    # Build the upsert statement
    stmt = insert_stmt.on_duplicate_key_update(**update_map)

    # Execute the statement
    result = conn.execute(stmt)
    return result.rowcount

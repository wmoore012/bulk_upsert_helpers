# SPDX-License-Identifier: MIT
# Copyright (c) 2024 Wilton Moore

"""
Database-specific upsert strategies.

This module implements the strategy pattern to handle dialect-specific
upsert operations, reducing complexity in the main upsert functions.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.schema import Table


class UpsertStrategy(ABC):
    """Abstract base class for database-specific upsert strategies."""

    @abstractmethod
    def upsert_batch(
        self,
        conn: Connection,
        table: Table,
        rows: List[Dict[str, Any]],
        update_cols: List[str]
    ) -> int:
        """Execute a batch upsert and return affected row count."""
        pass


class MySQLStrategy(UpsertStrategy):
    """MySQL-specific upsert using ON DUPLICATE KEY UPDATE."""

    def upsert_batch(
        self,
        conn: Connection,
        table: Table,
        rows: List[Dict[str, Any]],
        update_cols: List[str]
    ) -> int:
        from sqlalchemy.dialects.mysql import insert as mysql_insert

        insert_stmt = mysql_insert(table)
        up_map = {c: insert_stmt.inserted[c] for c in update_cols}
        stmt = insert_stmt.values(rows).on_duplicate_key_update(**up_map)

        result = conn.execute(stmt)
        return result.rowcount


class PostgreSQLStrategy(UpsertStrategy):
    """PostgreSQL-specific upsert using ON CONFLICT DO UPDATE."""

    def upsert_batch(
        self,
        conn: Connection,
        table: Table,
        rows: List[Dict[str, Any]],
        update_cols: List[str]
    ) -> int:
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        insert_stmt = pg_insert(table)

        # Use primary key columns for conflict detection
        pk_cols = [c.name for c in table.primary_key.columns]
        if not pk_cols and rows:
            pk_cols = list(rows[0].keys())

        up_map = {c: insert_stmt.excluded[c] for c in update_cols}
        stmt = insert_stmt.values(rows).on_conflict_do_update(
            index_elements=pk_cols,
            set_=up_map
        )

        result = conn.execute(stmt)
        return result.rowcount


class GenericStrategy(UpsertStrategy):
    """Generic fallback strategy using individual operations."""

    def upsert_batch(
        self,
        conn: Connection,
        table: Table,
        rows: List[Dict[str, Any]],
        update_cols: List[str]
    ) -> int:
        affected = 0
        pk_cols = [c.name for c in table.primary_key.columns]

        for row_data in rows:
            affected += self._upsert_single_row(
                conn, table, row_data, update_cols, pk_cols
            )

        return affected

    def _upsert_single_row(
        self,
        conn: Connection,
        table: Table,
        row_data: Dict[str, Any],
        update_cols: List[str],
        pk_cols: List[str]
    ) -> int:
        """Upsert a single row using select-then-insert/update pattern."""
        where_clause = {k: v for k, v in row_data.items() if k in pk_cols}
        if where_clause:
            existing = self._select_existing(conn, table, where_clause)
            if existing:
                return self._update_existing(
                    conn, table, row_data, update_cols, where_clause
                )

        conn.execute(insert(table).values(**row_data))
        return 1

    def _select_existing(
        self,
        conn: Connection,
        table: Table,
        where_clause: Dict[str, Any]
    ) -> Any:
        """Check if a row exists with the given where clause."""
        conditions = [table.c[k] == v for k, v in where_clause.items()]
        stmt = select(table).where(*conditions)
        return conn.execute(stmt).first()

    def _update_existing(
        self,
        conn: Connection,
        table: Table,
        row_data: Dict[str, Any],
        update_cols: List[str],
        where_clause: Dict[str, Any]
    ) -> int:
        """Update an existing row."""
        update_data = {k: v for k, v in row_data.items() if k in update_cols}
        if not update_data:
            return 0

        conditions = [table.c[k] == v for k, v in where_clause.items()]
        stmt = update(table).where(*conditions).values(**update_data)
        result = conn.execute(stmt)
        return result.rowcount

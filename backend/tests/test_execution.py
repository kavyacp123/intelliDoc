"""
Unit tests for the Execution Engine.

End-to-end tests that:
  1. Create a DuckDB table with sample data
  2. Execute queries via the execution engine
  3. Verify JSON results are correct
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import duckdb

from app.services.execution_service import QueryExecutionError, execute_query


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    """
    Create an in-memory DuckDB with sample data for each test.

    Monkeypatches both the _connection variable and the get_connection
    function so the execution engine uses our test connection.
    """
    conn = duckdb.connect(":memory:")

    # Create and populate a test table
    conn.execute("""
        CREATE TABLE test_dataset (
            tenant_id VARCHAR,
            region VARCHAR,
            category VARCHAR,
            revenue DOUBLE,
            expense DOUBLE,
            quantity INTEGER,
            date DATE
        )
    """)

    conn.execute("""
        INSERT INTO test_dataset VALUES
        ('user1', 'East', 'Electronics', 15000, 9000, 50, '2024-01-15'),
        ('user1', 'West', 'Clothing', 8500, 5100, 120, '2024-02-22'),
        ('user1', 'East', 'Food', 7500, 4500, 180, '2024-03-01'),
        ('user1', 'North', 'Electronics', 16500, 9900, 55, '2024-05-02'),
        ('user2', 'South', 'Clothing', 6500, 3900, 110, '2024-06-22'),
        ('user2', 'West', 'Food', 9000, 5400, 190, '2024-06-01')
    """)

    # Monkeypatch both the module-level _connection AND the get_connection function
    import app.core.database as db_module
    monkeypatch.setattr(db_module, "_connection", conn)
    monkeypatch.setattr(db_module, "get_connection", lambda: conn)

    yield conn
    conn.close()


class TestExecuteQuery:
    """Tests for the execute_query function."""

    def test_basic_select(self):
        """Basic SELECT should return list of dicts."""
        results = execute_query(
            "SELECT region, revenue FROM test_dataset WHERE tenant_id = 'user1' LIMIT 10"
        )
        assert isinstance(results, list)
        assert len(results) == 4  # user1 has 4 rows
        assert "region" in results[0]
        assert "revenue" in results[0]

    def test_aggregation_query(self):
        """SUM aggregation should return correct totals."""
        results = execute_query(
            "SELECT region, SUM(revenue) AS revenue "
            "FROM test_dataset "
            "WHERE tenant_id = 'user1' "
            "GROUP BY region"
        )
        assert isinstance(results, list)
        # user1 has East (15000 + 7500) and West (8500) and North (16500)
        region_map = {r["region"]: r["revenue"] for r in results}
        assert region_map["East"] == 22500.0
        assert region_map["West"] == 8500.0
        assert region_map["North"] == 16500.0

    def test_tenant_isolation(self):
        """Queries scoped to user1 should not include user2 data."""
        results = execute_query(
            "SELECT COUNT(*) AS cnt FROM test_dataset WHERE tenant_id = 'user1'"
        )
        assert results[0]["cnt"] == 4

    def test_tenant2_isolation(self):
        """Queries scoped to user2 should not include user1 data."""
        results = execute_query(
            "SELECT COUNT(*) AS cnt FROM test_dataset WHERE tenant_id = 'user2'"
        )
        assert results[0]["cnt"] == 2

    def test_empty_result(self):
        """Query with no matching rows returns empty list."""
        results = execute_query(
            "SELECT * FROM test_dataset WHERE tenant_id = 'nonexistent'"
        )
        assert results == []

    def test_invalid_sql_raises(self):
        """Invalid SQL should raise QueryExecutionError."""
        with pytest.raises(QueryExecutionError):
            execute_query("SELECT * FROM nonexistent_table")

    def test_limit_enforcement(self):
        """LIMIT clause restricts result count."""
        results = execute_query(
            "SELECT * FROM test_dataset WHERE tenant_id = 'user1' LIMIT 2"
        )
        assert len(results) == 2

    def test_json_serializable(self):
        """All result values should be JSON-serializable types."""
        results = execute_query(
            "SELECT region, revenue, quantity, date "
            "FROM test_dataset WHERE tenant_id = 'user1' LIMIT 1"
        )
        assert len(results) == 1
        row = results[0]
        for value in row.values():
            assert isinstance(value, (str, int, float, bool, type(None)))

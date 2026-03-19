"""
Unit tests for the SQL Validator.

Tests that dangerous queries are rejected and safe queries pass.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.validator_service import QueryValidationError, validate_query


class TestValidateQuery:
    """Tests for the validate_query function."""

    # ── Queries that SHOULD be blocked ──

    def test_rejects_drop_table(self):
        """DROP TABLE must be blocked."""
        with pytest.raises(QueryValidationError, match="Dangerous keyword"):
            validate_query("DROP TABLE users")

    def test_rejects_delete(self):
        """DELETE must be blocked."""
        with pytest.raises(QueryValidationError, match="Dangerous keyword"):
            validate_query("DELETE FROM users WHERE 1=1")

    def test_rejects_update(self):
        """UPDATE must be blocked."""
        with pytest.raises(QueryValidationError, match="Dangerous keyword"):
            validate_query("UPDATE users SET email = 'hacked'")

    def test_rejects_insert(self):
        """INSERT must be blocked."""
        with pytest.raises(QueryValidationError, match="Dangerous keyword"):
            validate_query("INSERT INTO users VALUES ('x', 'y', 'z')")

    def test_rejects_alter(self):
        """ALTER must be blocked."""
        with pytest.raises(QueryValidationError, match="Dangerous keyword"):
            validate_query("ALTER TABLE users ADD COLUMN admin BOOLEAN")

    def test_rejects_truncate(self):
        """TRUNCATE must be blocked."""
        with pytest.raises(QueryValidationError, match="Dangerous keyword"):
            validate_query("TRUNCATE TABLE users")

    def test_rejects_create(self):
        """CREATE must be blocked."""
        with pytest.raises(QueryValidationError, match="Dangerous keyword"):
            validate_query("CREATE TABLE hacked (id INT)")

    def test_rejects_grant(self):
        """GRANT must be blocked."""
        with pytest.raises(QueryValidationError, match="Dangerous keyword"):
            validate_query("GRANT ALL ON users TO public")

    def test_rejects_empty_query(self):
        """Empty queries must be rejected."""
        with pytest.raises(QueryValidationError, match="Empty query"):
            validate_query("")

    def test_rejects_disallowed_table(self):
        """Tables not in the allowlist must be blocked."""
        with pytest.raises(QueryValidationError, match="Table not allowed"):
            validate_query(
                "SELECT * FROM secret_table",
                allowed_tables={"safe_table"},
            )

    # ── Queries that SHOULD pass ──

    def test_accepts_valid_select(self):
        """A simple SELECT should pass validation."""
        sql = validate_query(
            "SELECT region, SUM(revenue) FROM dataset_1 GROUP BY region",
            allowed_tables={"dataset_1"},
        )
        assert "SELECT" in sql

    def test_accepts_select_with_where(self):
        """SELECT with WHERE clause should pass."""
        sql = validate_query(
            "SELECT revenue FROM dataset_1 WHERE region = 'East'",
            allowed_tables={"dataset_1"},
        )
        assert "WHERE" in sql

    def test_accepts_select_with_limit(self):
        """SELECT with LIMIT should pass."""
        sql = validate_query(
            "SELECT * FROM dataset_1 LIMIT 100",
            allowed_tables={"dataset_1"},
        )
        assert "LIMIT" in sql

    def test_column_validation(self):
        """Columns not in the allowlist should be blocked."""
        with pytest.raises(QueryValidationError, match="Column not allowed"):
            validate_query(
                "SELECT secret_col FROM dataset_1",
                allowed_tables={"dataset_1"},
                allowed_columns={"revenue", "region"},
            )

    def test_accepts_allowed_columns(self):
        """Columns in the allowlist should pass."""
        sql = validate_query(
            "SELECT region, revenue FROM dataset_1",
            allowed_tables={"dataset_1"},
            allowed_columns={"region", "revenue"},
        )
        assert "region" in sql

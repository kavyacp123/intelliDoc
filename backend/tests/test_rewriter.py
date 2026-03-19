"""
Unit tests for the Query Rewriter.

Tests that tenant_id is correctly injected and LIMIT is enforced.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.rewrite_service import rewrite_query


class TestRewriteQuery:
    """Tests for the rewrite_query function."""

    def test_injects_tenant_filter_no_where(self):
        """Adds WHERE tenant_id when no WHERE exists."""
        sql = "SELECT region, SUM(revenue) FROM dataset_1 GROUP BY region"
        result = rewrite_query(sql, tenant_id="user123", table_name="dataset_1")

        assert "tenant_id = 'user123'" in result
        assert "WHERE" in result

    def test_injects_tenant_filter_with_where(self):
        """Adds AND tenant_id when WHERE already exists."""
        sql = "SELECT region FROM dataset_1 WHERE region = 'East'"
        result = rewrite_query(sql, tenant_id="user123", table_name="dataset_1")

        assert "tenant_id = 'user123'" in result
        assert "AND" in result

    def test_adds_limit_when_missing(self):
        """Adds LIMIT when query has no LIMIT."""
        sql = "SELECT * FROM dataset_1"
        result = rewrite_query(
            sql, tenant_id="user123", table_name="dataset_1", max_limit=500
        )

        assert "LIMIT 500" in result

    def test_caps_existing_limit(self):
        """Reduces LIMIT if it exceeds the maximum."""
        sql = "SELECT * FROM dataset_1 LIMIT 99999"
        result = rewrite_query(
            sql, tenant_id="user123", table_name="dataset_1", max_limit=100
        )

        assert "LIMIT 100" in result

    def test_keeps_reasonable_limit(self):
        """Keeps LIMIT if it's within the maximum."""
        sql = "SELECT * FROM dataset_1 LIMIT 50"
        result = rewrite_query(
            sql, tenant_id="user123", table_name="dataset_1", max_limit=100
        )

        assert "LIMIT 50" in result

    def test_tenant_id_before_group_by(self):
        """WHERE tenant_id should appear before GROUP BY."""
        sql = "SELECT region, SUM(revenue) FROM dataset_1 GROUP BY region"
        result = rewrite_query(sql, tenant_id="user123", table_name="dataset_1")

        where_pos = result.upper().find("WHERE")
        group_pos = result.upper().find("GROUP BY")
        assert where_pos < group_pos

    def test_sql_injection_in_tenant_id(self):
        """Tenant IDs with single quotes should be escaped."""
        sql = "SELECT * FROM dataset_1"
        result = rewrite_query(
            sql, tenant_id="user'; DROP TABLE--", table_name="dataset_1"
        )

        # The single quote should be escaped
        assert "user''; DROP TABLE--" in result
        assert "tenant_id" in result

"""
Unit tests for the Query Builder Engine.

Tests that StructuredIntent is correctly converted to SQL
using the Semantic Layer mappings.
"""

import sys
from pathlib import Path

import pytest

# Ensure the backend is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.query_schema import StructuredIntent
from app.services import semantic_service
from app.services.query_builder_service import build_query


@pytest.fixture(autouse=True)
def load_semantic_config():
    """Ensure the semantic config is loaded before each test."""
    config_path = Path(__file__).resolve().parents[1] / "semantic_config.yaml"
    semantic_service.reload_config(config_path)
    yield
    semantic_service.reload_config(config_path)


class TestBuildQuery:
    """Tests for the build_query function."""

    def test_basic_metric_with_dimension(self):
        """Revenue by region → SELECT region, SUM(revenue) ... GROUP BY ..."""
        intent = StructuredIntent(
            metric="revenue",
            dimension="region",
            table_name="test_table",
        )
        sql = build_query(intent)

        assert "SUM(revenue)" in sql
        assert "region" in sql
        assert "GROUP BY" in sql
        assert "test_table" in sql

    def test_metric_only_no_dimension(self):
        """Total revenue → SELECT SUM(revenue) FROM ... (no GROUP BY)."""
        intent = StructuredIntent(
            metric="revenue",
            table_name="test_table",
        )
        sql = build_query(intent)

        assert "SUM(revenue)" in sql
        assert "GROUP BY" not in sql

    def test_profit_metric(self):
        """Profit uses the formula SUM(revenue - expense)."""
        intent = StructuredIntent(
            metric="profit",
            dimension="region",
            table_name="test_table",
        )
        sql = build_query(intent)

        assert "SUM(revenue - expense)" in sql

    def test_time_dimension(self):
        """Monthly dimension uses DATE_TRUNC."""
        intent = StructuredIntent(
            metric="revenue",
            dimension="month",
            table_name="test_table",
        )
        sql = build_query(intent)

        assert "DATE_TRUNC" in sql
        assert "month" in sql.lower()

    def test_with_filters(self):
        """Filters are added to WHERE clause."""
        intent = StructuredIntent(
            metric="revenue",
            dimension="region",
            filters=[{"column": "category", "op": "=", "value": "Electronics"}],
            table_name="test_table",
        )
        sql = build_query(intent)

        assert "WHERE" in sql
        assert "category" in sql
        assert "Electronics" in sql

    def test_with_time_range(self):
        """Time range filter is added to WHERE clause."""
        intent = StructuredIntent(
            metric="revenue",
            dimension="region",
            time_range="last 6 months",
            table_name="test_table",
        )
        sql = build_query(intent)

        assert "CURRENT_DATE" in sql
        assert "INTERVAL" in sql

    def test_order_count_metric(self):
        """Order count uses COUNT(*)."""
        intent = StructuredIntent(
            metric="order_count",
            dimension="category",
            table_name="test_table",
        )
        sql = build_query(intent)

        assert "COUNT(*)" in sql

    def test_no_table_name_raises(self):
        """Missing table_name should raise ValueError."""
        intent = StructuredIntent(metric="revenue")
        with pytest.raises(ValueError, match="No table_name"):
            build_query(intent)

    def test_unknown_metric_fallback(self):
        """Unknown metric falls back to COUNT(metric_name)."""
        intent = StructuredIntent(
            metric="unknown_metric",
            table_name="test_table",
        )
        sql = build_query(intent)

        assert "COUNT(unknown_metric)" in sql

    def test_ordering_with_dimension(self):
        """Results should be ordered by metric DESC when grouped."""
        intent = StructuredIntent(
            metric="revenue",
            dimension="region",
            table_name="test_table",
        )
        sql = build_query(intent)

        assert "ORDER BY revenue DESC" in sql

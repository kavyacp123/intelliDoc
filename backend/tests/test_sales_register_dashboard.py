import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.sales_register_dashboard import (
    build_sales_register_dashboard,
    export_sales_register_dashboard,
)


@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    conn = duckdb.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE datasets (
            dataset_id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR NOT NULL,
            table_name VARCHAR NOT NULL,
            file_name VARCHAR NOT NULL,
            row_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE dataset_metadata (
            dataset_id VARCHAR NOT NULL,
            column_name VARCHAR NOT NULL,
            column_type VARCHAR NOT NULL,
            distinct_count INTEGER DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE sales_register_test (
            tenant_id VARCHAR,
            date DATE,
            product VARCHAR,
            company VARCHAR,
            customer VARCHAR,
            voucher_no VARCHAR,
            allocated_revenue DOUBLE,
            line_quantity INTEGER,
            payment_term_days DOUBLE
        )
        """
    )
    conn.execute(
        """
        INSERT INTO sales_register_test VALUES
        ('tenant-1', '2024-01-05', 'Citric Acid', 'Acme Co', 'Acme Co', 'INV-001', 1000, 2, 30),
        ('tenant-1', '2024-02-02', 'Citric Acid', 'Acme Co', 'Acme Co', 'INV-002', 900, 1, 15),
        ('tenant-1', '2024-02-15', 'Sodium Chloride', 'Beta Labs', 'Beta Labs', 'INV-003', 1500, 3, 45),
        ('tenant-1', '2024-03-03', 'Potassium Carbonate', 'Gamma Pharma', 'Gamma Pharma', 'INV-004', 2000, 4, 0),
        ('tenant-1', '2024-03-22', 'Citric Acid', 'Acme Co', 'Acme Co', 'INV-005', 700, 1, 30)
        """
    )
    conn.execute(
        """
        INSERT INTO datasets (dataset_id, tenant_id, table_name, file_name, row_count)
        VALUES ('dataset-1', 'tenant-1', 'sales_register_test', 'sales.xlsx', 5)
        """
    )

    for column_name, column_type, distinct_count in [
        ("date", "datetime", 5),
        ("product", "string", 3),
        ("company", "string", 3),
        ("customer", "string", 3),
        ("voucher_no", "string", 5),
        ("allocated_revenue", "float", 5),
        ("line_quantity", "int", 4),
        ("payment_term_days", "float", 4),
    ]:
        conn.execute(
            """
            INSERT INTO dataset_metadata (dataset_id, column_name, column_type, distinct_count)
            VALUES (?, ?, ?, ?)
            """,
            ["dataset-1", column_name, column_type, distinct_count],
        )

    import app.core.database as db_module
    import app.services.schema_service as schema_service_module
    import app.services.execution_service as execution_service_module

    monkeypatch.setattr(db_module, "_connection", conn)
    monkeypatch.setattr(db_module, "get_connection", lambda: conn)
    monkeypatch.setattr(schema_service_module, "get_connection", lambda: conn)
    monkeypatch.setattr(execution_service_module, "get_connection", lambda: conn)

    yield conn
    conn.close()


def test_build_sales_register_dashboard_returns_all_queries():
    dashboard = build_sales_register_dashboard("dataset-1", "tenant-1")

    assert dashboard["title"] == "Sales Register Intelligence Dashboard"
    assert len(dashboard["queries"]) == 10
    assert len(dashboard["summary_cards"]) == 5
    top_products = next(query for query in dashboard["queries"] if query["id"] == "top_products_value")
    assert top_products["data"][0]["product"] == "Citric Acid"


def test_repeat_order_cycle_query_has_rows():
    dashboard = build_sales_register_dashboard("dataset-1", "tenant-1")

    repeat_query = next(query for query in dashboard["queries"] if query["id"] == "repeat_order_cycle")
    assert repeat_query["row_count"] >= 1
    assert repeat_query["data"][0]["customer"] == "Acme Co"


def test_export_sales_register_dashboard_returns_excel_bytes():
    workbook_bytes, file_name = export_sales_register_dashboard("dataset-1", "tenant-1")
    single_bytes, single_name = export_sales_register_dashboard("dataset-1", "tenant-1", query_id="top_products_value")

    assert file_name == "sales_register_dashboard.xlsx"
    assert single_name == "top_products_value.xlsx"
    assert len(workbook_bytes) > 100
    assert len(single_bytes) > 100

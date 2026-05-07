from __future__ import annotations

import io
import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from app.core.database import get_connection
from app.services import execution_service, schema_service

logger = logging.getLogger(__name__)


def _quote(identifier: str) -> str:
    return f'"{identifier}"'


def _has(columns: set[str], name: str) -> bool:
    return name in columns


def _first_available(columns: set[str], *names: str) -> Optional[str]:
    for name in names:
        if name in columns:
            return name
    return None


def _safe_execute(sql: str) -> List[Dict[str, Any]]:
    try:
        return execution_service.execute_query(sql)
    except Exception as exc:
        logger.warning("Sales-register query failed: %s", exc)
        return []


def _sales_register_context(dataset_id: str, tenant_id: str) -> Dict[str, Any]:
    conn = get_connection()
    row = conn.execute(
        "SELECT table_name FROM datasets WHERE dataset_id = ? AND tenant_id = ?",
        [dataset_id, tenant_id],
    ).fetchone()
    if not row:
        raise ValueError("Dataset not found")

    metadata = schema_service.get_dataset_schema(dataset_id)
    if metadata is None:
        raise ValueError("Dataset schema not found")

    columns = {column.name for column in metadata.columns}
    if "date" not in columns or "product" not in columns:
        raise ValueError("This dashboard requires a structured sales-register style dataset with date and product columns.")

    party_col = _first_available(columns, "customer", "company")
    if not party_col:
        raise ValueError("This dashboard requires at least one party column (customer/company).")

    invoice_col = _first_available(columns, "voucher_no", "voucher_ref_no")
    value_col = _first_available(columns, "allocated_revenue", "allocated_gross_total", "revenue", "gross_total")
    quantity_col = _first_available(columns, "quantity", "line_quantity")
    payment_days_col = _first_available(columns, "payment_term_days")
    terms_col = _first_available(columns, "terms_of_payment")
    supplier_col = _first_available(columns, "supplier")

    value_expr = f"COALESCE({_quote(value_col)}, 0)" if value_col else "0"
    quantity_expr = f"COALESCE({_quote(quantity_col)}, 1)" if quantity_col else "1"
    invoice_expr = _quote(invoice_col) if invoice_col else f"CONCAT({_quote(party_col)}, '|', CAST({_quote('date')} AS VARCHAR))"
    payment_days_expr = f"COALESCE({_quote(payment_days_col)}, 999)" if payment_days_col else "999"
    advance_expr = (
        f"(CASE WHEN LOWER(COALESCE({_quote(terms_col)}, '')) LIKE '%advance%' THEN 1 ELSE 0 END)"
        if terms_col
        else "0"
    )

    notes = []
    if supplier_col is None:
        notes.append("Supplier rankings use the available party/customer field because this sales register does not contain a dedicated supplier column.")
    if payment_days_col is None:
        notes.append("Payment-speed analytics fall back to the textual payment term field when possible.")
    notes.append("Product quantity uses the structured line count when no true quantity column is present.")
    notes.append("Monthly collections are estimated from invoice date plus payment terms because receipt transactions are not present in this sales register.")

    return {
        "table_name": row[0],
        "columns": columns,
        "party_col": party_col,
        "supplier_col": supplier_col or party_col,
        "customer_col": party_col,
        "invoice_col": invoice_col,
        "invoice_expr": invoice_expr,
        "value_expr": value_expr,
        "quantity_expr": quantity_expr,
        "payment_days_expr": payment_days_expr,
        "advance_expr": advance_expr,
        "notes": notes,
    }


def _query_definitions(ctx: Dict[str, Any], tenant_id: str) -> List[Dict[str, Any]]:
    table_name = ctx["table_name"]
    party_col = _quote(ctx["party_col"])
    supplier_col = _quote(ctx["supplier_col"])
    customer_col = _quote(ctx["customer_col"])
    value_expr = ctx["value_expr"]
    quantity_expr = ctx["quantity_expr"]
    invoice_expr = ctx["invoice_expr"]
    payment_days_expr = ctx["payment_days_expr"]
    advance_expr = ctx["advance_expr"]
    date_col = _quote("date")
    product_col = _quote("product")
    tenant_filter = f"tenant_id = '{tenant_id}'"

    base_cte = f"""
        WITH base AS (
            SELECT
                {date_col} AS invoice_date,
                STRFTIME(DATE_TRUNC('month', {date_col}), '%Y-%m') AS invoice_month,
                {product_col} AS product,
                {party_col} AS party,
                {customer_col} AS customer,
                {supplier_col} AS supplier,
                {invoice_expr} AS invoice_no,
                {value_expr} AS line_value,
                {quantity_expr} AS line_quantity,
                {payment_days_expr} AS payment_term_days,
                {advance_expr} AS is_advance
            FROM "{table_name}"
            WHERE {tenant_filter}
              AND {date_col} IS NOT NULL
              AND {product_col} IS NOT NULL
        )
    """

    return [
        {
            "id": "top_products_value",
            "title": "Top 10 Product by Value",
            "description": "Ranked by allocated sales value.",
            "chart_type": "bar",
            "label_key": "product",
            "value_key": "total_value",
            "sql": base_cte + """
                SELECT product, ROUND(SUM(line_value), 2) AS total_value, SUM(line_quantity) AS total_quantity
                FROM base
                GROUP BY product
                ORDER BY total_value DESC
                LIMIT 10
            """,
        },
        {
            "id": "top_products_quantity",
            "title": "Top 10 Product by Quantity",
            "description": "Ranked by available quantity or structured line count.",
            "chart_type": "bar",
            "label_key": "product",
            "value_key": "total_quantity",
            "sql": base_cte + """
                SELECT product, SUM(line_quantity) AS total_quantity, ROUND(SUM(line_value), 2) AS total_value
                FROM base
                GROUP BY product
                ORDER BY total_quantity DESC, total_value DESC
                LIMIT 10
            """,
        },
        {
            "id": "top_suppliers_value",
            "title": "Top 10 Supplier by Value",
            "description": "Uses supplier if present, otherwise falls back to party/customer in this sales register.",
            "chart_type": "bar",
            "label_key": "supplier",
            "value_key": "total_value",
            "sql": base_cte + """
                SELECT supplier, ROUND(SUM(line_value), 2) AS total_value, SUM(line_quantity) AS total_quantity
                FROM base
                GROUP BY supplier
                ORDER BY total_value DESC
                LIMIT 10
            """,
        },
        {
            "id": "top_suppliers_quantity",
            "title": "Top 10 Supplier by Quantity",
            "description": "Uses supplier if present, otherwise falls back to party/customer in this sales register.",
            "chart_type": "bar",
            "label_key": "supplier",
            "value_key": "total_quantity",
            "sql": base_cte + """
                SELECT supplier, SUM(line_quantity) AS total_quantity, ROUND(SUM(line_value), 2) AS total_value
                FROM base
                GROUP BY supplier
                ORDER BY total_quantity DESC, total_value DESC
                LIMIT 10
            """,
        },
        {
            "id": "top_customers_value",
            "title": "Top 10 Customer by Value",
            "description": "Top customers ranked by allocated sales value.",
            "chart_type": "bar",
            "label_key": "customer",
            "value_key": "total_value",
            "sql": base_cte + """
                SELECT customer, ROUND(SUM(line_value), 2) AS total_value, COUNT(DISTINCT invoice_no) AS invoices
                FROM base
                GROUP BY customer
                ORDER BY total_value DESC
                LIMIT 10
            """,
        },
        {
            "id": "top_customers_quantity",
            "title": "Top 10 Customer by Quantity",
            "description": "Top customers ranked by quantity or line count.",
            "chart_type": "bar",
            "label_key": "customer",
            "value_key": "total_quantity",
            "sql": base_cte + """
                SELECT customer, SUM(line_quantity) AS total_quantity, ROUND(SUM(line_value), 2) AS total_value
                FROM base
                GROUP BY customer
                ORDER BY total_quantity DESC, total_value DESC
                LIMIT 10
            """,
        },
        {
            "id": "early_payment_parties",
            "title": "Top 10 Party Who Paid Early for Invoice/Advance",
            "description": "Proxy ranking based on advance terms and shortest contractual payment days.",
            "chart_type": "bar",
            "label_key": "party",
            "value_key": "advance_or_fast_score",
            "sql": base_cte + """
                SELECT
                    party,
                    SUM(is_advance) AS advance_invoices,
                    ROUND(AVG(payment_term_days), 1) AS avg_payment_days,
                    ROUND(SUM(line_value), 2) AS total_value,
                    ROUND((SUM(is_advance) * 1000) + (100 - AVG(payment_term_days)), 2) AS advance_or_fast_score
                FROM base
                GROUP BY party
                ORDER BY advance_invoices DESC, avg_payment_days ASC, total_value DESC
                LIMIT 10
            """,
        },
        {
            "id": "best_seller_month_wise",
            "title": "Best Seller Item Month Wise",
            "description": "Highest-value product for each month.",
            "chart_type": "bar",
            "label_key": "invoice_month",
            "value_key": "month_value",
            "sql": base_cte + """
                , ranked AS (
                    SELECT
                        invoice_month,
                        product,
                        ROUND(SUM(line_value), 2) AS month_value,
                        ROW_NUMBER() OVER (
                            PARTITION BY invoice_month
                            ORDER BY SUM(line_value) DESC, product ASC
                        ) AS rn
                    FROM base
                    GROUP BY invoice_month, product
                )
                SELECT invoice_month, product, month_value
                FROM ranked
                WHERE rn = 1
                ORDER BY invoice_month
            """,
        },
        {
            "id": "sales_vs_expected_receipts",
            "title": "Amount Received from Customers Against Sales Made Month to Month",
            "description": "Expected collections derived from invoice date plus payment terms.",
            "chart_type": "line",
            "label_key": "month",
            "value_key": "sales_booked",
            "secondary_value_key": "expected_receipts",
            "sql": base_cte + """
                , sales_by_month AS (
                    SELECT invoice_month AS month, ROUND(SUM(line_value), 2) AS sales_booked
                    FROM base
                    GROUP BY invoice_month
                ),
                receipts_by_month AS (
                    SELECT
                        STRFTIME(
                            DATE_TRUNC(
                                'month',
                                invoice_date + (CAST(payment_term_days AS INTEGER) * INTERVAL 1 DAY)
                            ),
                            '%Y-%m'
                        ) AS month,
                        ROUND(SUM(line_value), 2) AS expected_receipts
                    FROM base
                    GROUP BY 1
                )
                SELECT
                    COALESCE(s.month, r.month) AS month,
                    COALESCE(s.sales_booked, 0) AS sales_booked,
                    COALESCE(r.expected_receipts, 0) AS expected_receipts,
                    CASE
                        WHEN COALESCE(s.sales_booked, 0) = 0 THEN NULL
                        ELSE ROUND((COALESCE(r.expected_receipts, 0) / s.sales_booked) * 100, 2)
                    END AS receipt_ratio_pct
                FROM sales_by_month s
                FULL OUTER JOIN receipts_by_month r ON s.month = r.month
                ORDER BY month
            """,
        },
        {
            "id": "repeat_order_cycle",
            "title": "Customer Taking Time for Repeating Order",
            "description": "Average days between repeat orders per customer.",
            "chart_type": "bar",
            "label_key": "customer",
            "value_key": "avg_days_between_orders",
            "sql": base_cte + """
                , invoice_dates AS (
                    SELECT DISTINCT customer, invoice_no, invoice_date
                    FROM base
                ),
                gaps AS (
                    SELECT
                        customer,
                        invoice_date,
                        LAG(invoice_date) OVER (PARTITION BY customer ORDER BY invoice_date) AS prev_invoice_date
                    FROM invoice_dates
                )
                SELECT
                    customer,
                    COUNT(*) FILTER (WHERE prev_invoice_date IS NOT NULL) AS repeat_cycles,
                    ROUND(AVG(DATEDIFF('day', prev_invoice_date, invoice_date)), 2) AS avg_days_between_orders,
                    MAX(invoice_date) AS latest_invoice_date
                FROM gaps
                WHERE prev_invoice_date IS NOT NULL
                GROUP BY customer
                ORDER BY avg_days_between_orders DESC, repeat_cycles DESC
                LIMIT 10
            """,
        },
    ]


def _summary_cards(ctx: Dict[str, Any], tenant_id: str) -> List[Dict[str, Any]]:
    table_name = ctx["table_name"]
    party_col = _quote(ctx["customer_col"])
    value_expr = ctx["value_expr"]
    invoice_col = ctx.get("invoice_col")
    tenant_filter = f"tenant_id = '{tenant_id}'"
    invoice_count_expr = f"COUNT(DISTINCT {_quote(invoice_col)})" if invoice_col else "COUNT(*)"

    totals_sql = f"""
        SELECT
            ROUND(SUM({value_expr}), 2) AS total_value,
            COUNT(DISTINCT {_quote('product')}) AS products,
            COUNT(DISTINCT {party_col}) AS customers,
            {invoice_count_expr} AS invoices,
            ROUND(AVG(COALESCE({_quote('payment_term_days')}, 0)), 1) AS avg_payment_days
        FROM "{table_name}"
        WHERE {tenant_filter}
    """
    rows = _safe_execute(totals_sql)
    first = rows[0] if rows else {}
    return [
        {"label": "Total Sales Value", "value": float(first.get("total_value") or 0), "format": "currency"},
        {"label": "Distinct Products", "value": int(first.get("products") or 0), "format": "number"},
        {"label": "Active Customers", "value": int(first.get("customers") or 0), "format": "number"},
        {"label": "Invoices", "value": int(first.get("invoices") or 0), "format": "number"},
        {"label": "Avg Payment Term", "value": float(first.get("avg_payment_days") or 0), "format": "days"},
    ]


def build_sales_register_dashboard(dataset_id: str, tenant_id: str) -> Dict[str, Any]:
    ctx = _sales_register_context(dataset_id, tenant_id)
    query_defs = _query_definitions(ctx, tenant_id)
    query_results = []
    for query_def in query_defs:
        data = _safe_execute(query_def["sql"])
        query_results.append({**query_def, "data": data, "row_count": len(data)})

    return {
        "title": "Sales Register Intelligence Dashboard",
        "notes": ctx["notes"],
        "summary_cards": _summary_cards(ctx, tenant_id),
        "queries": query_results,
    }


def export_sales_register_dashboard(dataset_id: str, tenant_id: str, query_id: Optional[str] = None) -> tuple[bytes, str]:
    dashboard = build_sales_register_dashboard(dataset_id, tenant_id)
    queries = dashboard["queries"]
    if query_id:
        queries = [query for query in queries if query["id"] == query_id]
        if not queries:
            raise ValueError("Unknown dashboard query requested for export.")

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary_df = pd.DataFrame(dashboard["summary_cards"])
        summary_df.to_excel(writer, sheet_name="Summary", index=False)

        for query in queries:
            df = pd.DataFrame(query["data"])
            sheet_name = query["title"][:31]
            if df.empty:
                df = pd.DataFrame([{"message": "No rows returned"}])
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    output.seek(0)
    file_name = "sales_register_dashboard.xlsx" if query_id is None else f"{query_id}.xlsx"
    return output.getvalue(), file_name

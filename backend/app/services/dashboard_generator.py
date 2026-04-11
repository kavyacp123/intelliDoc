"""
CFO-Level Financial Dashboard Generator.

Auto-detects semantic fields from a dataset's schema, generates KPIs,
builds dashboard sections, and runs predefined SQL queries — all without
user input.

The generator:
  1. Inspects the schema to identify revenue, cost, profit, time, and dimension columns
  2. Builds parameterized SQL for each KPI and dashboard section
  3. Executes all queries against DuckDB via execution_service
  4. Returns a fully hydrated JSON structure ready for frontend rendering
"""

import logging
from typing import Any, Dict, List, Optional

from app.models.metadata import TableMetadata
from app.services import execution_service, schema_service
from app.services.semantic_service import infer_semantics

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# 1. FIELD DETECTION
# ─────────────────────────────────────────────

_REVENUE_COLS = ["revenue", "sales", "income", "gross_total", "net_total", "amount", "turnover", "gross_sales"]
_COST_COLS = ["cogs", "cost", "expense", "cost_of_goods_sold", "direct_costs", "total_cost"]
_QUANTITY_COLS = ["quantity", "qty", "units", "volume"]
_TIME_COLS = ["date", "time", "month", "year", "quarter", "timestamp", "period", "created_at", "order_date"]
_DIMENSION_COLS = ["product", "category", "segment", "region", "country", "customer", "city", "state",
                   "department", "channel", "brand", "type", "narration", "particulars", "voucher_type",
                   "party", "group", "area"]


def _detect_field(columns: List[str], candidates: List[str]) -> Optional[str]:
    """Find the first column that matches any candidate keyword."""
    cols_lower = {c.lower(): c for c in columns}
    # Exact match first
    for candidate in candidates:
        if candidate in cols_lower:
            return cols_lower[candidate]
    # Substring match
    for candidate in candidates:
        for col_lower, col_original in cols_lower.items():
            if candidate in col_lower:
                return col_original
    return None


def _detect_all_dimensions(columns: List[str]) -> List[str]:
    """Find all dimension-like columns in the schema."""
    cols_lower = {c.lower(): c for c in columns}
    dims = []
    for col_lower, col_original in cols_lower.items():
        if col_original == "tenant_id":
            continue
        for candidate in _DIMENSION_COLS:
            if candidate in col_lower:
                dims.append(col_original)
                break
    return dims


def detect_semantic_fields(schema: TableMetadata) -> Dict[str, Any]:
    """
    Detect semantic roles for each column in the dataset.
    Returns a dict with keys: revenue, cost, quantity, time, dimensions, all_columns, profit_formula.
    """
    all_cols = [c.name for c in schema.columns if c.name != "tenant_id"]
    numeric_cols = [c.name for c in schema.columns if c.dtype.lower() in ("int", "float", "double", "bigint", "integer", "decimal", "numeric")]

    revenue_col = _detect_field(all_cols, _REVENUE_COLS)
    cost_col = _detect_field(all_cols, _COST_COLS)
    quantity_col = _detect_field(all_cols, _QUANTITY_COLS)
    time_col = _detect_field(all_cols, _TIME_COLS)
    dimensions = _detect_all_dimensions(all_cols)

    # Profit formula
    profit_formula = None
    if revenue_col and cost_col:
        profit_formula = f"({revenue_col} - {cost_col})"

    # Infer semantics using existing service
    semantics = infer_semantics(schema)

    return {
        "revenue": revenue_col,
        "cost": cost_col,
        "quantity": quantity_col,
        "time": time_col,
        "dimensions": dimensions,
        "all_columns": all_cols,
        "numeric_columns": numeric_cols,
        "profit_formula": profit_formula,
        "semantics": semantics,
    }


# ─────────────────────────────────────────────
# 2. QUERY EXECUTION HELPER
# ─────────────────────────────────────────────

def _safe_execute(sql: str) -> List[Dict[str, Any]]:
    """Execute SQL and return results, or empty list on failure."""
    try:
        return execution_service.execute_query(sql)
    except Exception as e:
        logger.warning("Dashboard query failed: %s | SQL: %s", e, sql)
        return []


def _safe_scalar(sql: str, default: float = 0) -> float:
    """Execute SQL and return a single scalar value."""
    data = _safe_execute(sql)
    if data and len(data) > 0:
        first_row = data[0]
        first_value = list(first_row.values())[0]
        try:
            return float(first_value) if first_value is not None else default
        except (ValueError, TypeError):
            return default
    return default


# ─────────────────────────────────────────────
# 3. KPI GENERATION
# ─────────────────────────────────────────────

def _format_currency(value: float) -> str:
    """Format a number as currency string."""
    if abs(value) >= 1_000_000:
        return f"₹{value / 1_000_000:,.2f}M"
    if abs(value) >= 1_000:
        return f"₹{value / 1_000:,.1f}K"
    return f"₹{value:,.2f}"


def _format_pct(value: float) -> str:
    return f"{value:.1f}%"


def generate_kpis(
    table_name: str,
    tenant_id: str,
    fields: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Generate KPI cards with live values from the database."""
    kpis = []
    base_where = f"WHERE tenant_id = '{tenant_id}'"

    # Total Revenue
    if fields["revenue"]:
        val = _safe_scalar(f"SELECT SUM({fields['revenue']}) FROM {table_name} {base_where}")
        kpis.append({
            "name": "Total Revenue",
            "value": _format_currency(val),
            "raw_value": val,
            "icon": "payments",
            "color": "emerald",
            "type": "currency",
        })

    # Total Cost
    if fields["cost"]:
        val = _safe_scalar(f"SELECT SUM({fields['cost']}) FROM {table_name} {base_where}")
        kpis.append({
            "name": "Total Cost",
            "value": _format_currency(val),
            "raw_value": val,
            "icon": "receipt_long",
            "color": "red",
            "type": "currency",
        })

    # Gross Profit
    if fields["profit_formula"]:
        val = _safe_scalar(f"SELECT SUM({fields['profit_formula']}) FROM {table_name} {base_where}")
        kpis.append({
            "name": "Gross Profit",
            "value": _format_currency(val),
            "raw_value": val,
            "icon": "trending_up",
            "color": "blue",
            "type": "currency",
        })

    # Profit Margin %
    if fields["profit_formula"] and fields["revenue"]:
        rev = _safe_scalar(f"SELECT SUM({fields['revenue']}) FROM {table_name} {base_where}")
        profit = _safe_scalar(f"SELECT SUM({fields['profit_formula']}) FROM {table_name} {base_where}")
        margin = (profit / rev * 100) if rev != 0 else 0
        kpis.append({
            "name": "Profit Margin",
            "value": _format_pct(margin),
            "raw_value": margin,
            "icon": "percent",
            "color": "violet",
            "type": "percentage",
        })

    # Total Quantity
    if fields["quantity"]:
        val = _safe_scalar(f"SELECT SUM({fields['quantity']}) FROM {table_name} {base_where}")
        kpis.append({
            "name": "Total Quantity",
            "value": f"{val:,.0f}",
            "raw_value": val,
            "icon": "inventory_2",
            "color": "amber",
            "type": "number",
        })

    # Record Count
    count = _safe_scalar(f"SELECT COUNT(*) FROM {table_name} {base_where}")
    kpis.append({
        "name": "Total Records",
        "value": f"{count:,.0f}",
        "raw_value": count,
        "icon": "database",
        "color": "slate",
        "type": "number",
    })

    return kpis


# ─────────────────────────────────────────────
# 4. SECTION GENERATION
# ─────────────────────────────────────────────

def generate_sections(
    table_name: str,
    tenant_id: str,
    fields: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Generate dashboard sections with live chart data."""
    sections = []
    base_where = f"WHERE tenant_id = '{tenant_id}'"
    primary_dim = fields["dimensions"][0] if fields["dimensions"] else None
    revenue_col = fields["revenue"]
    cost_col = fields["cost"]
    profit_formula = fields["profit_formula"]
    time_col = fields["time"]
    quantity_col = fields["quantity"]

    # ── Section 1: Profitability Overview ──
    if profit_formula and primary_dim:
        sql = f"SELECT {primary_dim}, SUM({profit_formula}) as profit FROM {table_name} {base_where} GROUP BY {primary_dim} ORDER BY profit DESC LIMIT 10"
        data = _safe_execute(sql)
        if data:
            sections.append({
                "title": f"Profit by {primary_dim.replace('_', ' ').title()}",
                "chart_type": "bar",
                "icon": "bar_chart",
                "data": data,
                "x_key": primary_dim,
                "y_key": "profit",
                "color": "#3b82f6",
            })

    # ── Section 2: Revenue by Dimension ──
    if revenue_col and primary_dim:
        sql = f"SELECT {primary_dim}, SUM({revenue_col}) as revenue FROM {table_name} {base_where} GROUP BY {primary_dim} ORDER BY revenue DESC LIMIT 10"
        data = _safe_execute(sql)
        if data:
            sections.append({
                "title": f"Revenue by {primary_dim.replace('_', ' ').title()}",
                "chart_type": "bar",
                "icon": "leaderboard",
                "data": data,
                "x_key": primary_dim,
                "y_key": "revenue",
                "color": "#10b981",
            })

    # ── Section 3: Top 5 Products ──
    if revenue_col and primary_dim:
        sql = f"SELECT {primary_dim}, SUM({revenue_col}) as revenue FROM {table_name} {base_where} GROUP BY {primary_dim} ORDER BY revenue DESC LIMIT 5"
        data = _safe_execute(sql)
        if data:
            sections.append({
                "title": f"Top 5 {primary_dim.replace('_', ' ').title()}s by Revenue",
                "chart_type": "bar",
                "icon": "emoji_events",
                "data": data,
                "x_key": primary_dim,
                "y_key": "revenue",
                "color": "#f59e0b",
            })

    # ── Section 4: Revenue Trend (time-based) ──
    if revenue_col and time_col:
        sql = f"SELECT {time_col}, SUM({revenue_col}) as revenue FROM {table_name} {base_where} GROUP BY {time_col} ORDER BY {time_col} ASC LIMIT 50"
        data = _safe_execute(sql)
        if data:
            sections.append({
                "title": "Revenue Trend",
                "chart_type": "line",
                "icon": "trending_up",
                "data": data,
                "x_key": time_col,
                "y_key": "revenue",
                "color": "#0ea5e9",
            })

    # ── Section 5: Profit Trend (time-based) ──
    if profit_formula and time_col:
        sql = f"SELECT {time_col}, SUM({profit_formula}) as profit FROM {table_name} {base_where} GROUP BY {time_col} ORDER BY {time_col} ASC LIMIT 50"
        data = _safe_execute(sql)
        if data:
            sections.append({
                "title": "Profit Trend",
                "chart_type": "line",
                "icon": "show_chart",
                "data": data,
                "x_key": time_col,
                "y_key": "profit",
                "color": "#8b5cf6",
            })

    # ── Section 6: Cost Breakdown ──
    if cost_col and primary_dim:
        sql = f"SELECT {primary_dim}, SUM({cost_col}) as cost FROM {table_name} {base_where} GROUP BY {primary_dim} ORDER BY cost DESC LIMIT 10"
        data = _safe_execute(sql)
        if data:
            sections.append({
                "title": f"Cost Distribution by {primary_dim.replace('_', ' ').title()}",
                "chart_type": "bar",
                "icon": "pie_chart",
                "data": data,
                "x_key": primary_dim,
                "y_key": "cost",
                "color": "#ef4444",
            })

    # ── Section 7: Additional dimensions (if more than one dimension exists) ──
    for dim in fields["dimensions"][1:3]:  # Up to 2 additional dimensions
        if revenue_col:
            sql = f"SELECT {dim}, SUM({revenue_col}) as revenue FROM {table_name} {base_where} GROUP BY {dim} ORDER BY revenue DESC LIMIT 8"
            data = _safe_execute(sql)
            if data:
                sections.append({
                    "title": f"Revenue by {dim.replace('_', ' ').title()}",
                    "chart_type": "bar",
                    "icon": "analytics",
                    "data": data,
                    "x_key": dim,
                    "y_key": "revenue",
                    "color": "#06b6d4",
                })

    return sections


# ─────────────────────────────────────────────
# 5. PREDEFINED QUERIES
# ─────────────────────────────────────────────

def generate_predefined_queries(
    table_name: str,
    tenant_id: str,
    fields: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Generate the top 10 commonly used financial queries."""
    queries = []
    base_where = f"WHERE tenant_id = '{tenant_id}'"
    revenue_col = fields["revenue"]
    cost_col = fields["cost"]
    profit_formula = fields["profit_formula"]
    time_col = fields["time"]
    quantity_col = fields["quantity"]
    primary_dim = fields["dimensions"][0] if fields["dimensions"] else None

    # 1. Total Revenue
    if revenue_col:
        queries.append({
            "name": "Total Revenue",
            "description": f"Sum of all {revenue_col}",
            "sql": f"SELECT SUM({revenue_col}) as total_revenue FROM {table_name} {base_where}",
            "icon": "payments",
        })

    # 2. Total Profit
    if profit_formula:
        queries.append({
            "name": "Total Profit",
            "description": "Revenue minus Cost",
            "sql": f"SELECT SUM({profit_formula}) as total_profit FROM {table_name} {base_where}",
            "icon": "savings",
        })

    # 3. Profit Margin
    if profit_formula and revenue_col:
        queries.append({
            "name": "Profit Margin %",
            "description": "Profit as % of Revenue",
            "sql": f"SELECT ROUND(SUM({profit_formula}) * 100.0 / NULLIF(SUM({revenue_col}), 0), 2) as margin_pct FROM {table_name} {base_where}",
            "icon": "percent",
        })

    # 4. Revenue by Dimension
    if revenue_col and primary_dim:
        queries.append({
            "name": f"Revenue by {primary_dim.replace('_', ' ').title()}",
            "description": f"Revenue grouped by {primary_dim}",
            "sql": f"SELECT {primary_dim}, SUM({revenue_col}) as revenue FROM {table_name} {base_where} GROUP BY {primary_dim} ORDER BY revenue DESC LIMIT 20",
            "icon": "leaderboard",
        })

    # 5. Profit by Dimension
    if profit_formula and primary_dim:
        queries.append({
            "name": f"Profit by {primary_dim.replace('_', ' ').title()}",
            "description": f"Profit grouped by {primary_dim}",
            "sql": f"SELECT {primary_dim}, SUM({profit_formula}) as profit FROM {table_name} {base_where} GROUP BY {primary_dim} ORDER BY profit DESC LIMIT 20",
            "icon": "bar_chart",
        })

    # 6. Top 5 by Revenue
    if revenue_col and primary_dim:
        queries.append({
            "name": f"Top 5 {primary_dim.replace('_', ' ').title()}s",
            "description": f"Highest revenue {primary_dim}s",
            "sql": f"SELECT {primary_dim}, SUM({revenue_col}) as revenue FROM {table_name} {base_where} GROUP BY {primary_dim} ORDER BY revenue DESC LIMIT 5",
            "icon": "emoji_events",
        })

    # 7. Bottom 5 by Profit
    if profit_formula and primary_dim:
        queries.append({
            "name": f"Bottom 5 {primary_dim.replace('_', ' ').title()}s",
            "description": f"Lowest profit {primary_dim}s",
            "sql": f"SELECT {primary_dim}, SUM({profit_formula}) as profit FROM {table_name} {base_where} GROUP BY {primary_dim} ORDER BY profit ASC LIMIT 5",
            "icon": "trending_down",
        })

    # 8. Revenue Trend
    if revenue_col and time_col:
        queries.append({
            "name": "Revenue Trend",
            "description": f"Revenue over {time_col}",
            "sql": f"SELECT {time_col}, SUM({revenue_col}) as revenue FROM {table_name} {base_where} GROUP BY {time_col} ORDER BY {time_col} ASC",
            "icon": "show_chart",
        })

    # 9. Profit Trend
    if profit_formula and time_col:
        queries.append({
            "name": "Profit Trend",
            "description": f"Profit over {time_col}",
            "sql": f"SELECT {time_col}, SUM({profit_formula}) as profit FROM {table_name} {base_where} GROUP BY {time_col} ORDER BY {time_col} ASC",
            "icon": "timeline",
        })

    # 10. Cost Breakdown
    if cost_col and primary_dim:
        queries.append({
            "name": "Cost Breakdown",
            "description": f"Cost distribution by {primary_dim}",
            "sql": f"SELECT {primary_dim}, SUM({cost_col}) as cost FROM {table_name} {base_where} GROUP BY {primary_dim} ORDER BY cost DESC LIMIT 10",
            "icon": "pie_chart",
        })

    # Fill remaining slots with quantity/count queries
    if quantity_col and primary_dim and len(queries) < 10:
        queries.append({
            "name": f"Quantity by {primary_dim.replace('_', ' ').title()}",
            "description": f"Total quantity per {primary_dim}",
            "sql": f"SELECT {primary_dim}, SUM({quantity_col}) as total_qty FROM {table_name} {base_where} GROUP BY {primary_dim} ORDER BY total_qty DESC LIMIT 10",
            "icon": "inventory_2",
        })

    if len(queries) < 10:
        queries.append({
            "name": "Record Count",
            "description": "Total number of records",
            "sql": f"SELECT COUNT(*) as total_records FROM {table_name} {base_where}",
            "icon": "database",
        })

    return queries[:10]


# ─────────────────────────────────────────────
# 6. MAIN GENERATOR
# ─────────────────────────────────────────────

def generate_executive_dashboard(
    dataset_id: str,
    tenant_id: str,
) -> Dict[str, Any]:
    """
    Generate a complete CFO-level dashboard configuration for a dataset.

    Returns a fully hydrated JSON with KPI values, chart data, and predefined queries.
    """
    # 1. Get schema
    schema = schema_service.get_dataset_schema(dataset_id)
    if not schema:
        return {"error": "Dataset schema not found", "kpis": [], "sections": [], "predefined_queries": []}

    table_name = schema.table_name

    # 2. Detect semantic fields
    fields = detect_semantic_fields(schema)
    logger.info("Dashboard generator detected fields for %s: revenue=%s, cost=%s, time=%s, dims=%s",
                dataset_id, fields["revenue"], fields["cost"], fields["time"], fields["dimensions"])

    # 3. Generate components
    kpis = generate_kpis(table_name, tenant_id, fields)
    sections = generate_sections(table_name, tenant_id, fields)
    predefined_queries = generate_predefined_queries(table_name, tenant_id, fields)

    # 4. Notes
    notes = []
    if fields["profit_formula"]:
        notes.append(f"Profit computed as: {fields['profit_formula']}")
    else:
        notes.append("No profit formula could be derived (missing revenue or cost columns)")
    if not fields["time"]:
        notes.append("No time column detected — trend sections skipped")
    if not fields["dimensions"]:
        notes.append("No dimension columns detected — breakdown sections skipped")
    notes.append(f"Detected {len(fields['all_columns'])} columns, {len(fields['numeric_columns'])} numeric")

    return {
        "kpis": kpis,
        "sections": sections,
        "predefined_queries": predefined_queries,
        "insight_button": {
            "enabled": True,
            "label": "Generate AI Insights",
            "behavior": "Only generate insights when user clicks this button",
        },
        "notes": notes,
        "detected_fields": {
            "revenue": fields["revenue"],
            "cost": fields["cost"],
            "quantity": fields["quantity"],
            "time": fields["time"],
            "dimensions": fields["dimensions"],
        },
    }

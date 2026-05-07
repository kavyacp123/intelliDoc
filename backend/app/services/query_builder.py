from typing import Dict, List, Optional, Set

from app.models.intent import StepIntent


# Virtual time dimension names that should be resolved to DATE_TRUNC expressions
_TIME_GRANULARITY_MAP = {
    "year": "year", "_year": "year",
    "month": "month", "_month": "month",
    "quarter": "quarter", "_quarter": "quarter",
    "week": "week", "_week": "week",
    "day": "day", "_day": "day",
}


def _render_filter_clause(col: str, val) -> str:
    if isinstance(val, dict):
        parts = []
        op_map = {"gte": ">=", "lte": "<=", "gt": ">", "lt": "<", "eq": "="}
        for key, op in op_map.items():
            if key not in val:
                continue
            raw_val = val[key]
            if raw_val is None:
                continue
            if isinstance(raw_val, (int, float)):
                parts.append(f"{col} {op} {raw_val}")
            else:
                parts.append(f"{col} {op} '{raw_val}'")
        return " AND ".join(parts) if parts else "1=1"

    if isinstance(val, list):
        in_clause = ", ".join([f"'{v}'" for v in val])
        return f"{col} IN ({in_clause})"

    if isinstance(val, str):
        time_clause = _render_time_shortcut(col, val)
        if time_clause:
            return time_clause
        for op in [">=", "<=", ">", "<", "="]:
            if val.startswith(op):
                raw_val = val[len(op):].strip()
                if raw_val.replace(".", "", 1).isdigit():
                    return f"{col} {op} {raw_val}"
                return f"{col} {op} '{raw_val}'"

    return f"{col} = '{val}'"


def _render_time_shortcut(col: str, val: str) -> Optional[str]:
    shortcuts = {
        "__last_month": f"{col} >= CURRENT_DATE - INTERVAL '1' MONTH",
        "__this_month": f"DATE_TRUNC('month', {col}) = DATE_TRUNC('month', CURRENT_DATE)",
        "__last_30_days": f"{col} >= CURRENT_DATE - INTERVAL '30' DAY",
        "__last_quarter": f"{col} >= CURRENT_DATE - INTERVAL '3' MONTH",
        "__this_year": f"DATE_TRUNC('year', {col}) = DATE_TRUNC('year', CURRENT_DATE)",
    }
    return shortcuts.get(val)


def _resolve_metric(
    metric: Optional[str],
    semantics: Optional[Dict[str, str]] = None,
) -> str:
    """
    Resolve a metric name to a SQL expression.

    If the metric is a semantic/derived metric (e.g. 'total_revenue'),
    return its formula (e.g. 'SUM(value)') directly if it already contains
    an aggregate function, or wrap it in SUM() if it's a raw expression
    (e.g. 'profit' = 'sales - cogs' → 'SUM(sales - cogs)').
    """
    if not metric or metric == "*":
        return "COUNT(*)"

    # Check if it's a derived semantic metric
    if semantics and metric in semantics:
        formula = semantics[metric]
        # If the formula already contains an aggregate function, use it directly
        if _has_aggregate(formula):
            return formula
        # Otherwise, wrap the raw expression in SUM() for GROUP BY compatibility
        return f"SUM({formula})"

    return f"SUM({metric})"


# Aggregate function keywords to detect in semantic formulas
_AGG_FUNCS = {"SUM(", "COUNT(", "AVG(", "MIN(", "MAX(", "NULLIF("}

def _has_aggregate(expr: str) -> bool:
    """Check if a SQL expression already contains an aggregate function."""
    upper = expr.upper()
    return any(fn in upper for fn in _AGG_FUNCS)


def _resolve_dimension(
    dim: str,
    actual_columns: Optional[List[str]] = None,
) -> tuple[str, str]:
    """
    Resolve a dimension name to (select_expr, group_expr).

    If it's a virtual time dimension like 'month' or '_month', expand it to
    DATE_TRUNC on the first actual date/time column found.
    Otherwise return the dimension name as-is.
    """
    dim_lower = dim.lower()

    # Check if it's a time granularity alias
    if dim_lower in _TIME_GRANULARITY_MAP and actual_columns:
        granularity = _TIME_GRANULARITY_MAP[dim_lower]
        # Find the first date/time column in the schema
        date_col = _find_date_column(actual_columns)
        if date_col:
            expr = f"DATE_TRUNC('{granularity}', {date_col})"
            alias = dim_lower.strip("_")
            return f"{expr} AS {alias}", expr
    
    # Regular column — pass through
    return dim, dim


def _find_date_column(columns: List[str]) -> Optional[str]:
    """Find a date/time column from the column list by name heuristics."""
    date_keywords = ["date", "time", "timestamp", "created", "updated"]
    for col in columns:
        if any(kw in col.lower() for kw in date_keywords):
            return col
    return None


def _build_dimensions(
    dimensions: List[str],
    actual_columns: Optional[List[str]] = None,
) -> tuple[str, str]:
    """
    Build SELECT and GROUP BY parts for all dimensions.
    Returns (select_parts_csv, group_parts_csv).
    """
    select_parts = []
    group_parts = []
    
    for dim in dimensions:
        sel, grp = _resolve_dimension(dim, actual_columns)
        select_parts.append(sel)
        group_parts.append(grp)
    
    return ", ".join(select_parts), ", ".join(group_parts)


def build_aggregate(
    step: StepIntent,
    table_name: str,
    tenant_id: str,
    semantics: Optional[Dict[str, str]] = None,
    actual_columns: Optional[List[str]] = None,
) -> str:
    metric_expr = _resolve_metric(step.metric, semantics)
    
    select_dims, group_dims = _build_dimensions(step.dimensions, actual_columns)
    select_cols = f"{select_dims}, " if select_dims else ""
    
    sql = f"SELECT {select_cols}{metric_expr} as total FROM {table_name} WHERE tenant_id = '{tenant_id}'"
    
    if step.filters:
        for col, val in step.filters.items():
            sql += f" AND {_render_filter_clause(col, val)}"
                
    if group_dims:
        sql += f" GROUP BY {group_dims}"
        
    order = "ASC" if step.order and step.order.lower() == "asc" else "DESC"
    limit = step.limit or 1000
    sql += f" ORDER BY total {order} LIMIT {limit}"
    return sql

def build_top_n(
    step: StepIntent,
    table_name: str,
    tenant_id: str,
    semantics: Optional[Dict[str, str]] = None,
    actual_columns: Optional[List[str]] = None,
) -> str:
    metric_expr = _resolve_metric(step.metric, semantics)
    
    select_dims, group_dims = _build_dimensions(step.dimensions, actual_columns)
    select_cols = f"{select_dims}, " if select_dims else ""
    
    sql = f"SELECT {select_cols}{metric_expr} as total FROM {table_name} WHERE tenant_id = '{tenant_id}'"
    
    if step.filters:
        for col, val in step.filters.items():
            sql += f" AND {_render_filter_clause(col, val)}"
    
    if group_dims:
        sql += f" GROUP BY {group_dims}"
        
    order_dir = "ASC" if step.order and step.order.lower() == "asc" else "DESC"
    limit = step.limit or 5
    sql += f" ORDER BY total {order_dir} LIMIT {limit}"
    return sql

def build_row_level(step: StepIntent, table_name: str, tenant_id: str) -> str:
    sql = f"SELECT * FROM {table_name} WHERE tenant_id = '{tenant_id}'"
    if step.filters:
        for col, val in step.filters.items():
            # Ignore placeholder resolution if it wasn't caught by orchestrator (fallback)
            if str(val) == "top_party":
                sql += f" AND {col} IS NOT NULL" 
            else:
                sql += f" AND {_render_filter_clause(col, val)}"
                
    if step.order and step.order.lower() != "none" and step.metric:
        sql += f" ORDER BY {step.metric} {step.order}"
        
    limit = step.limit or 1000
    sql += f" LIMIT {limit}"
    return sql

def build_query_for_step(
    step: StepIntent,
    table_name: str,
    tenant_id: str,
    semantics: Optional[Dict[str, str]] = None,
    actual_columns: Optional[List[str]] = None,
) -> str:
    """Routes the step to specific query builder components."""
    if step.intent_type == "row_level" or step.intent_type == "detail":
        return build_row_level(step, table_name, tenant_id)
    elif step.intent_type == "top_n" or step.intent_type == "ranking":
        return build_top_n(step, table_name, tenant_id, semantics, actual_columns)
    else:
        return build_aggregate(step, table_name, tenant_id, semantics, actual_columns)

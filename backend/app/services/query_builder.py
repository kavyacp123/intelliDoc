from app.models.intent import QueryIntent

def build_aggregate(intent: QueryIntent, table_name: str, tenant_id: str) -> str:
    metric_expr = intent.resolved_metric or intent.metric
    if metric_expr and metric_expr != "*":
        metric_expr = f"SUM({metric_expr})"
    else:
        metric_expr = "COUNT(*)"
        
    group_cols = ", ".join(intent.group_by) if intent.group_by else ""
    select_cols = f"{group_cols}, " if group_cols else ""
    
    sql = f"SELECT {select_cols}{metric_expr} as total FROM {table_name} WHERE tenant_id = '{tenant_id}'"
    
    if intent.filters:
        for f in intent.filters:
            col, op, val = f.get("column"), f.get("operator", "="), f.get("value")
            if col and val:
                if isinstance(val, list) or op.lower() == "in":
                    # For generic "compare Asia vs Europe" lists
                    if isinstance(val, str): val = [val] # Defensive
                    in_clause = ", ".join([f"'{v}'" for v in val])
                    sql += f" AND {col} IN ({in_clause})"
                else:
                    sql += f" AND {col} {op} '{val}'"
                
    if group_cols:
        sql += f" GROUP BY {group_cols}"
        
    order = "ASC" if intent.order == "asc" else "DESC"
    sql += f" ORDER BY total {order} LIMIT {intent.limit}"
    return sql

def build_top_n(intent: QueryIntent, table_name: str, tenant_id: str) -> str:
    metric_expr = intent.resolved_metric or intent.metric
    if metric_expr and metric_expr != "*":
        metric_expr = f"SUM({metric_expr})"
    else:
        metric_expr = "COUNT(*)"
        
    dim = intent.dimensions[0] if intent.dimensions else None
    group = intent.group_by[0] if intent.group_by else None
    
    sql = f"""
    SELECT tenant_id, {group}, {dim}, total
    FROM (
        SELECT 
            tenant_id,
            {group},
            {dim},
            {metric_expr} as total,
            ROW_NUMBER() OVER (
                PARTITION BY tenant_id, {group}
                ORDER BY {metric_expr} DESC
            ) as rank_n
        FROM {table_name}
        WHERE tenant_id = '{tenant_id}'
        GROUP BY tenant_id, {group}, {dim}
    )
    WHERE rank_n <= {intent.rank or 5}
    """
    return sql

def build_trend(intent: QueryIntent, table_name: str, tenant_id: str) -> str:
    time_col = intent.resolved_time_column or "date"
    metric_expr = intent.resolved_metric or intent.metric
    
    if metric_expr and metric_expr != "*":
        metric_expr = f"SUM({metric_expr})"
    else:
        metric_expr = "COUNT(*)"
        
    return f"""
    SELECT {time_col} as time_period,
           {metric_expr} as total
    FROM {table_name}
    WHERE tenant_id = '{tenant_id}'
    GROUP BY time_period
    ORDER BY time_period ASC
    """

def build_query(intent: QueryIntent, plan: dict, tenant_id: str) -> str:
    """Routes the intent to deterministic execution paths based on Query Planner instructions."""
    table = plan.get("table", "main_table")
    strategy = plan.get("strategy", "simple_agg")
    
    if strategy == "window_function":
        return build_top_n(intent, table, tenant_id)
    elif strategy == "time_series":
        return build_trend(intent, table, tenant_id)
    elif strategy == "comparison":
        return build_aggregate(intent, table, tenant_id)
    else:
        # Simple agg or simple agg with Limit (Top N without partitions)
        return build_aggregate(intent, table, tenant_id)

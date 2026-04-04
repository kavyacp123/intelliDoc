from app.models.intent import StepIntent

def build_aggregate(step: StepIntent, table_name: str, tenant_id: str) -> str:
    metric_expr = step.metric or "*"
    if metric_expr and metric_expr != "*":
        metric_expr = f"SUM({metric_expr})"
    else:
        metric_expr = "COUNT(*)"
        
    group_cols = ", ".join(step.dimensions) if step.dimensions else ""
    select_cols = f"{group_cols}, " if group_cols else ""
    
    sql = f"SELECT {select_cols}{metric_expr} as total FROM {table_name} WHERE tenant_id = '{tenant_id}'"
    
    if step.filters:
        for col, val in step.filters.items():
            if isinstance(val, list):
                in_clause = ", ".join([f"'{v}'" for v in val])
                sql += f" AND {col} IN ({in_clause})"
            else:
                sql += f" AND {col} = '{val}'"
                
    if group_cols:
        sql += f" GROUP BY {group_cols}"
        
    order = "ASC" if step.order and step.order.lower() == "asc" else "DESC"
    limit = step.limit or 1000
    sql += f" ORDER BY total {order} LIMIT {limit}"
    return sql

def build_top_n(step: StepIntent, table_name: str, tenant_id: str) -> str:
    metric_expr = step.metric or "*"
    if metric_expr and metric_expr != "*":
        metric_expr = f"SUM({metric_expr})"
    else:
        metric_expr = "COUNT(*)"
        
    group_cols = ", ".join(step.dimensions) if step.dimensions else ""
    select_cols = f"{group_cols}, " if group_cols else ""
    
    sql = f"SELECT {select_cols}{metric_expr} as total FROM {table_name} WHERE tenant_id = '{tenant_id}'"
    
    if step.filters:
        for col, val in step.filters.items():
            if isinstance(val, list):
                in_clause = ", ".join([f"'{v}'" for v in val])
                sql += f" AND {col} IN ({in_clause})"
            else:
                sql += f" AND {col} = '{val}'"
    
    if group_cols:
        sql += f" GROUP BY {group_cols}"
        
    order_dir = "ASC" if step.order and step.order.lower() == "asc" else "DESC"
    limit = step.limit or 5
    sql += f" ORDER BY total {order_dir} LIMIT {limit}"
    return sql

def build_row_level(step: StepIntent, table_name: str, tenant_id: str) -> str:
    sql = f"SELECT * FROM {table_name} WHERE tenant_id = '{tenant_id}'"
    if step.filters:
        for col, val in step.filters.items():
            if isinstance(val, list):
                in_clause = ", ".join([f"'{v}'" for v in val])
                sql += f" AND {col} IN ({in_clause})"
            # Ignore placeholder resolution if it wasn't caught by orchestrator (fallback)
            elif str(val) == "top_party":
                sql += f" AND {col} IS NOT NULL" 
            else:
                sql += f" AND {col} = '{val}'"
                
    if step.order and step.order.lower() != "none" and step.metric:
        sql += f" ORDER BY {step.metric} {step.order}"
        
    limit = step.limit or 1000
    sql += f" LIMIT {limit}"
    return sql

def build_query_for_step(step: StepIntent, table_name: str, tenant_id: str) -> str:
    """Routes the step to specific query builder components."""
    if step.intent_type == "row_level" or step.intent_type == "detail":
        return build_row_level(step, table_name, tenant_id)
    elif step.intent_type == "top_n" or step.intent_type == "ranking":
        return build_top_n(step, table_name, tenant_id)
    else:
        return build_aggregate(step, table_name, tenant_id)


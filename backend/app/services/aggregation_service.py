import logging
from app.core.database import get_connection

logger = logging.getLogger(__name__)

def run_pre_aggregations(table_name: str, columns: list):
    """
    Precompute common analytical views into DuckDB tables.
    Dramatically speeds up read access for generic queries.
    """
    conn = get_connection()
    col_names = [c.lower() for c in columns]
    
    has_revenue = "revenue" in col_names or "sales" in col_names
    revenue_col = "revenue" if "revenue" in col_names else "sales" if "sales" in col_names else None
    
    has_region = "region" in col_names or "country" in col_names
    region_col = "region" if "region" in col_names else "country" if "country" in col_names else None
    
    has_month = "month" in col_names
    month_col = "month" if "month" in col_names else None
    
    if not revenue_col:
        return
        
    try:
        all_tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
        partitions = [t for t in all_tables if t.startswith(f"{table_name}_") and "_agg_" not in t]
        
        if not partitions:
            return
            
        subqueries = [f'SELECT * FROM "{p}"' for p in partitions]
        base_from = f"({ ' UNION ALL '.join(subqueries) })"
        
        # Precompute Revenue by Region
        if region_col:
            agg_table = f"{table_name}_agg_rev_by_region"
            sql = f'''
                CREATE TABLE "{agg_table}" AS 
                SELECT tenant_id, {region_col} AS region, SUM({revenue_col}) AS revenue
                FROM {base_from}
                GROUP BY tenant_id, {region_col}
            '''
            conn.execute(sql)
            logger.info("Created pre-aggregation: %s", agg_table)
            
        # Precompute Revenue by Month
        if month_col:
            agg_table = f"{table_name}_agg_rev_by_month"
            sql = f'''
                CREATE TABLE "{agg_table}" AS 
                SELECT tenant_id, {month_col} AS month, SUM({revenue_col}) AS revenue
                FROM {base_from}
                GROUP BY tenant_id, {month_col}
            '''
            conn.execute(sql)
            logger.info("Created pre-aggregation: %s", agg_table)
            
    except Exception as e:
        logger.error("Pre-aggregation failed for %s: %s", table_name, str(e))

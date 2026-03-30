from typing import Dict, List, Any, Optional

class KPIEngine:
    """
    Computes financial KPIs (Net Profit, Margin, etc.) from normalized data.
    """

    @classmethod
    def compute_dashboard_metrics(cls, normalized_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Aggregate normalized data to produce KPIs and chart-ready structures.
        """
        if not normalized_data:
            return {"kpis": [], "charts": [], "table": {"columns": [], "rows": []}}

        total_revenue = 0
        total_cost = 0
        total_profit = 0
        record_count = len(normalized_data)
        
        # Aggregates for charts
        time_series = {} # {period: sum_profit}
        category_series = {} # {category: sum_profit}
        
        for row in normalized_data:
            rev = row.get("revenue", 0)
            cost = row.get("cost", 0)
            profit = row.get("profit", rev - cost)
            
            total_revenue += rev
            total_cost += cost
            total_profit += profit
            
            # Time Detection
            if "time" in row:
                t = str(row["time"])
                time_series[t] = time_series.get(t, 0) + profit
            
            # Category Detection
            if "category" in row:
                c = str(row["category"])
                category_series[c] = category_series.get(c, 0) + profit

        # 1. KPIs
        margin = (total_profit / total_revenue * 100) if total_revenue != 0 else 0
        kpis = [
            {"name": "Net Profit", "value": f"${total_profit:,.2f}", "type": "currency"},
            {"name": "Profit Margin", "value": f"{margin:.1f}%", "type": "percentage"},
            {"name": "Total Revenue", "value": f"${total_revenue:,.2f}", "type": "currency"},
            {"name": "Operations Cost", "value": f"${total_cost:,.2f}", "type": "currency"}
        ]

        # 2. Charts
        charts = []
        if time_series:
            sorted_times = sorted(time_series.keys())
            charts.append({
                "type": "line",
                "title": "Profit Trend Over Time",
                "x": sorted_times,
                "series": [{"name": "Profit", "data": [time_series[t] for t in sorted_times]}]
            })
            
        if category_series:
            sorted_cats = sorted(category_series.keys(), key=lambda x: category_series[x], reverse=True)[:10]
            charts.append({
                "type": "bar",
                "title": "Top Categories by Profit",
                "x": sorted_cats,
                "series": [{"name": "Profit", "data": [category_series[c] for c in sorted_cats]}]
            })

        # 3. Table
        all_keys = set()
        for row in normalized_data:
            all_keys.update(row.keys())
        
        columns = [{"key": k, "label": k.capitalize()} for k in sorted(list(all_keys))]
        rows = normalized_data[:50] # Limit for dashboard preview

        return {
            "kpis": kpis,
            "charts": charts,
            "table": {"columns": columns, "rows": rows}
        }

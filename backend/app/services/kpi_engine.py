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

    @classmethod
    def compute_profit_dashboard_metrics(cls, normalized_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Specialized engine that mimics the detailed financial dashboard in the provided plan.
        """
        if not normalized_data:
            return {}

        monthly_aggs = {}
        
        # 1. Monthly Aggregation
        for row in normalized_data:
            t = str(row.get("time", "Unknown"))
            if t not in monthly_aggs:
                monthly_aggs[t] = {
                    "revenue": 0, "cogs": 0, "sales": 0, "marketing": 0, "ga": 0,
                    "other_income": 0, "other_expenses": 0, "interest_tax": 0, "target_ebit": 0
                }
            
            monthly_aggs[t]["revenue"] += row.get("revenue", 0)
            monthly_aggs[t]["cogs"] += row.get("cogs", 0)
            monthly_aggs[t]["sales"] += row.get("opex_sales", 0)
            monthly_aggs[t]["marketing"] += row.get("opex_marketing", 0)
            monthly_aggs[t]["ga"] += row.get("opex_ga", 0)
            monthly_aggs[t]["other_income"] += row.get("other_income", 0)
            monthly_aggs[t]["other_expenses"] += row.get("other_expenses", 0)
            monthly_aggs[t]["interest_tax"] += row.get("interest", 0) + row.get("tax", 0)
            monthly_aggs[t]["target_ebit"] += row.get("target", row.get("revenue", 0) * 0.2) # Default target if missing

        sorted_months = sorted(monthly_aggs.keys())
        
        # Totals
        total_rev = sum(m["revenue"] for m in monthly_aggs.values())
        total_cogs = sum(m["cogs"] for m in monthly_aggs.values())
        total_gp = total_rev - total_cogs
        total_opex = sum(m["sales"] + m["marketing"] + m["ga"] for m in monthly_aggs.values())
        total_ebit = total_gp - total_opex + sum(m["other_income"] - m["other_expenses"] for m in monthly_aggs.values())
        total_np = total_ebit - sum(m["interest_tax"] for m in monthly_aggs.values())

        # 2. Gauges
        gauges = [
            {"label": "GROSS PROFIT MARGIN", "value": (total_gp/total_rev*100) if total_rev else 0},
            {"label": "OPEX RATIO", "value": (total_opex/total_rev*100) if total_rev else 0},
            {"label": "OPERATING PROFIT MARGIN", "value": (total_ebit/total_rev*100) if total_rev else 0},
            {"label": "NET PROFIT MARGIN", "value": (total_np/total_rev*100) if total_rev else 0}
        ]

        # 3. OPEX Chart Data
        opex_chart = []
        for m in sorted_months:
            ma = monthly_aggs[m]
            total_m_opex = ma["sales"] + ma["marketing"] + ma["ga"]
            opex_chart.append({
                "month": m,
                "Sales": ma["sales"],
                "Marketing": ma["marketing"],
                "GA": ma["ga"],
                "OPEX_Ratio": (total_m_opex / ma["revenue"] * 100) if ma["revenue"] else 0
            })

        # 4. EBIT Chart Data
        ebit_chart = []
        for m in sorted_months:
            ma = monthly_aggs[m]
            m_ebit = (ma["revenue"] - ma["cogs"]) - (ma["sales"] + ma["marketing"] + ma["ga"]) + (ma["other_income"] - ma["other_expenses"])
            ebit_chart.append({
                "month": m,
                "Actual": m_ebit,
                "Target": ma["target_ebit"]
            })

        # 5. Income Statement
        statement = [
            {"item": "Revenue", "value": total_rev},
            {"item": "COGS", "value": total_cogs},
            {"item": "GROSS PROFIT", "value": total_gp, "isHeader": True},
            {"item": "OPEX", "value": total_opex, "isHeader": True},
            {"item": "  Sales", "value": sum(m["sales"] for m in monthly_aggs.values())},
            {"item": "  Marketing", "value": sum(m["marketing"] for m in monthly_aggs.values())},
            {"item": "  General & Admin", "value": sum(m["ga"] for m in monthly_aggs.values())},
            {"item": "Other Income", "value": sum(m["other_income"] for m in monthly_aggs.values())},
            {"item": "Other Expenses", "value": sum(m["other_expenses"] for m in monthly_aggs.values())},
            {"item": "OPERATING PROFIT (EBIT)", "value": total_ebit, "isHeader": True},
            {"item": "Interest and Tax", "value": sum(m["interest_tax"] for m in monthly_aggs.values())},
            {"item": "NET PROFIT", "value": total_np, "isHeader": True}
        ]

        return {
            "gauges": gauges,
            "opex_chart": opex_chart,
            "ebit_chart": ebit_chart,
            "statement": statement,
            "summary": {
                "profit": total_np,
                "revenue": total_rev,
                "margin": (total_np/total_rev*100) if total_rev else 0
            }
        }

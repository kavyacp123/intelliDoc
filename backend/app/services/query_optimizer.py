"""
Multi-Plan Query Optimizer (V4).

Generates multiple execution candidates and selects the one with the lowest estimated cost.
"""

from app.models.intent import QueryIntent
from app.services.cost_estimator import estimate_cost

class QueryOptimizer:
    @staticmethod
    def generate_plans(intent: QueryIntent, metadata: dict) -> list:
        """
        Generate multiple candidate execution plans.
        """
        plans = []

        # Plan 1: Standard Table scan (Base Plan)
        plans.append({
            "table": metadata["table_name"],
            "strategy": "base_scan",
            "is_pre_agg": False,
            "use_partitions": metadata.get("has_partitions", False)
        })

        # Plan 2: Pre-aggregation (if available)
        if intent.group_by:
            dim = intent.group_by[0]
            pre_agg_table = metadata.get("pre_agg_tables", {}).get(dim)
            if pre_agg_table:
                plans.append({
                    "table": pre_agg_table,
                    "strategy": "pre_agg_hit",
                    "is_pre_agg": True,
                    "use_partitions": False
                })

        # Plan 3: Partition-optimized (if time intelligence is involved)
        # Note: In V4, partitions are often inferred by base_scan, but 
        # we can explicitly declare a direct child partition scan here if needed.

        return plans

    @staticmethod
    def choose_best_plan(plans: list, intent: QueryIntent, metadata: dict) -> dict:
        """
        Evaluate all candidate plans via the cost estimator and pick the winner.
        """
        best_plan = None
        min_cost = float("inf")

        for plan in plans:
            # Merge plan-specific metadata (like is_pre_agg) with global metadata
            evaluation_metadata = metadata.copy()
            evaluation_metadata.update(plan)
            
            cost = estimate_cost(intent, evaluation_metadata)
            
            if cost < min_cost:
                min_cost = cost
                best_plan = plan

        if best_plan:
            best_plan["estimated_cost"] = min_cost
        
        return best_plan

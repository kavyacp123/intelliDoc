from app.models.intent import QueryIntent
from app.services.cost_estimator import estimate_cost

class QueryPlanner:
    @staticmethod
    def plan(intent: QueryIntent, schema: dict, metadata: dict) -> dict:
        """
        The Query Planner Core Engine.
        Determines execution strategy, target table mapping, and partition utilization 
        dynamically.
        """
        from typing import Any
        plan: dict[str, Any] = {}
        
        table_name = metadata.get("table_name", "main_table")
        
        # Scenario: Intelligent Estimation bounds
        cost = estimate_cost(intent, metadata)
        plan["estimated_cost"] = cost
        
        if cost < 1e5:
            plan["execution_mode"] = "sync"
        else:
            plan["execution_mode"] = "async"
        
        # Scenario: Intelligent Table Routing (Real Pre-Agg)
        if intent.group_by:
            primary_dim = intent.group_by[0]
            pre_agg_map = metadata.get("pre_agg_tables", {})
            if primary_dim in pre_agg_map:
                plan["table"] = pre_agg_map[primary_dim]
                plan["used_pre_agg"] = True
            else:
                plan["table"] = table_name
        else:
            plan["table"] = table_name
            
        # Scenario: Partition Pruning Eligibility
        if intent.time_grain or intent.resolved_time_column:
            plan["use_partitions"] = True
        else:
            plan["use_partitions"] = False
            
        # Scenario: Execution Strategy Mapping
        if intent.operation == "top_n":
            # Swap dimensions into group_by if LLM gets confused on simple arrays
            if not intent.group_by and intent.dimensions:
                intent.group_by = intent.dimensions
                
            # If there's distinct dimensions spanning over a distinct partition group (e.g. Best Product explicitly PER Year)
            # -> Employs Window functions `ROW_NUMBER() OVER()`
            if len(intent.dimensions) > 0 and len(intent.group_by) > 0 and intent.dimensions[0] != intent.group_by[0]:
                plan["strategy"] = "window_function"
            else:
                plan["strategy"] = "simple_agg_limit"
                # Override limit to exactly the requested rank
                intent.limit = intent.rank or 5
                
        elif intent.operation == "trend":
            plan["strategy"] = "time_series"
            
        elif intent.operation == "comparison":
            plan["strategy"] = "comparison"
            # Ensure comparison groups by primary dimension
            if not intent.group_by and intent.dimensions:
                intent.group_by = intent.dimensions
            
        else:
            plan["strategy"] = "simple_agg"
            
        return plan

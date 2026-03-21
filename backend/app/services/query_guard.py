"""
Query Guard (V4).

Enforces budget limits to prevent expensive queries from straining the system.
"""

from fastapi import HTTPException

MAX_COST = 1000000.0  # 1M cost units limit for synchronous queries

def enforce_budget(plan: dict) -> None:
    """
    Check the estimated cost of a plan against the system budget.
    """
    cost = plan.get("estimated_cost", 0)
    
    if cost > MAX_COST:
        raise HTTPException(
            status_code=400,
            detail=f"Query budget exceeded (Cost: {cost:.0f}). Please add filters or reduce groupings."
        )

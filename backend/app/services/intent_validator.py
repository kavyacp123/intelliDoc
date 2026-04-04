from typing import Set
from app.models.intent import QueryIntent

class IntentValidationError(Exception):
    def __init__(self, message: str, available_columns: list, invalid_column: str = None):
        self.message = message
        self.available_columns = available_columns
        self.invalid_column = invalid_column
        super().__init__(self.message)

from app.models.intent import MultiStepPlan

def validate_intent(plan: MultiStepPlan, allowed_columns: Set[str]):
    """
    Validates that the generated Intent only references columns that actually exist.
    """
    available_cols = sorted(list(allowed_columns - {"tenant_id"}))
    
    for step in plan.steps:
        # Validate metric
        if step.metric and step.metric not in allowed_columns and step.metric != "*":
            raise IntentValidationError(
                f"Invalid metric: '{step.metric}'",
                available_cols,
                step.metric
            )
            
        # Validate dimensions
        for dim in step.dimensions:
            if dim not in allowed_columns and dim not in ["year", "month", "day"]:
                raise IntentValidationError(
                    f"Invalid dimension: '{dim}'",
                    available_cols,
                    dim
                )
    
        # Group_by doesn't exist explicitly in step anymore. It relies on dimensions.
            
    return True

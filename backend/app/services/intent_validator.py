from typing import Set
from app.models.intent import QueryIntent

class IntentValidationError(Exception):
    def __init__(self, message: str, available_columns: list, invalid_column: str = None):
        self.message = message
        self.available_columns = available_columns
        self.invalid_column = invalid_column
        super().__init__(self.message)

def validate_intent(intent: QueryIntent, allowed_columns: Set[str]):
    """
    Validates that the generated Intent only references columns that actually exist.
    """
    available_cols = sorted(list(allowed_columns - {"tenant_id"}))
    
    # Validate metric
    if intent.metric and intent.metric not in allowed_columns:
        # It's possible the metric name is derived or misspelled
        raise IntentValidationError(
            f"Invalid metric: '{intent.metric}'",
            available_cols,
            intent.metric
        )
        
    # Validate dimensions
    for dim in intent.dimensions:
        # Ignore time_grain aliases like 'year' or 'month' as they might be handled by DATE_TRUNC unless they explicitly exist
        if dim not in allowed_columns and dim not in ["year", "month", "day"]:
            raise IntentValidationError(
                f"Invalid dimension: '{dim}'",
                available_cols,
                dim
            )
            
    # Validate group_by
    for group in intent.group_by:
        if group not in allowed_columns and group not in ["year", "month", "day"]:
            raise IntentValidationError(
                f"Invalid group_by column: '{group}'",
                available_cols,
                group
            )

    return True

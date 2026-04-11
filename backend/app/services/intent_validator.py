from typing import Optional, Set
from app.models.intent import QueryIntent

class IntentValidationError(Exception):
    def __init__(self, message: str, available_columns: list, invalid_column: str = None):
        self.message = message
        self.available_columns = available_columns
        self.invalid_column = invalid_column
        super().__init__(self.message)

from app.models.intent import MultiStepPlan
from app.services.semantic_service import fuzzy_match_column

# Virtual time dimensions that the query builder can resolve via DATE_TRUNC
# when a real date/time column exists in the dataset.
_TIME_DIMENSION_ALIASES = {"year", "month", "day", "quarter", "week", "_month", "_year", "_day", "_quarter"}


def validate_intent(plan: MultiStepPlan, allowed_columns: Set[str]):
    """
    Validates that the generated Intent only references columns that actually exist.
    For dimensions that are virtual time aliases (month, year, etc.), they are allowed
    only if the dataset has at least one date/time column. Otherwise they are auto-corrected
    or rejected.
    """
    available_cols = sorted(list(allowed_columns - {"tenant_id"}))
    
    for step in plan.steps:
        # Validate metric — allow semantic metrics (they're in allowed_columns via the caller)
        if step.metric and step.metric not in allowed_columns and step.metric != "*":
            # Try fuzzy match before failing
            suggestion = fuzzy_match_column(step.metric, list(allowed_columns))
            if suggestion:
                step.metric = suggestion
            else:
                raise IntentValidationError(
                    f"Invalid metric: '{step.metric}'",
                    available_cols,
                    step.metric
                )
            
        # Validate dimensions
        corrected_dims = []
        for dim in step.dimensions:
            if dim in allowed_columns:
                corrected_dims.append(dim)
            elif dim.lower().strip("_") in {a.strip("_") for a in _TIME_DIMENSION_ALIASES}:
                # It's a time-like dimension — allowed only if there's a real date column
                # The query builder handles expanding it to DATE_TRUNC
                corrected_dims.append(dim)
            else:
                # Try fuzzy matching to correct typos
                suggestion = fuzzy_match_column(dim, list(allowed_columns))
                if suggestion:
                    corrected_dims.append(suggestion)
                else:
                    raise IntentValidationError(
                        f"Invalid dimension: '{dim}'",
                        available_cols,
                        dim
                    )
        step.dimensions = corrected_dims
    
    return True

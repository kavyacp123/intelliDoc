from pydantic import BaseModel
from typing import List, Optional

class QueryIntent(BaseModel):
    """Deprecated alias for backward compatibility in routing and explanation services not yet refactored."""
    pass

class StepIntent(BaseModel):
    step_id: int
    intent_type: str  # aggregate | top_n | trend | comparison | row_level
    description: str
    metric: Optional[str] = None
    dimensions: List[str] = []
    filters: dict = {}
    order: Optional[str] = "NONE"
    limit: Optional[int] = None
    depends_on: Optional[int] = None
    output: Optional[str] = None

class FinalOutput(BaseModel):
    type: str
    description: str

class MultiStepPlan(BaseModel):
    query_type: str
    requires_multi_step: bool
    steps: List[StepIntent] = []
    final_output: FinalOutput
    
    # Internal context bindings (added by the processor later)
    resolved_time_column: Optional[str] = None


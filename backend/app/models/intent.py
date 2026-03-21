from pydantic import BaseModel
from typing import List, Optional

class QueryIntent(BaseModel):
    metric: Optional[str] = None
    dimensions: List[str] = []
    filters: List[dict] = []
    
    operation: str = "aggregate"  
    # allowed:
    # aggregate | top_n | trend | comparison
    
    group_by: List[str] = []
    
    order: Optional[str] = "desc"
    rank: Optional[int] = None
    
    time_grain: Optional[str] = None  
    # year, month, day
    
    limit: Optional[int] = 1000
    
    # Execution Context (V2)
    confidence: float = 1.0
    resolved_metric: Optional[str] = None
    resolved_time_column: Optional[str] = None

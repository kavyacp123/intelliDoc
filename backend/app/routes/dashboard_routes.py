from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.services.normalization_service import NormalizationService
from app.services.kpi_engine import KPIEngine
from app.core.security import get_current_user

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

class DashboardRequest(BaseModel):
    data: List[Dict[str, Any]]
    dataset_name: Optional[str] = "unnamed_dataset"

class DashboardResponse(BaseModel):
    kpis: List[Dict[str, Any]]
    charts: List[Dict[str, Any]]
    table: Dict[str, Any]

# In-memory cache for demo/performance (use Redis for production)
_dashboard_cache: Dict[str, Dict[str, Any]] = {}

@router.post("/analyze", response_model=DashboardResponse)
async def analyze_dataset(
    request: DashboardRequest,
    current_user: Any = Depends(get_current_user)
):
    """
    Analyzes any JSON dataset and returns normalized dashboard structures.
    """
    if not request.data:
        raise HTTPException(status_code=400, detail="Dataset is empty")

    import hashlib
    # Simple cache key based on data sample
    data_sample = str(request.data[:5]).encode("utf-8")
    cache_key = hashlib.md5(data_sample).hexdigest()
    
    if cache_key in _dashboard_cache:
        return _dashboard_cache[cache_key]

    try:
        # 1. Normalize
        normalized_data = NormalizationService.apply_normalization(request.data)
        
        # 2. Compute Metrics
        dashboard_content = KPIEngine.compute_dashboard_metrics(normalized_data)
        
        # 3. Cache and Return
        _dashboard_cache[cache_key] = dashboard_content
        return dashboard_content

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

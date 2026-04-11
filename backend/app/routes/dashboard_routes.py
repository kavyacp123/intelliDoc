from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.services.normalization_service import NormalizationService
from app.services.kpi_engine import KPIEngine
from app.services.dashboard_generator import generate_executive_dashboard
from app.services.executive_insight_generator import generate_executive_insights
from app.core.database import get_connection
from app.core.security import get_current_user

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

class DashboardRequest(BaseModel):
    data: List[Dict[str, Any]]
    dataset_name: Optional[str] = "unnamed_dataset"

class DashboardResponse(BaseModel):
    kpis: List[Dict[str, Any]]
    charts: List[Dict[str, Any]]
    table: Dict[str, Any]

class ExecutiveDashboardRequest(BaseModel):
    dataset_id: str

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

@router.post("/profit-analysis")
async def profit_analysis(
    request: DashboardRequest,
    current_user: Any = Depends(get_current_user)
):
    """
    Detailed financial analysis resulting in Gauges, P&L Statement, and specific sub-OPEX trends.
    """
    if not request.data:
        raise HTTPException(status_code=400, detail="Dataset is empty")

    try:
        # 1. Normalize
        normalized_data = NormalizationService.apply_normalization(request.data)
        
        # 2. Compute specialized Profit metrics
        dashboard_content = KPIEngine.compute_profit_dashboard_metrics(normalized_data)
        
        return dashboard_content

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Profit analysis failed: {str(e)}")


# ─────────────────────────────────────────────
# NEW: Executive Dashboard (Schema-Driven, No Data Transfer)
# ─────────────────────────────────────────────

@router.post("/executive")
async def executive_dashboard(
    request: ExecutiveDashboardRequest,
    current_user: str = Depends(get_current_user),
):
    """
    Generate a CFO-level executive dashboard for a dataset.

    Runs SQL queries directly against DuckDB — no raw data transfer needed.
    Auto-detects semantic fields (revenue, cost, profit, time, dimensions)
    and builds KPIs, chart sections, and predefined queries.
    """
    dataset_id = request.dataset_id

    # Verify ownership
    conn = get_connection()
    row = conn.execute(
        "SELECT table_name FROM datasets WHERE dataset_id = ? AND tenant_id = ?",
        [dataset_id, current_user],
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Dataset not found")

    try:
        result = generate_executive_dashboard(dataset_id, current_user)
        if "error" in result and not result.get("kpis"):
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Dashboard generation failed: {str(e)}")


@router.post("/executive/query")
async def execute_predefined_query(
    request: dict,
    current_user: str = Depends(get_current_user),
):
    """
    Execute a predefined query from the dashboard and return its results.
    """
    sql = request.get("sql")
    dataset_id = request.get("dataset_id")

    if not sql or not dataset_id:
        raise HTTPException(status_code=400, detail="sql and dataset_id required")

    # Verify ownership
    conn = get_connection()
    row = conn.execute(
        "SELECT table_name FROM datasets WHERE dataset_id = ? AND tenant_id = ?",
        [dataset_id, current_user],
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Security: verify the SQL references the correct table
    table_name = row[0]
    if table_name not in sql:
        raise HTTPException(status_code=403, detail="SQL does not reference the expected dataset table")

    try:
        from app.services import execution_service
        data = execution_service.execute_query(sql)
        # Strip tenant_id from results
        for row_data in data:
            row_data.pop("tenant_id", None)
        return {"data": data, "row_count": len(data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.post("/executive/insights")
async def generate_insights(
    request: dict,
    current_user: str = Depends(get_current_user),
):
    """
    Generate professional financial insights from executive dashboard data.
    Takes the full JSON blob of the dashboard content and passes it to the LLM
    via executive_insight_generator.py.
    """
    dashboard_data = request.get("dashboard_data")
    if not dashboard_data:
        raise HTTPException(status_code=400, detail="dashboard_data required")

    try:
        insights = generate_executive_insights(dashboard_data)
        return insights
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Insight generation failed: {str(e)}")

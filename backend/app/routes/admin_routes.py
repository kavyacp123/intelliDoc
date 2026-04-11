from typing import Optional

from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.services.rag_metrics_service import compute_rag_metrics

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/rag-metrics", summary="Summarize shadow RAG evaluation metrics")
async def get_rag_metrics(
    dataset_id: Optional[str] = None,
    current_user: str = Depends(get_current_user),
):
    return compute_rag_metrics(current_user, dataset_id)

import logging
from app.worker.celery_app import celery_app
from app.services.query_builder_service import build_query
from app.services.validator_service import validate_query
from app.services.rewrite_service import rewrite_query
from app.services.execution_service import execute_query
from app.schemas.query_schema import StructuredIntent

logger = logging.getLogger(__name__)

@celery_app.task(name="app.worker.tasks.run_query_task")
def run_query_task(intent_dict: dict, tenant_id: str):
    """
    Background job to run the entire query pipeline.
    Celery automatically stores the returned dict in its Redis results backend.
    """
    logger.info("Starting background query task for tenant %s", tenant_id)
    try:
        intent = StructuredIntent(**intent_dict)
        
        # 1. Build initial SQL (or view intercept)
        sql = build_query(intent)
        
        # 2. Validate
        validate_query(sql, intent.table_name)
        
        # 3. Rewrite for safety
        safe_sql = rewrite_query(sql, tenant_id)
        
        # 4. Execute
        result = execute_query(safe_sql)
        
        return {
            "status": "success", 
            "data": result, 
            "sql": safe_sql
        }
    except Exception as e:
        logger.error("Background task failed: %s", str(e))
        return {
            "status": "error", 
            "message": str(e)
        }

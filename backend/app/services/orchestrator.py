from typing import Any, Dict, List
import logging
from app.models.intent import MultiStepPlan, StepIntent
from app.services.query_builder import build_query_for_step
from app.services.execution_service import execute_query

logger = logging.getLogger(__name__)

class Orchestrator:
    @staticmethod
    def execute_plan(plan: MultiStepPlan, table_name: str, tenant_id: str) -> Dict[str, Any]:
        """
        Executes a multi-step query plan sequentially.
        Passes results from dependent steps into filters of subsequent steps.
        Returns the final resultset, SQLs executed, and intermediate metadata.
        """
        execution_context = {}
        all_sqls = []
        final_data = []

        # Sort steps by ID to ensure sequence
        steps = sorted(plan.steps, key=lambda x: x.step_id)

        for step in steps:
            logger.info("Executing step %s: %s", step.step_id, step.description)

            # 1. Resolve dependencies in filters
            resolved_filters = orchestrate_filters(step.filters, execution_context)
            step.filters = resolved_filters

            # 2. Build SQL for step
            # Note: We pass raw table_name here; ideally planner handles routing, but for multi-step V1 we use main table.
            sql = build_query_for_step(step, table_name, tenant_id)
            all_sqls.append(sql)

            # 3. Execute
            logger.info("Step %s SQL: %s", step.step_id, sql)
            data = execute_query(sql)

            # 4. Save output for next steps if there is an output key
            if step.output and data:
                # Store the primary key/dimension value returned
                # e.g. if we ranked top party, grab the first column of the first row
                first_row = data[0]
                # Assuming the dimension requested is the key
                dim_key = step.dimensions[0] if step.dimensions else list(first_row.keys())[0]
                # For safety, if dim_key exists, grab it, else first val
                extracted_val = first_row.get(dim_key, list(first_row.values())[0])
                
                execution_context[step.output] = extracted_val
                logger.debug("Stored execution context %s = %s", step.output, extracted_val)

            final_data = data

        return {
            "data": final_data,
            "sqls": all_sqls,
            "context": execution_context
        }

def orchestrate_filters(filters: dict, context: dict) -> dict:
    """
    If a filter value maps to a known output in the execution context, replace it.
    Example: filters={"party": "top_party"} and context={"top_party": "Acme Corp"}
    Result: filters={"party": "Acme Corp"}
    """
    resolved = {}
    for col, val in filters.items():
        if isinstance(val, str) and val in context:
            resolved[col] = context[val]
        else:
            resolved[col] = val
    return resolved

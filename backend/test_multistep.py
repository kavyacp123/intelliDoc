import asyncio
import os
import json
from datetime import datetime

# Mock settings just for local testing the service logic
from dotenv import load_dotenv
load_dotenv()

from app.schemas.query_schema import QueryRequest
from app.services import llm_service
from app.models.intent import MultiStepPlan
from app.services.intent_processor import enhance_intent
from app.services.metric_resolver import resolve_metric
from app.services.orchestrator import Orchestrator
from app.core.database import get_connection

from typing import Any
class ColumnMock:
    def __init__(self, name, dtype, sample_values, distinct_count):
        self.name = name
        self.dtype = dtype
        self.sample_values = sample_values
        self.distinct_count = distinct_count

def main():
    # 1. Provide mock schema matching sr_22-23.xlsx
    columns = [
        ColumnMock(name="transaction_date", dtype="datetime", sample_values=[], distinct_count=100),
        ColumnMock(name="party", dtype="string", sample_values=["Acme", "Globex"], distinct_count=5),
        ColumnMock(name="items", dtype="int", sample_values=[10, 50], distinct_count=50),
        ColumnMock(name="revenue", dtype="float", sample_values=[500.0, 1500.0], distinct_count=100),
        ColumnMock(name="product_name", dtype="string", sample_values=["Product_1", "Product_2"], distinct_count=5),
        ColumnMock(name="transaction_id", dtype="string", sample_values=["TXN_1000", "TXN_1001"], distinct_count=150),
        ColumnMock(name="tenant_id", dtype="string", sample_values=[], distinct_count=1)
    ]
    
    class TableMock:
        def __init__(self):
            self.table_name = "sr_22_23"
            self.columns = columns
            
    schema = TableMock()
    
    schema_dict = {
        "table_name": "sr_22_23",
        "metrics": ["items", "revenue"],
        "dimensions": ["party", "product_name", "transaction_id"],
        "time_dimensions": ["transaction_date"],
    }
    
    question = "highest number of items sale to one party and details"
    
    # Generate Intents 
    print("Generating LLM Intent...")
    intent_json = llm_service.generate_intent_json(
        question=question,
        schemas=[schema],
        table_name="sr_22_23",
        semantics=None
    )
    
    print("LLM Response:\n", json.dumps(intent_json, indent=2))
    
    print("\nExecuting Plan...")
    plan_obj = MultiStepPlan(**intent_json)
    plan_obj = enhance_intent(plan_obj, question, schema_dict)
    resolve_metric(plan_obj, schema_dict)
    
    # We will upload the sr_22-23.xlsx to mock duckdb database here
    import pandas as pd
    df = pd.read_excel("sr_22-23.xlsx")
    df['tenant_id'] = "test_tenant"
    conn = get_connection()
    conn.execute("CREATE TABLE IF NOT EXISTS sr_22_23 AS SELECT * FROM df")
    
    result = Orchestrator.execute_plan(plan_obj, "sr_22_23", "test_tenant")
    
    print("\nSQLs Executed:")
    for sql in result["sqls"]:
        print("  ", sql.strip())
        
    print("\nFinal Data:")
    for row in result["data"][:5]:
        print(row)
    print(f"(total rows: {len(result['data'])})")

if __name__ == "__main__":
    main()

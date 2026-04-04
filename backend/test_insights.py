import os
import json
from dotenv import load_dotenv
load_dotenv()

from app.services.insight_service import generate_insights
from app.schemas.query_schema import DashboardResponse

def main():
    data = [
        {"party": "Acme", "sales": 100},
        {"party": "Globex", "sales": 300},
        {"party": "Soylent", "sales": 50}
    ]
    
    question = "What are the total sales per party?"
    sql = "SELECT party, sum(sales) FROM test_table GROUP BY party"
    
    insights = generate_insights(data, question, sql)
    
    print("Insights JSON Output:")
    print(insights.model_dump_json(indent=2))
    
if __name__ == "__main__":
    main()

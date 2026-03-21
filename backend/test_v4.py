import httpx
import time
from app.core.security import create_access_token

def test_v4_pipeline():
    tenant_id = "test_tenant_v4"
    token = create_access_token({"sub": tenant_id})
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        with httpx.Client() as client:
            # 1. Upload File (Tests file_service distinct count logic)
            print("Uploading file to establish dataset...")
            files = {"file": ("Financial Sample.xlsx", open("../Financial Sample.xlsx", "rb"), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            start = time.time()
            res = client.post("http://127.0.0.1:8000/upload", headers={"Authorization": f"Bearer {token}"}, files=files, timeout=300.0)
            print(f"Upload took {time.time() - start:.2f}s")
            if res.status_code not in [200, 201]:
                print(f"Failed to upload: {res.text}")
                return
            
            dataset_id = res.json()["dataset_id"]
            print(f"Uploaded successfully. Dataset ID: {dataset_id}")

            def run_test(name, q):
                print(f"\n--- {name}: '{q}' ---")
                res = client.post("http://127.0.0.1:8000/query", headers=headers, json={"dataset_id": dataset_id, "question": q}, timeout=120)
                if res.status_code == 200:
                    data = res.json()
                    print("Execution Plan:", data.get('execution_plan'))
                    print("Insights:", data.get('insights'))
                    return data
                else:
                    print(f"Error {res.status_code}: {res.text}")
                    return None

            # Test 1: Cardinality Estimation
            print("\n*** Testing Cardinality Estimation ***")
            res1 = run_test("Basic Plan & Cardinality", "total sales by Product")
            
            # Test 2: Insights & Pre-Agg
            print("\n*** Testing Insight Generation Engine ***")
            run_test("Insights (Top 5)", "top 5 countries by sales")
            run_test("Insights (Trend)", "sales trend over time")

            # Test 3: Adaptive Feedback Loop
            # The previous query for product should have recorded its execution time.
            print("\n*** Testing Adaptive Cost Model Feedback Loop ***")
            # We use a slightly different wording but identical intent to avoid basic SQL cache, testing intent hash
            # Wait, cache key is `current_user:table_name:normalized_question`.
            # If normalized question is exactly same, semantic cache hits.
            # "sum of sales per product" vs "total sales by product"
            res_learned = run_test("Learned Cost Verification", "sum of sales per product")
            
            if res1 and res_learned:
                cost_orig = res1.get('execution_plan', {}).get('estimated_cost')
                cost_new = res_learned.get('execution_plan', {}).get('estimated_cost')
                print(f"Original heuristic cost: {cost_orig}")
                print(f"Learned adaptive cost: {cost_new}")

    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == "__main__":
    test_v4_pipeline()

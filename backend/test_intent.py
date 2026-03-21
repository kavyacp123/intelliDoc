import httpx
import json
import time
from app.core.security import create_access_token

def test_pipeline():
    tenant_id = "test_tenant_intent"
    token = create_access_token({"sub": tenant_id})
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    upload_headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Upload file
    print("Uploading file to establish dataset...")
    files = {"file": ("Financial Sample.xlsx", open("../Financial Sample.xlsx", "rb"), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    with httpx.Client() as client:
        res = client.post("http://127.0.0.1:8000/upload", headers=upload_headers, files=files, timeout=60.0)
        if res.status_code not in [200, 201]:
            print(f"Failed to upload: {res.text}")
            return
        
        data = res.json()
        dataset_id = data["dataset_id"]
        print(f"Uploaded successfully. Dataset ID: {dataset_id}")
        
        # 2. Test 5 intentional queries
        queries = [
            "total sales",
            "sales by segment",
            "best product per year",
            "top 5 countries by sales",
            "sales trend over time",
            "compare Asia vs Europe"
        ]
        
        for q in queries:
            print(f"\n--- Testing Query: '{q}' ---")
            payload = {
                "dataset_id": dataset_id,
                "question": q
            }
            start_time = time.time()
            q_res = client.post("http://127.0.0.1:8000/query", headers=headers, json=payload, timeout=60.0)
            elapsed = time.time() - start_time
            
            if q_res.status_code == 200:
                body = q_res.json()
                print(f"[SUCCESS] (Took {elapsed:.2f}s)")
                print(f"SQL Generated:\n{body.get('sql')}")
                print(f"Plan: {body.get('execution_plan')}")
                print(f"Explanation: {body.get('explanation')}")
                print(f"Insights (V4): {body.get('insights')}")
                data_preview = body.get('data', [])[:3]
                print(f"Data Preview ({len(body.get('data', []))} rows total): {data_preview}")
            else:
                print(f"[ERROR] Status: {q_res.status_code}")
                print(q_res.text)

    # ── Final Cache Hit Test ──
    print("\n--- Testing Cache Hit: 'total sales' again ---")
    start = time.time()
    with httpx.Client() as client:
        q_res = client.post("http://127.0.0.1:8000/query", json={"question": "total sales", "dataset_id": dataset_id}, headers=headers, timeout=60.0)
        elapsed = time.time() - start
        if q_res.status_code == 200:
            body = q_res.json()
            print(f"[SUCCESS] (Took {elapsed:.2f}s)")
            print(f"Plan: {body.get('execution_plan')}")
            print(f"Explanation: {body.get('explanation')}")
        else:
            print(f"[FAILED] {q_res.text}")

if __name__ == "__main__":
    test_pipeline()

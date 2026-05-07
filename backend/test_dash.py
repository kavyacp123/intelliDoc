import requests

# 1. Login to get token
r = requests.post("http://localhost:8000/auth/login", data={"username": "test@example.com", "password": "password"})
token = r.json().get("access_token")
headers = {"Authorization": f"Bearer {token}"}

# 2. Get latest dataset
datasets = requests.get("http://localhost:8000/datasets", headers=headers).json()
if datasets:
    latest = datasets[0]
    print(f"Latest dataset: {latest['file_name']} (ID: {latest['dataset_id']})")
    
    # 3. Call executive dashboard
    dash = requests.post("http://localhost:8000/dashboard/executive", json={"dataset_id": latest["dataset_id"]}, headers=headers)
    print("Dashboard Response Status:", dash.status_code)
    try:
        data = dash.json()
        print("Detected fields:", data.get("detected_fields"))
        print("Notes:", data.get("notes"))
        print("KPIs:", [k["name"] for k in data.get("kpis", [])])
        print("Sections:", [s["title"] for s in data.get("sections", [])])
    except Exception as e:
        print("Error parsing json:", dash.text)
else:
    print("No datasets found.")

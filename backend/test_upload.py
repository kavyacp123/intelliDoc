import httpx
from app.core.security import create_access_token

def test_upload():
    token = create_access_token({"sub": "test_tenant"})
    print("Token generated")
    
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("Financial Sample.xlsx", open("../Financial Sample.xlsx", "rb"), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    
    with httpx.Client() as client:
        response = client.post("http://127.0.0.1:8000/upload", headers=headers, files=files, timeout=60.0)
        print(response.status_code)
        print(response.text)

if __name__ == "__main__":
    test_upload()

import os
import sys

workspace_dir = "/Users/kavyapatel/Desktop/final inteldoc "
backend_dir = os.path.join(workspace_dir, "intelliDoc", "backend")
sys.path.insert(0, backend_dir)

from app.services.file_service import process_upload

def test():
    file_path = os.path.join(workspace_dir, "SR_22-23.xls")
    with open(file_path, "rb") as f:
        file_bytes = f.read()
    
    try:
        process_upload(file_bytes, "SR_22-23.xls", "test-tenant-123")
        print("Success")
    except Exception as e:
        import traceback
        traceback.print_exc()

test()

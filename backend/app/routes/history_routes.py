from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
import json

from app.core.database import get_connection
from app.core.security import get_current_user

router = APIRouter(tags=["History"])

class ChatMessage(BaseModel):
    id: str
    dataset_id: str
    message: Dict[str, Any]

@router.get("/chat_history/{dataset_id}", summary="Get chat history for a dataset")
async def get_chat_history(dataset_id: str, current_user: str = Depends(get_current_user)):
    conn = get_connection()
    # Verify dataset ownership first
    row = conn.execute(
        "SELECT tenant_id FROM datasets WHERE dataset_id = ?",
        [dataset_id]
    ).fetchone()
    
    if not row or row[0] != current_user:
        raise HTTPException(status_code=403, detail="Dataset not found or access denied")
        
    rows = conn.execute(
        "SELECT message FROM chat_history WHERE dataset_id = ? AND tenant_id = ? ORDER BY created_at ASC",
        [dataset_id, current_user]
    ).fetchall()
    
    messages = []
    for r in rows:
        try:
            messages.append(json.loads(r[0]))
        except:
            pass
            
    return {"messages": messages}

@router.post("/chat_history", summary="Save a chat message")
async def save_chat_message(msg: ChatMessage, current_user: str = Depends(get_current_user)):
    conn = get_connection()
    
    # Verify dataset ownership
    row = conn.execute(
        "SELECT tenant_id FROM datasets WHERE dataset_id = ?",
        [msg.dataset_id]
    ).fetchone()
    
    if not row or row[0] != current_user:
        raise HTTPException(status_code=403, detail="Dataset not found or access denied")
        
    message_json = json.dumps(msg.message)
    
    try:
        conn.execute(
            """
            INSERT INTO chat_history (id, dataset_id, tenant_id, message) 
            VALUES (?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET message = excluded.message
            """,
            [msg.id, msg.dataset_id, current_user, message_json]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    return {"status": "saved"}

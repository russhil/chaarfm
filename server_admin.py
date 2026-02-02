
import os
import json
import datetime
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from pydantic import BaseModel

import user_db

app = FastAPI(title="Chaar.fm Admin", description="Analytics Dashboard")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Initialize DB if needed (should be done by server_user.py, but safe to call)
user_db.init_db()

class ChatRequest(BaseModel):
    user_id: str
    message: str
    api_key: str

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """Serve the admin dashboard."""
    return templates.TemplateResponse("admin.html", {"request": request})

@app.get("/api/admin/stats")
async def get_stats(session_id: str = Query(None)):
    """Get aggregated statistics for the dashboard."""
    # Verify session if needed, but for admin we might want a separate auth.
    # For now, open or basic check.
    
    stats = {
        "global": {
            "total_plays": 0,
            "avg_listen_time": 0,
            "skip_rate": 0
        },
        "users": {}
    }
    
    with user_db.engine.connect() as conn:
        # Global Stats
        res = conn.execute(text("""
            SELECT 
                COUNT(*) as total,
                AVG(duration) as avg_dur,
                SUM(CASE WHEN action='skip' OR duration < 20 THEN 1 ELSE 0 END) as skips
            FROM user_logs
            WHERE action IN ('play', 'feedback', 'skip')
        """)).mappings().fetchone()
        
        if res and res['total'] > 0:
            stats['global']['total_plays'] = res['total']
            stats['global']['avg_listen_time'] = res['avg_dur'] or 0
            stats['global']['skip_rate'] = (res['skips'] or 0) / res['total']
            
        # User Stats
        users_res = conn.execute(text("""
            SELECT 
                user_id,
                COUNT(*) as total,
                AVG(duration) as avg_dur,
                SUM(CASE WHEN action='skip' OR duration < 20 THEN 1 ELSE 0 END) as skips
            FROM user_logs
            WHERE action IN ('play', 'feedback', 'skip') AND user_id IS NOT NULL
            GROUP BY user_id
        """)).mappings().fetchall()
        
        for row in users_res:
            uid = row['user_id']
            total = row['total']
            if total > 0:
                stats['users'][uid] = {
                    "total_plays": total,
                    "avg_listen_time": row['avg_dur'] or 0,
                    "skip_rate": (row['skips'] or 0) / total,
                    "engagement_growth": 0 # Placeholder
                }
                
    return stats

@app.get("/api/admin/logs")
async def get_logs(limit: int = 50):
    """Get recent logs."""
    logs = []
    with user_db.engine.connect() as conn:
        res = conn.execute(text("""
            SELECT * FROM user_logs 
            ORDER BY timestamp DESC 
            LIMIT :lim
        """), {"lim": limit}).mappings().fetchall()
        
        for row in res:
            logs.append(dict(row))
            
    return logs

@app.post("/api/admin/chat")
async def admin_chat(data: ChatRequest):
    """Chat with Gemma (Mock for now)."""
    # Here we would integrate with Google AI Studio API using data.api_key
    # For now, return a placeholder response.
    
    return {
        "response": f"Analyzing user {data.user_id}... [Gemma Integration Placeholder]. \n\nBased on the logs, this user prefers high-energy tracks in the morning."
    }

if __name__ == "__main__":
    import uvicorn
    print("Starting Admin Server on port 5002...")
    uvicorn.run(app, host="0.0.0.0", port=5002)

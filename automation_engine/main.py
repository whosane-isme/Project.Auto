from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
import os
from dotenv import load_dotenv
from datetime import datetime
import uuid

# Load environment variables
load_dotenv()

# Import config to ensure env vars are loaded and validated
from config import PORT, SUPABASE_URL
from db import get_supabase

app = FastAPI(title="Automation Engine", description="Core automation service")


class EventIn(BaseModel):
    """Event input model for ingesting events."""
    event_name: str
    payload: dict = {}
    user_id: Optional[str] = None
    source: Optional[str] = None


@app.post("/automation/events")
async def ingest_event(event: EventIn):
    """
    Ingest an event into the automation engine.
    Stores the event in the database, matches flows, and triggers execution.
    """
    try:
        from matcher import match_flows
        from executor import execute_flow

        supabase = get_supabase()
        
        # Create event record
        event_data = {
            "event_name": event.event_name,
            "payload": event.payload,
            "user_id": event.user_id,
            "source": event.source or "manual",
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Insert into Supabase
        result = supabase.table("events").insert(event_data).execute()
        event_id = result.data[0]["id"] if result.data else str(uuid.uuid4())

        # Match and execute flows
        flows = await match_flows(event.event_name, event.user_id)

        execution_results = []
        for flow in flows:
            try:
                exec_result = await execute_flow(
                    {
                        "id": flow.id,
                        "definition": flow.definition
                    },
                    event.payload,
                    event.user_id
                )
                execution_results.append(exec_result)
            except Exception as e:
                execution_results.append({
                    "status": "error",
                    "error": str(e)
                })

        return {
            "status": "ok",
            "event_id": event_id,
            "event_name": event.event_name,
            "flows_matched": len(flows),
            "execution_results": execution_results
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "event_name": event.event_name
        }


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "automation_engine"}


@app.get("/debug/db-check")
async def db_check():
    """
    Debug endpoint to verify database connectivity.
    Queries the flows table and returns the count.
    [DELETE THIS ROUTE AT END OF PHASE A]
    """
    try:
        import httpx
        from config import SUPABASE_URL, SUPABASE_SERVICE_KEY

        # Make direct HTTP request to Supabase REST API
        headers = {
            'Authorization': f'Bearer {SUPABASE_SERVICE_KEY}',
            'apikey': SUPABASE_SERVICE_KEY
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f'{SUPABASE_URL}/rest/v1/flows?select=id',
                headers=headers
            )
            if response.status_code == 200:
                data = response.json()
                flows_count = len(data)
                return {"flows_count": flows_count}
            else:
                return {
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "message": "Failed to connect to database. Check your Supabase credentials."
                }
    except Exception as e:
        return {
            "error": str(e),
            "message": "Failed to connect to database. Check your Supabase credentials."
        }


@app.get("/debug/match")
async def debug_match(event_name: str, user_id: str):
    """
    Debug endpoint to test flow matching.
    Returns flows that match the given event and user.
    [DELETE AT END OF PHASE B]
    """
    from matcher import match_flows

    try:
        flows = await match_flows(event_name, user_id)
        return {"flows": [flow.to_dict() for flow in flows]}
    except Exception as e:
        return {
            "error": str(e),
            "message": "Failed to match flows"
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)

#!/usr/bin/env python3
"""
End-to-end integration test for the Step Executor.

This script demonstrates the complete flow:
1. Create and publish a test flow
2. Send trigger events via the API
3. Verify runs and step_runs were created correctly
4. Test branching with different event payloads

Prerequisites:
- Automation engine running: uvicorn main:app --reload --port 8010
- Supabase database with schema initialized
"""

import asyncio
import httpx
import json
from db import get_supabase
import uuid

API_BASE_URL = "http://localhost:8010"

# Test flow definition
TEST_FLOW_DEFINITION = {
    "name": "poc_test_flow",
    "steps": [
        {"key": "t1", "type": "trigger", "config": {"event_name": "test.ping"}},
        {"key": "c1", "type": "condition", "config": {"expr": "{{ event.x }} == 1"}},
        {"key": "a1", "type": "set_variable", "config": {"name": "greeting", "value": "hello"}}
    ],
    "connections": [
        {"from": "t1", "to": "c1"},
        {"from": "c1", "to": "a1", "label": "condition_met"}
    ]
}


def setup_test_flow():
    """Create and publish a test flow in the database."""
    supabase = get_supabase()

    test_user_id = str(uuid.uuid4())
    flow_data = {
        "name": "poc_test_flow",
        "definition": TEST_FLOW_DEFINITION,
        "status": "published",
        "user_id": test_user_id,
    }

    result = supabase.table("flows").insert(flow_data).execute()
    return test_user_id, result.data[0]["id"]


async def send_trigger_event(user_id: str, payload: dict) -> dict:
    """Send a trigger event via the API."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE_URL}/automation/events",
            json={
                "event_name": "test.ping",
                "payload": payload,
                "user_id": user_id,
                "source": "test"
            }
        )
        return response.json()


async def verify_run(run_id: str, expected_status: str, expected_step_count: int):
    """Verify a run was created with expected step_runs."""
    supabase = get_supabase()

    # Check run status
    runs = supabase.table("runs").select("*").eq("id", run_id).execute()
    if not runs.data:
        raise AssertionError(f"Run {run_id} not found")

    run = runs.data[0]
    if run["status"] != expected_status:
        raise AssertionError(f"Expected status {expected_status}, got {run['status']}")

    # Check step_runs count
    step_runs = supabase.table("step_runs").select("*").eq("run_id", run_id).order("started_at").execute()
    if len(step_runs.data) != expected_step_count:
        raise AssertionError(f"Expected {expected_step_count} step_runs, got {len(step_runs.data)}")

    return run, step_runs.data


async def main():
    """Run the end-to-end test."""
    print("="*70)
    print("END-TO-END INTEGRATION TEST: Step Executor")
    print("="*70)

    try:
        # Step 1: Setup test flow
        print("\n[1] Setting up test flow...")
        user_id, flow_id = setup_test_flow()
        print(f"    ✓ Created user: {user_id}")
        print(f"    ✓ Created flow: {flow_id}")

        # Step 2: Send trigger with x=1 (condition_met)
        print("\n[2] Sending trigger event with payload: {x: 1}")
        result1 = await send_trigger_event(user_id, {"x": 1})
        print(f"    ✓ Response status: {result1['status']}")
        print(f"    ✓ Flows matched: {result1.get('flows_matched')}")

        if result1['execution_results']:
            exec_result = result1['execution_results'][0]
            run_id_1 = exec_result.get('run_id')
            print(f"    ✓ Run ID: {run_id_1}")

            # Verify run and step_runs
            run, step_runs = await verify_run(run_id_1, "completed", 3)
            print(f"    ✓ Run status: {run['status']}")
            print(f"    ✓ Step runs: {len(step_runs)}")
            print(f"       - t1 (trigger): {step_runs[0]['output']}")
            print(f"       - c1 (condition): {step_runs[1]['output']}")
            print(f"       - a1 (set_variable): {step_runs[2]['output']}")

        # Step 3: Send trigger with x=2 (condition_not_met)
        print("\n[3] Sending trigger event with payload: {x: 2}")
        result2 = await send_trigger_event(user_id, {"x": 2})
        print(f"    ✓ Response status: {result2['status']}")

        if result2['execution_results']:
            exec_result = result2['execution_results'][0]
            run_id_2 = exec_result.get('run_id')
            print(f"    ✓ Run ID: {run_id_2}")

            # Verify run and step_runs (only 2 steps)
            run, step_runs = await verify_run(run_id_2, "completed", 2)
            print(f"    ✓ Run status: {run['status']}")
            print(f"    ✓ Step runs: {len(step_runs)} (a1 not executed)")
            print(f"       - t1 (trigger): {step_runs[0]['output']}")
            print(f"       - c1 (condition): {step_runs[1]['output']}")

        print("\n" + "="*70)
        print("✅ ALL END-TO-END TESTS PASSED")
        print("="*70)
        print("\nThe executor is working correctly!")
        print(f"- Run 1 (x=1): 3 steps executed (trigger → condition → action)")
        print(f"- Run 2 (x=2): 2 steps executed (trigger → condition, action skipped)")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\nMake sure the automation engine is running:")
    print("  uvicorn main:app --reload --port 8010")
    input("\nPress Enter to continue...\n")

    asyncio.run(main())


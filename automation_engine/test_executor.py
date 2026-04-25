"""
Integration test for the step executor.
Tests flow execution with trigger events, conditions, and branching.
"""

import asyncio
import json
from db import get_supabase
from executor import execute_flow
import uuid

# Test flow matching the test_flow.json fixture
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

TEST_USER_ID = str(uuid.uuid4())  # Use a proper UUID for user_id


async def setup_test_flow():
    """Create and publish a test flow in the database."""
    supabase = get_supabase()

    flow_data = {
        "name": "poc_test_flow",
        "definition": TEST_FLOW_DEFINITION,
        "status": "published",
        "user_id": TEST_USER_ID,
    }

    result = supabase.table("flows").insert(flow_data).execute()
    return result.data[0]["id"]


async def test_execution_x_equals_1():
    """Test execution with event.x == 1 (condition_met, a1 should execute)."""
    print("\n" + "="*60)
    print("TEST 1: Execute with event.x == 1 (condition_met)")
    print("="*60)

    supabase = get_supabase()

    # Setup flow
    flow_id = await setup_test_flow()
    print(f"[OK] Published test flow: {flow_id}")

    # Get the flow
    flow_result = supabase.table("flows").select("*").eq("id", flow_id).execute()
    flow = {
        "id": flow_result.data[0]["id"],
        "definition": flow_result.data[0]["definition"]
    }

    # Execute with x=1
    trigger_event = {"x": 1}
    result = await execute_flow(flow, trigger_event, TEST_USER_ID)

    print(f"[OK] Execution result: {result['status']}")
    print(f"  Run ID: {result.get('run_id')}")
    print(f"  Execution count: {result.get('execution_count')}")

    # Query runs
    run_id = result.get("run_id")
    runs = supabase.table("runs").select("*").eq("id", run_id).execute()
    run = runs.data[0]
    print(f"\n[OK] Run status: {run['status']}")
    if run['status'] == 'failed':
        print(f"  Error: {run.get('error_message')}")
    assert run["status"] == "completed", f"Expected status 'completed', got '{run['status']}'"

    # Query step_runs
    step_runs = supabase.table("step_runs").select("*").eq("run_id", run_id).order("started_at").execute()
    print(f"[OK] Step runs count: {len(step_runs.data)} (expected 3)")
    assert len(step_runs.data) == 3, f"Expected 3 step_runs, got {len(step_runs.data)}"

    # Verify each step
    for i, sr in enumerate(step_runs.data):
        print(f"\n  Step {i+1}: {sr['step_key']}")
        print(f"    Status: {sr['status']}")
        print(f"    Output: {sr['output']}")
        assert sr["status"] == "completed", f"Expected status 'completed' for step {sr['step_key']}"

    # Verify t1 output (trigger)
    assert step_runs.data[0]["step_key"] == "t1"
    assert step_runs.data[0]["output"]["event_name"] == "test.ping"

    # Verify c1 output (condition - true)
    assert step_runs.data[1]["step_key"] == "c1"
    assert step_runs.data[1]["output"]["result"] == True, "Expected condition result=true for x=1"

    # Verify a1 output (set_variable)
    assert step_runs.data[2]["step_key"] == "a1"
    assert step_runs.data[2]["output"]["name"] == "greeting"
    assert step_runs.data[2]["output"]["value"] == "hello"

    print("\n✅ TEST 1 PASSED")
    return run_id


async def test_execution_x_equals_2():
    """Test execution with event.x == 2 (condition_not_met, a1 should NOT execute)."""
    print("\n" + "="*60)
    print("TEST 2: Execute with event.x == 2 (condition_not_met)")
    print("="*60)

    supabase = get_supabase()

    # Setup flow
    flow_id = await setup_test_flow()
    print(f"[OK] Published test flow: {flow_id}")

    # Get the flow
    flow_result = supabase.table("flows").select("*").eq("id", flow_id).execute()
    flow = {
        "id": flow_result.data[0]["id"],
        "definition": flow_result.data[0]["definition"]
    }

    # Execute with x=2
    trigger_event = {"x": 2}
    result = await execute_flow(flow, trigger_event, TEST_USER_ID)

    print(f"[OK] Execution result: {result['status']}")
    print(f"  Run ID: {result.get('run_id')}")
    print(f"  Execution count: {result.get('execution_count')}")

    # Query runs
    run_id = result.get("run_id")
    runs = supabase.table("runs").select("*").eq("id", run_id).execute()
    run = runs.data[0]
    print(f"\n[OK] Run status: {run['status']}")
    assert run["status"] == "completed", f"Expected status 'completed', got '{run['status']}'"

    # Query step_runs
    step_runs = supabase.table("step_runs").select("*").eq("run_id", run_id).order("started_at").execute()
    print(f"[OK] Step runs count: {len(step_runs.data)} (expected 2 - a1 should not execute)")
    assert len(step_runs.data) == 2, f"Expected 2 step_runs, got {len(step_runs.data)}"

    # Verify each step
    for i, sr in enumerate(step_runs.data):
        print(f"\n  Step {i+1}: {sr['step_key']}")
        print(f"    Status: {sr['status']}")
        print(f"    Output: {sr['output']}")
        assert sr["status"] == "completed", f"Expected status 'completed' for step {sr['step_key']}"

    # Verify t1 output (trigger)
    assert step_runs.data[0]["step_key"] == "t1"

    # Verify c1 output (condition - false)
    assert step_runs.data[1]["step_key"] == "c1"
    assert step_runs.data[1]["output"]["result"] == False, "Expected condition result=false for x=2"

    print("\n✅ TEST 2 PASSED")
    return run_id


async def main():
    """Run all tests."""
    print("Starting Step Executor Tests...")
    print(f"Using test user: {TEST_USER_ID}")

    try:
        # Test 1: x == 1 (condition met, all 3 steps execute)
        await test_execution_x_equals_1()

        # Test 2: x == 2 (condition not met, only 2 steps execute)
        await test_execution_x_equals_2()

        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED")
        print("="*60)

    except Exception as e:
        print(f"\n[FAIL] TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())


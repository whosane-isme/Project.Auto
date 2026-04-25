# Task 13 - Step Executor Testing Guide

This guide shows you exactly how to test and verify the step executor implementation.

## Prerequisites

1. **Database Setup**: Ensure Supabase is running and schema is initialized
2. **Dependencies**: All required packages installed (`pip install -r requirements.txt`)
3. **Server Running** (for E2E tests): `uvicorn main:app --reload --port 8010`

## Quick Start

Run the comprehensive verification script:

```bash
cd C:\Users\iix_m\PycharmProjects\PythonProject\auto-main\automation_engine
python verify_task13.py
```

This will automatically:
- Create test flows in the database
- Execute flows with different payloads
- Verify runs and step_runs are created correctly
- Test branching logic (condition_met vs condition_not_met)
- Verify max execution cap

## Detailed Test Scenarios

### Test 1: Condition Met (x=1)

**What it tests:**
- Flow executes all 3 steps when condition is true
- Branching takes the `condition_met` path
- All step_runs are created with correct outputs

**Expected behavior:**
```
Event: {"x": 1}
Flow: t1 (trigger) → c1 (condition) → a1 (set_variable)
Steps executed: 3
Run status: completed
```

**Database verification:**
```sql
-- Check run status
SELECT id, status FROM runs ORDER BY started_at DESC LIMIT 1;
-- Expected: status='completed'

-- Check step_runs
SELECT step_key, status, output 
FROM step_runs 
WHERE run_id = '<run_id_from_above>' 
ORDER BY started_at;

-- Expected results:
-- step_key | status    | output
-- ---------|-----------|----------------------------------
-- t1       | completed | {"event_name": "test.ping", ...}
-- c1       | completed | {"result": true}
-- a1       | completed | {"name": "greeting", "value": "hello"}
```

**How to run:**
```bash
python test_executor.py
# or
python verify_task13.py
```

---

### Test 2: Condition Not Met (x=2)

**What it tests:**
- Flow skips steps when condition is false
- Branching correctly avoids the `condition_met` path
- Only 2 step_runs are created (a1 is NOT executed)

**Expected behavior:**
```
Event: {"x": 2}
Flow: t1 (trigger) → c1 (condition) → [a1 SKIPPED]
Steps executed: 2
Run status: completed
```

**Database verification:**
```sql
-- Check run status
SELECT id, status FROM runs ORDER BY started_at DESC LIMIT 1;
-- Expected: status='completed'

-- Check step_runs (should be only 2!)
SELECT step_key, status, output 
FROM step_runs 
WHERE run_id = '<run_id_from_above>' 
ORDER BY started_at;

-- Expected results:
-- step_key | status    | output
-- ---------|-----------|----------------------------------
-- t1       | completed | {"event_name": "test.ping", ...}
-- c1       | completed | {"result": false}
-- NOTE: a1 is NOT in the results!
```

**How to run:**
```bash
python test_executor.py
# or
python verify_task13.py
```

---

### Test 3: End-to-End via API

**What it tests:**
- Complete integration from API endpoint to database
- Flow matching works correctly
- Executor is invoked automatically

**How to run:**

1. **Start the server** (Terminal 1):
```bash
cd C:\Users\iix_m\PycharmProjects\PythonProject\auto-main\automation_engine
uvicorn main:app --reload --port 8010
```

2. **Run E2E tests** (Terminal 2):
```bash
python test_e2e.py
```

**Manual API testing:**

```bash
# Test 1: condition_met
curl -s -X POST http://localhost:8010/automation/events \
  -H "Content-Type: application/json" \
  -d '{
    "event_name": "test.ping",
    "payload": {"x": 1},
    "user_id": "your-user-uuid",
    "source": "test"
  }'

# Test 2: condition_not_met
curl -s -X POST http://localhost:8010/automation/events \
  -H "Content-Type: application/json" \
  -d '{
    "event_name": "test.ping",
    "payload": {"x": 2},
    "user_id": "your-user-uuid",
    "source": "test"
  }'
```

**Expected response:**
```json
{
  "status": "ok",
  "event_id": "event-uuid",
  "event_name": "test.ping",
  "flows_matched": 1,
  "execution_results": [
    {
      "status": "ok",
      "run_id": "run-uuid",
      "execution_count": 3,
      "step_outputs": {
        "t1": {"event_name": "test.ping", "payload": {"x": 1}},
        "c1": {"result": true},
        "a1": {"name": "greeting", "value": "hello"}
      }
    }
  ]
}
```

---

### Test 4: Unit Tests

**What it tests:**
- Individual handlers work correctly
- Variable resolution works
- Handler contract is satisfied

**How to run:**
```bash
pytest tests/ -v
```

**Expected output:**
```
tests/test_handlers.py::test_trigger_returns_event PASSED
tests/test_handlers.py::test_condition_true PASSED
tests/test_handlers.py::test_condition_false PASSED
tests/test_handlers.py::test_condition_with_template PASSED
tests/test_handlers.py::test_condition_with_step_reference PASSED
tests/test_handlers.py::test_set_variable PASSED
tests/test_resolver.py::test_simple_event_var PASSED
tests/test_resolver.py::test_nested PASSED
tests/test_resolver.py::test_unknown_var_raises PASSED
```

---

## Understanding the Test Flow

All tests use the same flow definition:

```json
{
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
```

**Flow visualization:**
```
┌──────────────────────────────────────────────┐
│                                              │
│  t1 (trigger) ──────────────────┐            │
│                                  │            │
│                                  ▼            │
│  c1 (condition: x == 1) ────────┤            │
│    │                            │            │
│    │ condition_met              │            │
│    ▼                            │            │
│  a1 (set_variable)              │            │
│                                  │            │
└──────────────────────────────────────────────┘
```

**Execution paths:**
- When `x=1`: `t1 → c1 → a1` (3 steps, condition_met branch taken)
- When `x=2`: `t1 → c1` (2 steps, condition_not_met, a1 skipped)

---

## Troubleshooting

### Issue: No flows matched

**Symptom:** API returns `"flows_matched": 0`

**Solution:**
1. Ensure flow is inserted into database with correct `user_id`
2. Ensure flow `status` is `'published'`
3. Ensure flow definition has a trigger step with matching `event_name`

```sql
-- Check your flows
SELECT id, name, status, definition->>'steps' as steps
FROM flows 
WHERE user_id = 'your-user-id';
```

### Issue: Run status is 'failed'

**Symptom:** Run created but status is `'failed'`

**Solution:**
1. Check `error_message` in runs table:
```sql
SELECT id, status, error_message FROM runs ORDER BY started_at DESC LIMIT 1;
```

2. Common errors:
   - `Unknown handler type`: Check step type is registered in HANDLERS
   - `Undefined variable`: Check template variables exist in context
   - `StepError`: Check handler-specific error messages

### Issue: Step runs not created

**Symptom:** Run exists but no step_runs

**Solution:**
1. Check executor is being called (add print statements)
2. Verify database connection is working
3. Check Supabase permissions for `step_runs` table

---

## What to Look For in Test Results

### ✅ Success Indicators

1. **Run status**: Should be `'completed'` for successful executions
2. **Step count**: 
   - Test 1 (x=1): Exactly 3 step_runs
   - Test 2 (x=2): Exactly 2 step_runs
3. **Condition results**:
   - Test 1: `c1.output.result = true`
   - Test 2: `c1.output.result = false`
4. **Step outputs**: All should be non-null JSON objects
5. **Duration**: All steps should have `duration_ms > 0`

### ❌ Failure Indicators

1. **Run status = 'failed'**: Check error_message
2. **Wrong step count**: Branching logic issue
3. **Missing outputs**: Handler didn't return expected data
4. **Null duration_ms**: Timing code not executing
5. **Execution count > 100**: Infinite loop detected

---

## Advanced Testing

### Test Variable Resolution

```python
from executor import execute_flow

flow = {
    "id": "test-flow",
    "definition": {
        "steps": [
            {"key": "t1", "type": "trigger", "config": {"event_name": "test"}},
            {"key": "s1", "type": "set_variable", "config": {"name": "val", "value": 42}},
            {"key": "c1", "type": "condition", "config": {"expr": "{{ steps.s1.value }} == 42"}}
        ],
        "connections": [
            {"from": "t1", "to": "s1"},
            {"from": "s1", "to": "c1"},
            {"from": "c1", "to": "end", "label": "condition_met"}
        ]
    }
}

result = await execute_flow(flow, {}, "user-id")
# Should execute all 3 steps
```

### Test Error Handling

```python
flow = {
    "id": "test-flow",
    "definition": {
        "steps": [
            {"key": "t1", "type": "trigger", "config": {"event_name": "test"}},
            {"key": "c1", "type": "condition", "config": {"expr": "{{ event.missing }} == 1"}}
        ],
        "connections": [
            {"from": "t1", "to": "c1"}
        ]
    }
}

result = await execute_flow(flow, {}, "user-id")
# Should fail with StepError: undefined variable
```

---

## Summary

| Test | Command | What It Verifies |
|------|---------|------------------|
| Comprehensive Verification | `python verify_task13.py` | All Task 13 requirements |
| Integration Tests | `python test_executor.py` | Branching logic |
| End-to-End Tests | `python test_e2e.py` | Full API integration |
| Unit Tests | `pytest tests/ -v` | Individual handlers |
| Manual API Test | `curl ...` | Real-world usage |

**Recommended workflow:**
1. Run `python verify_task13.py` for comprehensive check
2. If issues, run `python test_executor.py` for detailed output
3. For API issues, run `python test_e2e.py` with server running
4. For handler issues, run `pytest tests/ -v`

All tests should pass for Task 13 to be considered complete! ✅

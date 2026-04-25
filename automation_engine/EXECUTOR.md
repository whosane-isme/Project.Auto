# Step Executor Implementation

## Overview

The Step Executor walks a flow's directed acyclic graph (DAG), executing steps in sequence, branching based on conditions, and persisting execution state to the database.

## Architecture

### Flow Definition Structure

```json
{
  "name": "flow_name",
  "steps": [
    {
      "key": "step_identifier",
      "type": "handler_type",
      "config": { "option": "value" }
    }
  ],
  "connections": [
    {
      "from": "step_key_1",
      "to": "step_key_2",
      "label": "condition_met"  // optional
    }
  ]
}
```

### Execution Flow

1. **Event Ingestion** → `/automation/events` endpoint
2. **Flow Matching** → Find all published flows matching the event
3. **Executor Invocation** → `execute_flow()` for each matching flow
4. **DAG Traversal** → Execute steps following connections
5. **Branching** → Route based on condition results or labels
6. **Persistence** → Create runs and step_runs records

## Key Components

### Database Tables

- **runs**: Records execution of a flow instance
  - `id`: UUID primary key
  - `flow_id`: Reference to flow
  - `status`: 'running', 'completed', 'failed', 'cancelled', 'skipped', 'waiting'
  - `started_at`: Execution start time
  - `completed_at`: Execution end time
  - `error_message`: Failure details if applicable

- **step_runs**: Records execution of individual steps
  - `id`: UUID primary key
  - `run_id`: Reference to parent run
  - `step_key`: Step identifier
  - `status`: Same as run status
  - `started_at`: Step start time
  - `completed_at`: Step end time
  - `output`: Step handler output (JSONB)
  - `duration_ms`: Execution time in milliseconds

### Branching Rules

#### Trigger Steps

After a trigger step, follow the **unlabeled** connection:

```json
{
  "from": "trigger_step",
  "to": "next_step"
  // Note: no label field
}
```

#### Condition Steps

Branch based on the `result` field of condition output:

- If `result == True` → Follow connection with label `"condition_met"`
- If `result == False` → Follow connection with label `"condition_not_met"`

Example:
```json
{
  "from": "condition_step",
  "to": "action_step_true",
  "label": "condition_met"
},
{
  "from": "condition_step",
  "to": "action_step_false",
  "label": "condition_not_met"
}
```

#### Other Steps

Follow the **unlabeled** connection (typically linear flow):

```json
{
  "from": "action_step",
  "to": "next_step"
  // No label
}
```

### Execution Context

Each step receives a context dictionary:

```python
{
  "event": { /* trigger event payload */ },
  "contact": { /* contact info if available */ },
  "steps": {
    "step_key_1": { /* handler output */ },
    "step_key_2": { /* handler output */ }
  }
}
```

## Usage

### Example: Simple Trigger → Condition → Action Flow

```python
from executor import execute_flow

flow = {
    "id": "flow-uuid",
    "definition": {
        "name": "ReplyOnPing",
        "steps": [
            {
                "key": "t1",
                "type": "trigger",
                "config": {"event_name": "test.ping"}
            },
            {
                "key": "c1",
                "type": "condition",
                "config": {"expr": "{{ event.x }} == 1"}
            },
            {
                "key": "a1",
                "type": "set_variable",
                "config": {"name": "greeting", "value": "hello"}
            }
        ],
        "connections": [
            {"from": "t1", "to": "c1"},
            {"from": "c1", "to": "a1", "label": "condition_met"}
        ]
    }
}

trigger_event = {"x": 1}
user_id = "user-uuid"

result = await execute_flow(flow, trigger_event, user_id)
# Result: {"status": "ok", "run_id": "run-uuid", ...}
```

### API Integration

When an event is posted to `/automation/events`:

```bash
curl -X POST http://localhost:8010/automation/events \
  -H "Content-Type: application/json" \
  -d '{
    "event_name": "test.ping",
    "payload": {"x": 1},
    "user_id": "user-uuid",
    "source": "test"
  }'
```

The endpoint:
1. Stores the event
2. Matches flows for the user and event
3. Executes each matching flow
4. Returns results

## Safety Limits

- **Max Executions**: 100 steps per run (prevents infinite loops)
- **Timeout**: 30 seconds per HTTP request (handlers may vary)
- **Error Handling**: Failed steps mark entire run as failed

## Error Handling

### Step Errors

If a handler raises `StepError`:
- Current step_run marked as 'failed'
- Run marked as 'failed'
- Execution stops
- Error message captured in run.error_message

### Network Errors

Handlers may raise `StepError` on network failures:
- HTTP request timeout
- Connection refused
- Invalid endpoint

### Template Resolution

If a handler fails to resolve templates:
- `StepError` raised with undefined variable details
- Run fails with error message

## Testing

### Unit Tests
```bash
pytest tests/test_handlers.py -v
pytest tests/test_resolver.py -v
```

### Executor Tests
```bash
# Direct executor tests
python test_executor.py

# End-to-end with API
uvicorn main:app --reload --port 8010
# In another terminal:
python test_e2e.py
```

## Implementation Details

### ExecutionContext Class

Tracks state during execution:
- `flow_id`: Flow being executed
- `user_id`: User who owns the flow
- `trigger_event`: Initial event payload
- `run_id`: Database run ID
- `step_outputs`: Results of executed steps
- `execution_count`: Steps executed (capped at 100)

### DAG Traversal Algorithm

1. Find trigger step (first step with type='trigger')
2. Execute trigger: creates trigger output
3. Find next step from connections (unlabeled edge)
4. Loop:
   - Execute current step
   - Store output in step_outputs
   - Determine next step (using branching rules)
   - If next_step is None, exit loop
5. Mark run as completed/failed

### Connection Graph

Built by grouping connections by source step:

```python
connections_graph = {
    "t1": [{"to": "c1", "label": ""}],
    "c1": [
        {"to": "a1", "label": "condition_met"},
        {"to": "a2", "label": "condition_not_met"}
    ]
}
```

## Supported Handlers

- **trigger**: Returns event payload
- **condition**: Evaluates boolean expression
- **set_variable**: Stores value for downstream steps
- **http_request**: Makes HTTP calls
- **adam_action**: Routes to external services

## Future Enhancements

1. **Parallel Execution**: Execute independent branches concurrently
2. **Loop Support**: Repeat steps based on conditions
3. **Error Handling Branches**: Route on error instead of just success/fail
4. **Retry Logic**: Automatic retry on network errors
5. **Logging**: Detailed execution logs with timestamps


# Automation Center — Intern Task Breakdown

**For:** Husein (backend intern)
**Stack:** FastAPI + Supabase + Celery/Redis
**Source spec:** [AUTOMATION_CENTER_ROADMAP.md](AUTOMATION_CENTER_ROADMAP.md)

## How to use this doc

Each task is **1–4 hours of work, one clear deliverable, one test at the end.**
Rules:
1. Do tasks in order. Do not start N+1 until task N's test passes.
2. Every task ends with a **TEST** block. If the test doesn't pass, the task is not done.
3. Paste the test command output into the PR description so reviewers can see proof.
4. One task = one commit = one PR. Keep PRs tiny.
5. Ask before skipping a step or taking a shortcut.

Path: all work happens in a new backend repo/service at
`C:\Users\HP\Videos\admin\automation_engine\` (separate deploy, not mixed with existing backends).

---

## Phase A — Scaffolding (Tasks 1–3)

### Task 1 — Scaffold the FastAPI service
**Effort:** 1h
**Goal:** Empty FastAPI app runs locally and returns 200 on `/health`.

Steps:
1. Create folder `automation_engine/` with: `main.py`, `requirements.txt`, `.env.example`, `README.md`, `.gitignore`.
2. `requirements.txt`: `fastapi`, `uvicorn[standard]`, `pydantic`, `python-dotenv`, `httpx`, `supabase`, `jinja2`.
3. `main.py`: one route `GET /health` → `{"status":"ok","service":"automation_engine"}`.
4. `.env.example`: `SUPABASE_URL=`, `SUPABASE_SERVICE_KEY=`, `PORT=8010`.
5. Add `uvicorn main:app --reload --port 8010` to README.

**TEST:**
```bash
uvicorn main:app --port 8010 &
curl -s http://localhost:8010/health
# Expect: {"status":"ok","service":"automation_engine"}
```

---

### Task 2 — Create Supabase schema + tables
**Effort:** 2h
**Goal:** All 9 tables from roadmap section 2 exist in Supabase under schema `automation`.

Steps:
1. Create SQL migration file `automation_engine/migrations/001_init.sql`.
2. `CREATE SCHEMA IF NOT EXISTS automation;`
3. Create all 9 tables exactly as listed in roadmap §2 (flows, flow_versions, runs, step_runs, events, event_schemas, connections, webhook_endpoints, schedules).
4. Add the 3 indexes: `events(event_name, user_id, created_at desc)`, `runs(flow_id, started_at desc)`, `step_runs(run_id)`.
5. Add status enum `automation.run_status` with values `running, completed, failed, cancelled, skipped, waiting`.
6. Run the SQL in Supabase SQL editor. Do NOT add RLS yet — service key only for POC.

**TEST:**
```sql
-- Run in Supabase SQL editor, paste output in PR:
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'automation' ORDER BY table_name;
-- Expect: exactly 9 rows (the 9 tables).

SELECT indexname FROM pg_indexes WHERE schemaname = 'automation';
-- Expect: the 3 indexes listed above plus primary keys.
```

---

### Task 3 — Supabase client + config loader
**Effort:** 1h
**Goal:** `automation_engine` can read/write any `automation.*` table using the service key.

Steps:
1. `db.py`: function `get_supabase() -> Client` that reads `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` from env.
2. `config.py`: centralized env loader, fail fast if a required var is missing.
3. Add route `GET /debug/db-check` (DELETE THIS ROUTE AT END OF PHASE A) that does `SELECT count(*) FROM automation.flows`.

**TEST:**
```bash
curl -s http://localhost:8010/debug/db-check
# Expect: {"flows_count": 0}
```

---

## Phase B — Core engine POC (Tasks 4–13)

### Task 4 — Event ingestion endpoint
**Effort:** 1.5h
**Goal:** `POST /automation/events` accepts an event, writes to `automation.events`, returns the event id.

Steps:
1. Pydantic model `EventIn { event_name: str, payload: dict, user_id: UUID, contact_id: UUID | None, source: str }`.
2. Endpoint validates, inserts into `automation.events`, returns `{"event_id": ...}`.
3. Do NOT match flows yet — just persist.

**TEST:**
```bash
curl -s -X POST http://localhost:8010/automation/events \
  -H "Content-Type: application/json" \
  -d '{"event_name":"test.ping","payload":{"x":1},"user_id":"00000000-0000-0000-0000-000000000001","source":"manual"}'
# Expect: {"event_id": "<uuid>"}
# Verify: SELECT * FROM automation.events ORDER BY created_at DESC LIMIT 1;  -> your row
```

---

### Task 5 — Seed one hand-written flow
**Effort:** 1h
**Goal:** A test flow JSON exists in `automation.flows` with status=`published` — used by later tasks.

Steps:
1. Create `automation_engine/fixtures/test_flow.json`:
```json
{
  "name": "poc_test_flow",
  "steps": [
    { "key": "t1", "type": "trigger", "config": { "event_name": "test.ping" } },
    { "key": "c1", "type": "condition", "config": { "expr": "{{ event.x }} == 1" } },
    { "key": "a1", "type": "set_variable", "config": { "name": "greeting", "value": "hello" } }
  ],
  "connections": [
    { "from": "t1", "to": "c1" },
    { "from": "c1", "to": "a1", "label": "condition_met" }
  ]
}
```
2. Insert into Supabase with `status='published'`, pick any user_id.

**TEST:**
```sql
SELECT id, name, status, definition->>'name' FROM automation.flows;
-- Expect: 1 row, name='poc_test_flow', status='published'.
```

---

### Task 6 — Flow matcher
**Effort:** 1h
**Goal:** Given an event, return all published flows whose trigger.event_name matches.

Steps:
1. `matcher.py`: `async def match_flows(event_name, user_id) -> list[Flow]`.
2. Query `flows` where `status='published'` AND `user_id = :user_id` AND `definition->'steps'->0->>'event_name' = :event_name` (the first step is always the trigger per roadmap §3).
3. Add route `GET /debug/match?event_name=...&user_id=...` (DELETE AT END OF PHASE B).

**TEST:**
```bash
curl -s "http://localhost:8010/debug/match?event_name=test.ping&user_id=<user_from_task_5>"
# Expect: array with 1 flow (the poc_test_flow). Different event_name -> [].
```

---

### Task 7 — Jinja2 variable resolver
**Effort:** 1.5h
**Goal:** Function that takes a config dict + context and resolves `{{ event.x }}`, `{{ steps.foo.bar }}` templates. Unknown var → `StepError`.

Steps:
1. `resolver.py`: `resolve_vars(config: dict, context: dict) -> dict`.
2. Walk config recursively; for every string, run through `jinja2.Environment(undefined=StrictUndefined)`.
3. Raise `StepError` on `UndefinedError`.
4. Unit test file `tests/test_resolver.py`.

**TEST:**
```python
# tests/test_resolver.py — run with: pytest tests/test_resolver.py -v
def test_simple_event_var():
    ctx = {"event": {"x": 1}, "contact": {}, "steps": {}}
    assert resolve_vars({"v": "{{ event.x }}"}, ctx) == {"v": "1"}

def test_nested():
    ctx = {"event": {}, "contact": {}, "steps": {"s1": {"out": "done"}}}
    assert resolve_vars({"a": {"b": "{{ steps.s1.out }}"}}, ctx) == {"a": {"b": "done"}}

def test_unknown_var_raises():
    with pytest.raises(StepError):
        resolve_vars({"v": "{{ event.missing }}"}, {"event": {}, "contact": {}, "steps": {}})
```
All 3 tests must pass.

---

### Task 8 — Handler registry + `trigger` handler
**Effort:** 1h
**Goal:** `HANDLERS` dict exists. `trigger` handler is a no-op that returns the event payload.

Steps:
1. `handlers/__init__.py`: `HANDLERS: dict[str, Callable] = {}` + decorator `@handler("type_name")`.
2. `handlers/trigger.py`:
```python
@handler("trigger")
async def trigger_handler(config, context, run):
    return {"event_name": config["event_name"], "payload": context["event"]}
```

**TEST:**
```python
# tests/test_handlers.py
async def test_trigger_returns_event():
    out = await HANDLERS["trigger"](
        {"event_name": "test.ping"},
        {"event": {"x": 1}, "contact": {}, "steps": {}},
        None,
    )
    assert out == {"event_name": "test.ping", "payload": {"x": 1}}
```

---

### Task 9 — `condition` handler
**Effort:** 1.5h
**Goal:** Evaluates a boolean expression against context, returns `{"result": True|False}`.

Steps:
1. `handlers/condition.py`. Config: `{ "expr": "{{ event.x }} == 1" }`.
2. Use `simpleeval` lib (add to requirements) for safe eval — no Python exec.
3. Resolver runs first → expr becomes `"1 == 1"` → simpleeval returns True.
4. Output: `{"result": true_or_false}`.

**TEST:**
```python
async def test_condition_true():
    ctx = {"event": {"x": 1}, "contact": {}, "steps": {}}
    out = await HANDLERS["condition"]({"expr": "1 == 1"}, ctx, None)
    assert out == {"result": True}

async def test_condition_false():
    ctx = {"event": {"x": 2}, "contact": {}, "steps": {}}
    out = await HANDLERS["condition"]({"expr": "1 == 2"}, ctx, None)
    assert out == {"result": False}
```

---

### Task 10 — `set_variable` handler
**Effort:** 0.5h
**Goal:** Stores a value into `steps.<key>.value` so downstream steps can read it.

Steps:
1. `handlers/set_variable.py`. Config: `{ "name": "...", "value": <any> }`.
2. Output: `{"name": config["name"], "value": config["value"]}`.

**TEST:**
```python
async def test_set_variable():
    out = await HANDLERS["set_variable"]({"name": "g", "value": "hello"}, {}, None)
    assert out == {"name": "g", "value": "hello"}
```

---

### Task 11 — `http_request` handler
**Effort:** 2h
**Goal:** Makes an HTTP call to any URL and returns `{status, headers, body}`.

Steps:
1. `handlers/http_request.py`. Config: `{ method, url, headers?, body?, timeout_seconds? }`.
2. Use `httpx.AsyncClient`. Default timeout 10s, max 60s.
3. Output: `{"status": int, "headers": dict, "body": json-or-str}`. Try `.json()`, fall back to text.
4. On 5xx → still return the response (do NOT raise — that's retry policy, later phase).
5. On network error → `StepError`.

**TEST:**
```bash
# With engine running, manually exercise via Python REPL or a small script:
python -c "
import asyncio
from handlers import HANDLERS
out = asyncio.run(HANDLERS['http_request']({'method':'GET','url':'https://httpbin.org/get'}, {}, None))
assert out['status'] == 200
assert 'headers' in out
print('OK')
"
```

---

### Task 12 — `adam_action` handler (single endpoint wired)
**Effort:** 2h
**Goal:** Wire ONE real Adam endpoint to prove the pattern. Pick `whatsapp.send_freeform` (simplest).

Steps:
1. `handlers/adam_action.py`. Config: `{ action: str, params: dict }` where action is a dotted name like `whatsapp.send_freeform`.
2. Internal registry `ADAM_ENDPOINTS = { "whatsapp.send_freeform": { "base": "https://whatsapp-mfpm.onrender.com", "path": "/send-message", "method": "POST" } }` (verify exact path against `backend_whatsapp` repo).
3. Handler resolves action → URL → calls via httpx with service auth header → returns `{status, body}`.
4. Only this one action for now. Others come in Phase 2.

**TEST:**
```bash
# 1) Test with a real whatsapp_connection_id from backend_whatsapp (ask Muammal for a dev one).
python -c "
import asyncio
from handlers.adam_action import handler
out = asyncio.run(handler(
    {'action':'whatsapp.send_freeform',
     'params':{'connection_id':'<dev_id>','to':'<test_number>','text':'automation test'}},
    {}, None
))
print(out)
assert out['status'] in (200, 202)
"
# 2) Verify message arrived in test WhatsApp inbox.
```

---

### Task 13 — Step executor (walks the DAG)
**Effort:** 3h
**Goal:** Given a flow + trigger event, executes all steps in order, branches on condition labels, persists `runs` + `step_runs`.

Steps:
1. `executor.py`: async function `execute_flow(flow, trigger_event)` matching the pseudocode in roadmap §5.
2. Create `runs` row (status=running) at start, mark completed/failed at end.
3. For every step: create `step_runs` row (status=running), call handler, update with output/duration.
4. Branching rule: after a `condition` step, take the outgoing connection whose `label` matches `"condition_met"` if result is True, else `"condition_not_met"`.
5. For `trigger` → take the single unlabeled outgoing connection.
6. Cap: max 100 step executions per run (abort with error if exceeded).

**TEST:**
```bash
# 1) Ensure the test flow from Task 5 is published.
# 2) Post the trigger event:
curl -s -X POST http://localhost:8010/automation/events \
  -H "Content-Type: application/json" \
  -d '{"event_name":"test.ping","payload":{"x":1},"user_id":"<same_user>","source":"test"}'

# 3) Confirm a run was created:
# SELECT id, status FROM automation.runs ORDER BY started_at DESC LIMIT 1;
# Expect: status='completed'.

# 4) Confirm 3 step_runs exist, all completed:
# SELECT step_key, status, output FROM automation.step_runs
# WHERE run_id = <run_id from above> ORDER BY started_at;
# Expect: t1 completed, c1 completed result=true, a1 completed value=hello.

# 5) Flip the event payload to {"x": 2}:
# Expect: run completed, c1 result=false, a1 NOT executed (only 2 step_runs exist).
```

---

## Phase C — Event→flow pipeline (Task 14)

### Task 14 — Wire events endpoint to matcher + executor
**Effort:** 1.5h
**Goal:** `POST /automation/events` automatically runs all matching flows.

Steps:
1. After inserting the event, call `match_flows(event_name, user_id)`.
2. For each matched flow, call `execute_flow(flow, event)` with `asyncio.create_task` (fire-and-forget for POC — no Celery yet).
3. Response returns immediately: `{"event_id":..., "flows_triggered": N}`.

**TEST:**
```bash
# Single call should trigger the POC flow and complete it:
curl -s -X POST http://localhost:8010/automation/events \
  -H "Content-Type: application/json" \
  -d '{"event_name":"test.ping","payload":{"x":1},"user_id":"<seed_user>","source":"test"}'
# Expect: {"event_id":"...", "flows_triggered": 1}

# Wait 1s, check runs table:
# SELECT status FROM automation.runs WHERE started_at > now() - interval '5 seconds';
# Expect: completed.

# Unknown event fires no run:
curl -s -X POST http://localhost:8010/automation/events \
  -d '{"event_name":"nothing.matches","payload":{},"user_id":"<seed_user>","source":"test"}' \
  -H "Content-Type: application/json"
# Expect: {"flows_triggered": 0}, no new run row.
```

**⭐ At this point the POC exit criteria from roadmap §7 are met. Ship it, demo it, pause before Phase D.**

---

## Phase D — Async primitives (Tasks 15–17, roadmap Phase 1)

### Task 15 — Add Celery + Redis
**Effort:** 2h
**Goal:** Celery worker boots, connects to Redis, can run a hello-world task.

Steps:
1. Add `celery`, `redis` to requirements.
2. `celery_app.py`: broker=`REDIS_URL`, backend=`REDIS_URL`.
3. `tasks.py`: one task `@celery.task def ping(): return "pong"`.
4. Add `REDIS_URL` to `.env.example`.
5. README: how to run worker (`celery -A celery_app worker --loglevel=info`).

**TEST:**
```bash
# Terminal 1: redis-server (or Docker)
# Terminal 2: celery -A celery_app worker --loglevel=info
# Terminal 3:
python -c "from tasks import ping; r = ping.delay(); print(r.get(timeout=5))"
# Expect: pong
```

---

### Task 16 — `delay` handler
**Effort:** 2h
**Goal:** A step that pauses the run for N seconds (via Celery ETA) and resumes automatically.

Steps:
1. `handlers/delay.py`. Config: `{ seconds: int }` (max 30 days in seconds = 2_592_000).
2. Handler does NOT sleep inline. Instead:
   - Set `runs.status = 'waiting'`, persist current step pointer.
   - Schedule Celery task `resume_run.apply_async((run_id,), countdown=seconds)`.
   - Return a sentinel that tells executor to STOP (not continue).
3. `tasks.resume_run(run_id)` reloads the run, sets status back to running, continues executor from next step.

**TEST:**
```bash
# Add a delay step to a test flow (10 seconds).
# Trigger the flow:
curl -X POST .../automation/events -d '...'
# Check immediately: SELECT status FROM runs ORDER BY started_at DESC LIMIT 1;
# Expect: waiting
# Wait 12 seconds, check again:
# Expect: completed
```

---

### Task 17 — `wait_for_event` handler
**Effort:** 3h
**Goal:** A step that pauses until a matching event arrives (or timeout).

Steps:
1. `handlers/wait_for_event.py`. Config: `{ event_name, filter?, timeout_seconds }`.
2. Persist a `pending_waits` record (new table — add migration): `{run_id, step_key, event_name, filter, expires_at}`.
3. Set run status to `waiting` and stop executor.
4. In the events endpoint (Task 4), after matching new flows, also check `pending_waits` for matching records → if match, call `resume_run(run_id)` on the "event_received" branch.
5. Celery Beat periodic task scans `pending_waits` for expired ones → resume on "timeout" branch.

**TEST:**
```bash
# Flow: trigger(test.start) -> wait_for_event(event_name=test.arrive, timeout=60s) -> set_variable(branch=arrived or timed_out)

# Scenario A — event arrives:
curl -X POST .../events -d '{"event_name":"test.start",...}'
# run status should be 'waiting'
sleep 2
curl -X POST .../events -d '{"event_name":"test.arrive",...}'
sleep 1
# run status should be 'completed', final step_run should have branch=arrived

# Scenario B — timeout:
curl -X POST .../events -d '{"event_name":"test.start",...}'
# wait 65 seconds
# run status should be 'completed', final step_run should have branch=timed_out
```

---

## What's next (after Task 17)

- **Tasks 18–47**: one handler per Adam endpoint (roadmap §4.3.1, Phase 2). Each is ~30 lines. Template the first few with Husein, then he can churn them out.
- **Tasks 48+**: webhook_trigger, schedule_trigger, retry/backoff on http_request (Phase 3).
- **Phase 4** connectors (Google Sheets, Meta Lead Ads, etc.) are bigger — plan those with full engineer involvement, not intern-solo.

---

## Ground rules for Husein

1. **Ask questions.** If any step is ambiguous, ask before coding. Wrong guess = wasted hours.
2. **One task, one PR.** No batching. Reviewers should be able to verify each PR in 10 minutes.
3. **Paste TEST output into PR description.** If you skipped the test, the PR will be closed.
4. **No new dependencies without asking.** If you think we need a new library, flag it first.
5. **Never hard-code secrets.** Always read from env.
6. **Don't touch other backends** (`inbound_multy`, `backend_whatsapp`, etc.) in the same PR. `automation_engine/` only.
7. **If a test fails and you can't fix it in 30 min, stop and ask.** Don't keep digging.

# Automation Center — Backend Roadmap, TODO & POC

**Goal:** Build a generic, backend-first automation engine inside Adam. Any user can wire any trigger (internal event OR external app) to any Adam endpoint OR any external HTTP API, without code.

**Stack:** FastAPI + Supabase + Celery/Redis. **Backend only in this doc.**

---

## 1. Architecture

```
                ┌──────────────────────────────────────────────┐
                │           AUTOMATION ENGINE (FastAPI)        │
                │                                              │
  Events ─────▶ │  ┌────────────┐   ┌──────────────────────┐   │
  (internal +   │  │  Event Bus │──▶│  Flow Matcher        │   │
  external +    │  └────────────┘   │  (event → flows)     │   │
  scheduled)    │                    └──────────┬───────────┘   │
                │                               ▼               │
                │                    ┌──────────────────────┐   │
                │                    │  Run Orchestrator    │   │
                │                    │  (creates Run)       │   │
                │                    └──────────┬───────────┘   │
                │                               ▼               │
                │                    ┌──────────────────────┐   │
                │    ┌───────────────│  Step Executor       │──▶│──▶ Adam endpoints
                │    │               │  (async DAG walker)  │   │    External APIs
                │    │               └──────────┬───────────┘   │    Delays → Celery
                │    │                          ▼               │
                │    │               ┌──────────────────────┐   │
                │    └───────────────│  Context & Variables │   │
                │                    │  (event/contact/steps)│  │
                │                    └──────────────────────┘   │
                │                                              │
                └──────────────────────┬───────────────────────┘
                                       ▼
                              ┌────────────────┐
                              │   Supabase     │
                              │  (state/logs)  │
                              └────────────────┘
```

**Layers:**

| Layer | Responsibility |
|---|---|
| **Event Bus** | Single ingestion point: `POST /automation/events`. All triggers funnel here (internal emitters, external webhooks, scheduled crons). |
| **Flow Matcher** | Looks up enabled flows whose `trigger.event_name` matches incoming event. One event → N flow runs. |
| **Run Orchestrator** | Creates a run record, builds initial context, hands off to executor. Async, non-blocking. |
| **Step Executor** | Walks the flow DAG step-by-step. Resolves variables. Calls step handlers. Persists step_run rows. Handles branches (condition_met/not_met, event_received/timeout). |
| **Step Handlers** | Pluggable: one handler per node `type`. Pure function: `(config, context) → output`. Adding a new action = adding one handler. |
| **Context** | Per-run dict: `{ event: {...}, contact: {...}, steps: { <key>: <output> } }`. Passed to every handler. |
| **Scheduler** | Celery Beat for cron triggers + delayed step resumes. Redis as broker. |
| **Worker pool** | Celery workers for anything > a few seconds (delay, wait_for_event, outbound HTTP with retries). |

**Key property:** The engine has **zero knowledge of WhatsApp, calls, or any specific domain.** Every capability is a step handler plugged in via a registry. This is what makes it "build anything."

---

## 2. Data model (Supabase `automation` schema)

```sql
flows              (id, user_id, name, status, definition jsonb,
                    published_version, created_at, updated_at)

flow_versions      (id, flow_id, version, definition jsonb,
                    published_at, published_by)

runs               (id, flow_id, version, status, trigger_event_id,
                    started_at, finished_at, error jsonb)

step_runs          (id, run_id, step_key, type, status,
                    input jsonb, output jsonb, error jsonb,
                    started_at, finished_at, duration_ms)

events             (id, event_name, payload jsonb, user_id, contact_id,
                    source, created_at)

event_schemas      (id, user_id, event_name, schema jsonb)

connections        (id, user_id, provider, label,
                    credentials_encrypted, created_at)

webhook_endpoints  (id, flow_id, token, signing_secret, created_at)

schedules          (id, flow_id, cron_expr, next_run_at, enabled)
```

**Status enum (shared):** `running | completed | failed | cancelled | skipped | waiting`.

**Indexes:** `events(event_name, user_id, created_at desc)`, `runs(flow_id, started_at desc)`, `step_runs(run_id)`.

---

## 3. Flow definition contract (JSON)

Language-agnostic, stored in `flows.definition`:

```json
{
  "name": "<flow name>",
  "steps": [
    { "key": "<unique>", "type": "<node_type>", "config": { ... } }
  ],
  "connections": [
    { "from": "<step key>", "to": "<step key>", "label": "<optional>" }
  ]
}
```

**Rules:**
- First step MUST be `type: "trigger"`.
- `key` is unique within flow, used to reference step output: `steps.<key>.<field>`.
- `config` values can be literals or `{ "var": "event.x" | "contact.x" | "steps.x.y" }`.
- Connection `label` is required for branching nodes (`condition_met`, `condition_not_met`, `event_received`, `timeout`).

---

## 4. Node taxonomy

Three categories. Each is a backend handler function.

### 4.1 Triggers (entry points only)
| Type | Source |
|---|---|
| `trigger` | Internal/external event posted to `POST /automation/events` |
| `webhook_trigger` | Unique public URL per flow — any app POSTs JSON here |
| `schedule_trigger` | Cron expression — fires on schedule |
| `poll_trigger` | Periodic pull from external API (e.g. Google Sheets new row) |

### 4.2 Control flow (engine primitives)
| Type | Purpose |
|---|---|
| `condition` | Branch: `condition_met` / `condition_not_met` |
| `delay` | Pause run for duration (max 30 days, via Celery) |
| `wait_for_event` | Pause until matching event arrives: `event_received` / `timeout` |
| `filter` | Drop run if predicate false |
| `loop` | Iterate over array — one iteration per element |
| `set_variable` | Inject value into context |
| `ai_classify` | LLM call that returns a label/category for branching |
| `code` | Execute sandboxed Python snippet to reshape data (Phase 6) |

### 4.3 Actions (side-effecting — one per endpoint)

#### 4.3.1 Adam internal action nodes — maps 1:1 to existing Adam endpoints

Every Adam endpoint becomes a node. Source of truth for which endpoints exist:

**Inbound** (`inbound-multy.onrender.com`)
- `inbound.update_agent_config`
- `inbound.attach_knowledge_base`
- `inbound.set_routing_rules`

**Outbound** (`outbound-logi.onrender.com`)
- `outbound.trigger_call` — start an outbound AI call
- `outbound.cancel_call`
- `outbound.reschedule_call`
- `outbound.bulk_call_campaign`

**Meta / WhatsApp** (`whatsapp-mfpm.onrender.com`)
- `whatsapp.send_template`
- `whatsapp.send_freeform`
- `whatsapp.send_media`
- `whatsapp.bulk_campaign.start`
- `whatsapp.bulk_campaign.cancel`
- `whatsapp.conversation.assign_agent`
- `whatsapp.template.create`

**Adam Chat / Agent Studio** (`adam-chat.onrender.com`)
- `agent.create`
- `agent.update_prompt`
- `agent.attach_kb`
- `agent.transfer`
- `agent.end_session`


**Analytics** (`analytics-backend-zyl3.onrender.com`)
- `analytics.log_event`
- `analytics.log_conversion`
- `analytics.set_custom_field`

**System**
- `system.send_notification` (in-app to dashboard owner)
- `system.escalate_to_human`

Every one of these is a thin wrapper: validate config → call the existing Adam backend → return response into `steps.<key>.*`. Adding one is ~30 lines of Python.

#### 4.3.2 External action nodes — the "any app" surface

- `http_request` — full method/headers/body/auth/retry, JSONPath extract. **Covers ~any REST API on the planet.**
- `webhook_out` — fire-and-forget POST
- `email.send` — SMTP / Resend / SendGrid
- `sms.send` — Twilio
- `google.sheets.append_row`
- `google.sheets.read_range`
- `google.calendar.create_event`
- `google.calendar.check_availability`
- `slack.send_message`
- `notion.create_page`
- `hubspot.upsert_contact`
- `stripe.create_customer`
- … plus any future connector (each = one handler + one credential type)

**Design rule:** If it's not worth a native connector, `http_request` handles it. Native connectors are pure UX sugar on top of HTTP.

---

## 5. Execution model

**Core loop (pseudocode — the whole engine is ~200 lines):**

```python
async def execute_flow(flow, trigger_event):
    run = await create_run(flow, trigger_event)
    context = {
        "event":   trigger_event.payload,
        "contact": await load_contact(trigger_event.contact_id),
        "steps":   {},
    }

    queue = [start_step(flow)]
    while queue:
        step = queue.pop(0)
        step_run = await create_step_run(run, step)

        try:
            resolved_config = resolve_vars(step.config, context)
            handler = HANDLERS[step.type]
            output = await handler(resolved_config, context, run)
            context["steps"][step.key] = output

            await mark_step_complete(step_run, output)
            queue.extend(next_steps(flow, step, output))

        except StepError as e:
            await mark_step_failed(step_run, e)
            await mark_run_failed(run, e)
            return

    await mark_run_complete(run)
```

**Handler contract:**
```python
async def handler(config: dict, context: dict, run: Run) -> dict:
    """Pure-ish function. Returns output dict → stored in step_runs.output."""
```

**Async primitives:**
- `delay`, `wait_for_event` don't block the loop — they persist `runs.status = "waiting"` and register a Celery scheduled task / event listener. On resume, rehydrate context and continue.
- Everything else runs inline in a worker.

**Variable resolution:** Jinja2 with strict mode. `{{ event.sent_count }}`, `{{ steps.call1.duration_seconds }}`. Unknown var → step fails with clear error.

---

## 6. API surface (backend endpoints)

```
POST   /automation/events                    # ingest any event
POST   /automation/webhook/{flow_token}      # public per-flow webhook
POST   /automation/flows                     # create flow
GET    /automation/flows                     # list user's flows
GET    /automation/flows/{id}                # get flow + latest version
PUT    /automation/flows/{id}                # update draft
POST   /automation/flows/{id}/publish        # publish version
POST   /automation/flows/{id}/stop           # disable future runs
GET    /automation/flows/{id}/runs           # list runs (filters: status)
GET    /automation/runs/{id}                 # run with step_runs
POST   /automation/runs/{id}/retry           # re-execute failed run
POST   /automation/runs/{id}/cancel          # kill in-flight run
GET    /automation/nodes                     # registry of available node types
GET    /automation/events/schemas            # list event schemas for this user
POST   /automation/events/schemas            # define a new event + payload shape
```

All authed via existing Adam JWT. Rate-limited per user.

---

## 7. POC (Week 1) — prove the pipe

**Scope:** a generic engine that runs ANY flow definition. No domain-specific work.

**Exit criteria:**
- [ ] Engine executes a 3-step linear flow (trigger → condition → action) end-to-end
- [ ] Run + step_run rows persist with full I/O for debugging
- [ ] Variable resolution works across event / contact / steps
- [ ] Branching works (condition_met vs condition_not_met routes correctly)
- [ ] One Adam action handler (any endpoint — pick one to validate the pattern) + one `http_request` handler prove both internal + external work
- [ ] `POST /automation/events` accepts events; matching flow runs auto-start

**Explicitly OUT of POC:**
- ❌ No delays > a few seconds (no Celery yet — just asyncio.sleep)
- ❌ No scheduled triggers, no cron
- ❌ No OAuth connector framework (external = raw HTTP with API key in config for now)
- ❌ No retry logic beyond handler-level try/except
- ❌ Flow definitions hand-crafted as JSON and inserted directly into Supabase
- ❌ Nothing about UI — this doc is backend only

**POC tasks:**
1. [ ] Create new service `automation_engine/` (FastAPI app, separate from existing backends, deployable independently)
2. [ ] Supabase migration: all 9 tables in section 2
3. [ ] Node handler registry + 5 handlers: `trigger`, `condition`, `set_variable`, `adam_action`, `http_request`
4. [ ] `POST /automation/events` → matcher → executor
5. [ ] `execute_flow()` runtime + Jinja2 variable resolver
6. [ ] Hand-written test flow JSON covering all 5 handlers
7. [ ] End-to-end integration test: POST event → run completes → assert step outputs + final side-effect

---

## 8. Post-POC phases

### Phase 1 — Async & durability (Week 2)
- [ ] Celery + Redis
- [ ] `delay` handler (persists run, schedules resume task)
- [ ] `wait_for_event` handler (persists run, listens on event bus)
- [ ] Worker restart safety — in-flight runs resume from last step

### Phase 2 — Adam endpoint coverage (Week 3–4)
- [ ] One handler per endpoint in section 4.3.1 (~30 handlers, ~30 lines each)
- [ ] Each handler: config schema + validation + HTTP call to the right Adam backend + typed output
- [ ] Auto-generate node registry from handler docstrings

### Phase 3 — Universal escape hatches (Week 4)
- [ ] `webhook_trigger` — public URL per flow, HMAC-signed
- [ ] `http_request` — full retry/backoff/JSONPath/auth modes
- [ ] `schedule_trigger` — cron via Celery Beat

### Phase 4 — External connector framework (Week 5–7)
- [ ] OAuth abstraction + `connections` table encryption
- [ ] Connectors in priority order:
  1. Google Sheets (triggers + actions)
  2. Google Calendar
  3. Meta Lead Ads (Adam is already a Tech Provider — big advantage)
  4. TikTok Lead Ads
  5. HubSpot
  6. Stripe
  7. Slack
  8. Typeform / Google Forms
  9. Shopify
  10. LinkedIn Lead Gen Forms

### Phase 5 — Power user (Week 8+)
- [ ] `code` handler — sandboxed Python snippet, resource-limited
- [ ] `loop` over arrays
- [ ] `ai_classify` — LLM-based branching
- [ ] Sub-flow invocation (`call_flow` handler)

### Phase 6 — Ops (Week 10+)
- [ ] Per-tenant concurrency limits
- [ ] Per-flow rate limits + daily caps
- [ ] Dead-letter queue for failed runs
- [ ] Run retention policy (auto-archive at 30 days)
- [ ] Audit log on flow edits
- [ ] Secret redaction in step_runs.input/output
- [ ] Metrics: runs/day, success rate, p50/p95/p99 duration per flow + per handler
- [ ] Alerting — notify owner when flow failure rate crosses threshold

---

## 9. Non-negotiable invariants

1. **Engine is domain-agnostic.** It knows nothing about WhatsApp, calls, or any specific feature. Everything is a handler.
2. **Every handler is pluggable.** Adding a capability = adding one file. No engine changes.
3. **Every run is inspectable.** Full input + output + error for every step, forever (until retention kicks in).
4. **Flow definitions are portable.** Pure JSON — exportable, importable, shareable, diff-able.
5. **Cycles are forbidden.** Detect at publish time; reject flows with cycles unless bounded by `loop`.
6. **Secrets never leave the backend.** OAuth tokens encrypted at rest; never returned in API responses; redacted from logs.
7. **Fail closed.** Unknown node type, missing variable, malformed payload → run fails with clear error; never silent-skip.

---

## 10. Known risks

| Risk | Mitigation |
|---|---|
| Long delays crash if process restarts | Celery + Redis from Phase 1; `runs.status = "waiting"` persisted |
| Runaway loops / infinite recursion | Max 1000 step executions per run; cycle detection at publish |
| Secrets leak into logs | Explicit redaction list on `step_runs.output` write |
| External API flakiness | Exponential backoff + dead-letter queue + surfaced in run detail |
| Tenant A's flow blocks tenant B | Per-user Celery queue quotas |
| Engine deploy breaks all flows | Separate deployable; versioned node registry; handler contract is stable |
| Abusive webhook traffic | Signed URLs + per-endpoint rate limits + auto-disable on >N 5xx in window |

---

## 11. References

- Resend Automations — JSON flow schema model
- VoiceHub pathways — node/edge/variable semantics
- n8n docs — UX patterns only (do not copy code; wrong license)
- Celery docs — task scheduling + Beat for cron

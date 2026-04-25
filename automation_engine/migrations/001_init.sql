-- Automation Engine Schema Migration
-- Task 2: Create Supabase schema and tables

-- Note: Using 'public' schema instead of 'automation' for Supabase REST API compatibility

-- Drop existing tables if they exist (in reverse order due to foreign keys)
DROP TABLE IF EXISTS public.schedules;
DROP TABLE IF EXISTS public.webhook_endpoints;
DROP TABLE IF EXISTS public.connections;
DROP TABLE IF EXISTS public.event_schemas;
DROP TABLE IF EXISTS public.events;
DROP TABLE IF EXISTS public.step_runs;
DROP TABLE IF EXISTS public.runs;
DROP TABLE IF EXISTS public.flow_versions;
DROP TABLE IF EXISTS public.flows;

-- Drop existing type if it exists (after dropping tables that use it)
DROP TYPE IF EXISTS public.run_status;

-- Enum for run statuses
CREATE TYPE public.run_status AS ENUM ('running', 'completed', 'failed', 'cancelled', 'skipped', 'waiting');

-- Table: flows
CREATE TABLE public.flows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    definition JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    user_id UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table: flow_versions
CREATE TABLE public.flow_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flow_id UUID NOT NULL REFERENCES public.flows(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    definition JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table: runs
CREATE TABLE public.runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flow_id UUID NOT NULL REFERENCES public.flows(id) ON DELETE CASCADE,
    status public.run_status NOT NULL DEFAULT 'running',
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    error_message TEXT
);

-- Table: step_runs
CREATE TABLE public.step_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES public.runs(id) ON DELETE CASCADE,
    step_key TEXT NOT NULL,
    status public.run_status NOT NULL DEFAULT 'running',
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    output JSONB,
    duration_ms INTEGER
);

-- Table: events
CREATE TABLE public.events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_name TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    user_id UUID NOT NULL,
    contact_id UUID,
    source TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table: event_schemas
CREATE TABLE public.event_schemas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_name TEXT NOT NULL,
    schema JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table: connections
CREATE TABLE public.connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    config JSONB NOT NULL DEFAULT '{}',
    user_id UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table: webhook_endpoints
CREATE TABLE public.webhook_endpoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url TEXT NOT NULL,
    secret TEXT NOT NULL,
    user_id UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table: schedules
CREATE TABLE public.schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flow_id UUID NOT NULL REFERENCES public.flows(id) ON DELETE CASCADE,
    cron_expression TEXT NOT NULL,
    next_run TIMESTAMPTZ,
    user_id UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_events_event_name_user_id_created_at ON public.events(event_name, user_id, created_at DESC);
CREATE INDEX idx_runs_flow_id_started_at ON public.runs(flow_id, started_at DESC);
CREATE INDEX idx_step_runs_run_id ON public.step_runs(run_id);

"""
Step executor module.
Walks the DAG of steps, executes handlers, branches on conditions, and persists runs.
"""

import asyncio
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import UUID
from db import get_supabase
from handlers import HANDLERS
from resolver import StepError


class ExecutionContext:
    """Tracks execution state during flow execution."""

    def __init__(self, flow_id: str, user_id: str, trigger_event: Dict[str, Any]):
        self.flow_id = flow_id
        self.user_id = user_id
        self.trigger_event = trigger_event
        self.run_id: Optional[str] = None
        self.step_outputs: Dict[str, Any] = {}
        self.executed_step_keys: List[str] = []
        self.execution_count = 0
        self.max_executions = 100

    def get_context(self) -> Dict[str, Any]:
        """Get the current execution context for variable resolution."""
        return {
            "event": self.trigger_event,
            "contact": {},
            "steps": self.step_outputs
        }


async def execute_flow(flow: Dict[str, Any], trigger_event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Execute a flow given a trigger event.

    Args:
        flow: Flow definition with steps and connections
        trigger_event: The trigger event payload
        user_id: User ID for the flow

    Returns:
        Dictionary with execution status and run details

    Raises:
        StepError: If execution fails
    """
    supabase = get_supabase()

    try:
        # Extract flow info
        flow_id = flow.get("id")
        flow_definition = flow.get("definition", flow)
        steps = flow_definition.get("steps", [])
        connections = flow_definition.get("connections", [])

        if not flow_id:
            raise StepError("Flow ID is required")

        # Create execution context
        ctx = ExecutionContext(flow_id, user_id, trigger_event)

        # Create run record
        run_data = {
            "flow_id": flow_id,
            "status": "running",
            "started_at": datetime.utcnow().isoformat()
        }
        run_result = supabase.table("runs").insert(run_data).execute()
        ctx.run_id = run_result.data[0]["id"]

        # Build step lookup for quick access
        step_lookup = {step["key"]: step for step in steps}

        # Build connection graph
        connections_graph = {}
        for conn in connections:
            from_key = conn.get("from")
            to_key = conn.get("to")
            label = conn.get("label", "")
            if from_key not in connections_graph:
                connections_graph[from_key] = []
            connections_graph[from_key].append({
                "to": to_key,
                "label": label
            })

        # Start execution from trigger step
        trigger_steps = [s for s in steps if s.get("type") == "trigger"]
        if not trigger_steps:
            raise StepError("No trigger step found in flow")

        current_step_key = trigger_steps[0]["key"]

        # Execute steps in order
        while current_step_key and ctx.execution_count < ctx.max_executions:
            ctx.execution_count += 1

            if current_step_key not in step_lookup:
                raise StepError(f"Step '{current_step_key}' not found in flow definition")

            step = step_lookup[current_step_key]
            step_type = step.get("type")
            step_config = step.get("config", {})

            # Create step_run record
            step_run_data = {
                "run_id": ctx.run_id,
                "step_key": current_step_key,
                "status": "running",
                "started_at": datetime.utcnow().isoformat()
            }
            step_run_result = supabase.table("step_runs").insert(step_run_data).execute()
            step_run_id = step_run_result.data[0]["id"]

            try:
                step_start_time = time.time()

                # Get the handler
                if step_type not in HANDLERS:
                    raise StepError(f"Unknown handler type: {step_type}")

                handler = HANDLERS[step_type]

                # Get execution context (handlers handle their own template resolution)
                context = ctx.get_context()

                # Call handler with raw config (handlers manage their own template resolution)
                output = await handler(step_config, context, None)

                step_duration = int((time.time() - step_start_time) * 1000)

                # Store output
                ctx.step_outputs[current_step_key] = output

                # Update step_run with output
                update_data = {
                    "status": "completed",
                    "output": output,
                    "duration_ms": step_duration,
                    "completed_at": datetime.utcnow().isoformat()
                }
                supabase.table("step_runs").update(update_data).eq("id", step_run_id).execute()

                # Determine next step based on handler output and connections
                next_step_key = None

                if step_type == "trigger":
                    # For trigger steps, take the unlabeled connection
                    if current_step_key in connections_graph:
                        for conn in connections_graph[current_step_key]:
                            if conn.get("label") == "":
                                next_step_key = conn["to"]
                                break

                elif step_type == "condition":
                    # For condition steps, branch based on result
                    result = output.get("result", False)
                    label = "condition_met" if result else "condition_not_met"

                    if current_step_key in connections_graph:
                        for conn in connections_graph[current_step_key]:
                            if conn.get("label") == label:
                                next_step_key = conn["to"]
                                break

                else:
                    # For other steps, take the first connection (usually single path)
                    if current_step_key in connections_graph:
                        for conn in connections_graph[current_step_key]:
                            if conn.get("label") == "":
                                next_step_key = conn["to"]
                                break

                current_step_key = next_step_key

            except StepError as e:
                # Update step_run with error
                error_data = {
                    "status": "failed",
                    "completed_at": datetime.utcnow().isoformat(),
                    "duration_ms": int((time.time() - step_start_time) * 1000)
                }
                supabase.table("step_runs").update(error_data).eq("id", step_run_id).execute()

                # Mark run as failed
                run_update = {
                    "status": "failed",
                    "error_message": str(e),
                    "completed_at": datetime.utcnow().isoformat()
                }
                supabase.table("runs").update(run_update).eq("id", ctx.run_id).execute()

                return {
                    "status": "error",
                    "run_id": ctx.run_id,
                    "error": str(e)
                }

            except Exception as e:
                # Unexpected error
                error_data = {
                    "status": "failed",
                    "completed_at": datetime.utcnow().isoformat(),
                    "duration_ms": int((time.time() - step_start_time) * 1000)
                }
                supabase.table("step_runs").update(error_data).eq("id", step_run_id).execute()

                run_update = {
                    "status": "failed",
                    "error_message": f"Unexpected error: {str(e)}",
                    "completed_at": datetime.utcnow().isoformat()
                }
                supabase.table("runs").update(run_update).eq("id", ctx.run_id).execute()

                return {
                    "status": "error",
                    "run_id": ctx.run_id,
                    "error": str(e)
                }

        # Check if we exceeded max executions
        if ctx.execution_count >= ctx.max_executions and current_step_key:
            run_update = {
                "status": "failed",
                "error_message": f"Execution exceeded maximum {ctx.max_executions} steps",
                "completed_at": datetime.utcnow().isoformat()
            }
            supabase.table("runs").update(run_update).eq("id", ctx.run_id).execute()

            return {
                "status": "error",
                "run_id": ctx.run_id,
                "error": f"Execution exceeded maximum {ctx.max_executions} steps"
            }

        # Mark run as completed
        run_update = {
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat()
        }
        supabase.table("runs").update(run_update).eq("id", ctx.run_id).execute()

        return {
            "status": "ok",
            "run_id": ctx.run_id,
            "execution_count": ctx.execution_count,
            "step_outputs": ctx.step_outputs
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


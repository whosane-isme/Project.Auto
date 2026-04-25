"""
Adam action handler module.
Routes actions to external Adam endpoints (whatsapp, SMS, etc.).
"""

import httpx
from typing import Dict, Any
from handlers import handler
from resolver import StepError
import os

# Registry of available Adam endpoints
ADAM_ENDPOINTS = {
    "whatsapp.send_freeform": {
        "base": "https://whatsapp-mfpm.onrender.com",
        "path": "/send-message",
        "method": "POST"
    }
}


@handler("adam_action")
async def adam_action_handler(config: Dict[str, Any], context: Dict[str, Any], run: Any) -> Dict[str, Any]:
    """
    Adam action handler - routes to external service endpoints.

    Args:
        config: Handler configuration containing action and params
                action: dotted name like "whatsapp.send_freeform"
                params: dict of parameters to send to the endpoint
        context: Execution context containing event, contact, and steps
        run: Run instance (can be None)

    Returns:
        Dictionary with status and body

    Raises:
        StepError: If action not found, network error, or other failures
    """
    action = config.get("action")
    params = config.get("params", {})

    if not action:
        raise StepError("action is required in adam_action config")

    if action not in ADAM_ENDPOINTS:
        raise StepError(f"Unknown adam_action: {action}")

    endpoint = ADAM_ENDPOINTS[action]
    url = endpoint["base"] + endpoint["path"]
    method = endpoint["method"]

    # Get service auth header from environment
    service_key = os.getenv("ADAM_SERVICE_KEY")
    if not service_key:
        raise StepError("ADAM_SERVICE_KEY environment variable not set")

    headers = {
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.request(
                method,
                url,
                headers=headers,
                json=params
            )

            status = response.status_code

            try:
                body = response.json()
            except:
                body = response.text

            return {
                "status": status,
                "body": body
            }

    except httpx.RequestError as e:
        raise StepError(f"Adam action request failed: {str(e)}")
    except Exception as e:
        raise StepError(f"Unexpected error during adam_action: {str(e)}")

"""
HTTP request handler module.
Makes HTTP calls and returns response details.
"""

import httpx
from typing import Dict, Any
from handlers import handler
from resolver import StepError


@handler("http_request")
async def http_request_handler(config: Dict[str, Any], context: Dict[str, Any], run: Any) -> Dict[str, Any]:
    """
    HTTP request handler - makes HTTP calls to external services.

    Args:
        config: Handler configuration containing method, url, headers, body, timeout_seconds
        context: Execution context containing event, contact, and steps
        run: Run instance (can be None)

    Returns:
        Dictionary with status, headers, and body

    Raises:
        StepError: On network errors
    """
    method = config["method"].upper()
    url = config["url"]
    headers = config.get("headers", {})
    body = config.get("body")
    timeout_seconds = min(config.get("timeout_seconds", 10), 60)

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            if method in ["GET", "HEAD"]:
                response = await client.request(method, url, headers=headers)
            else:
                response = await client.request(method, url, headers=headers, content=body)

            status = response.status_code
            headers_dict = dict(response.headers)

            try:
                body_content = response.json()
            except:
                body_content = response.text

            return {
                "status": status,
                "headers": headers_dict,
                "body": body_content
            }
    except httpx.RequestError as e:
        raise StepError(f"HTTP request failed: {str(e)}")
    except Exception as e:
        raise StepError(f"Unexpected error during HTTP request: {str(e)}")

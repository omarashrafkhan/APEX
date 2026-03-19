from langchain_core.tools import tool
import json
from typing import Any, Dict



@tool
def http_sqli_probe(
    url: str,
    method: str,
    body: Dict[str, Any],
    param: str = "",
    payload: str = "",
    content_type: str = "form",
) -> str:
    """
    Fire HTTP request(s) with an SQLi payload injected into a parameter.
    Returns full response content and metadata for analysis.

    Args:
        url: Target endpoint.
        method: HTTP method (GET/POST).
        body: Base parameter dictionary.
        param: Optional parameter name to inject.
        payload: Optional payload value to inject into `param`.
        content_type: For POST, one of "form" (default), "json", or "both".
    """
    import requests

    injected_body = dict(body or {})
    if param:
        injected_body[param] = payload

    method_upper = method.upper()
    content_type_lower = content_type.lower()

    def _send_request(post_mode: str = "form") -> Dict[str, Any]:
        headers = {}
        if method_upper == "POST":
            headers["Content-Type"] = (
                "application/json" if post_mode == "json" else "application/x-www-form-urlencoded"
            )

        if method_upper == "POST":
            if post_mode == "json":
                resp = requests.post(url, json=injected_body, headers=headers, timeout=30)
            else:
                resp = requests.post(url, data=injected_body, headers=headers, timeout=30)
        else:
            resp = requests.get(url, params=injected_body, timeout=30)

        return {
            "url": url,
            "method": method_upper,
            "param": param,
            "payload": payload,
            "status": resp.status_code,
            "length": len(resp.text),
            "request_body": injected_body,
            "request_content_type": headers.get("Content-Type"),
            "response_headers": dict(resp.headers),
            "response_text": resp.text,
        }

    try:
        if method_upper == "POST" and content_type_lower == "both":
            form_result = _send_request(post_mode="form")
            json_result = _send_request(post_mode="json")
            return json.dumps(
                {
                    "mode": "both",
                    "results": {
                        "form": form_result,
                        "json": json_result,
                    },
                }
            )

        post_mode = "json" if (method_upper == "POST" and content_type_lower == "json") else "form"
        return json.dumps(_send_request(post_mode=post_mode))
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def baseline_request(
    url: str,
    method: str,
    body: Dict[str, Any],
    content_type: str = "form",
) -> str:
    """
    Fire a clean baseline request to record normal response for delta comparison.
    For POST requests, defaults to form encoding (works with PHP $_POST).
    Set content_type to "both" to test form and json in one call.
    Because some servers handle form and json differently, this can help identify which one to target for SQLi.
    """
    import requests

    method_upper = method.upper()
    content_type_lower = content_type.lower()

    def _send_request(post_mode: str = "form") -> Dict[str, Any]:
        headers = {}
        if method_upper == "POST":
            headers["Content-Type"] = (
                "application/json" if post_mode == "json" else "application/x-www-form-urlencoded"
            )

        if method_upper == "POST":
            if post_mode == "json":
                resp = requests.post(url, json=body, headers=headers, timeout=30)
            else:
                resp = requests.post(url, data=body, headers=headers, timeout=30)
        else:
            resp = requests.get(url, params=body, timeout=30)

        return {
            "url": url,
            "method": method_upper,
            "status": resp.status_code,
            "length": len(resp.text),
            "request_body": body,
            "request_content_type": headers.get("Content-Type"),
            "response_headers": dict(resp.headers),
            "response_text": resp.text,
        }

    try:
        if method_upper == "POST" and content_type_lower == "both":
            form_result = _send_request(post_mode="form")
            json_result = _send_request(post_mode="json")
            return json.dumps(
                {
                    "mode": "both",
                    "results": {
                        "form": form_result,
                        "json": json_result,
                    },
                }
            )

        post_mode = "json" if (method_upper == "POST" and content_type_lower == "json") else "form"
        return json.dumps(_send_request(post_mode=post_mode))
    except Exception as e:
        return json.dumps({"error": str(e)})

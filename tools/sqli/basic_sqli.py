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
    Fire a single HTTP request with an SQLi payload injected into a parameter.
    Returns full response content and metadata for analysis.

    Args:
        url: Target endpoint.
        method: HTTP method (GET/POST).
        body: Base parameter dictionary.
        param: Optional parameter name to inject.
        payload: Optional payload value to inject into `param`.
        content_type: For POST, either "form" (default) or "json".
    """
    import requests

    injected_body = dict(body or {})
    if param:
        injected_body[param] = payload

    method_upper = method.upper()
    is_json_post = method_upper == "POST" and content_type.lower() == "json"

    headers = {}
    if method_upper == "POST":
        headers["Content-Type"] = "application/json" if is_json_post else "application/x-www-form-urlencoded"

    try:
        if method_upper == "POST":
            if is_json_post:
                resp = requests.post(url, json=injected_body, headers=headers, timeout=8)
            else:
                resp = requests.post(url, data=injected_body, headers=headers, timeout=8)
        else:
            resp = requests.get(url, params=injected_body, timeout=8)

        return json.dumps({
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
        })
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
    """
    import requests

    method_upper = method.upper()
    is_json_post = method_upper == "POST" and content_type.lower() == "json"

    headers = {}
    if method_upper == "POST":
        headers["Content-Type"] = "application/json" if is_json_post else "application/x-www-form-urlencoded"

    try:
        if method_upper == "POST":
            if is_json_post:
                resp = requests.post(url, json=body, headers=headers, timeout=8)
            else:
                resp = requests.post(url, data=body, headers=headers, timeout=8)
        else:
            resp = requests.get(url, params=body, timeout=8)
        return json.dumps({
            "url": url,
            "method": method_upper,
            "status": resp.status_code,
            "length": len(resp.text),
            "request_body": body,
            "request_content_type": headers.get("Content-Type"),
            "response_headers": dict(resp.headers),
            "response_text": resp.text,
        })
    except Exception as e:
        return json.dumps({"error": str(e)})

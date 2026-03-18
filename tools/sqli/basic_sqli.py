from langchain_core.tools import tool
import json
from typing import Any, Dict



@tool
def http_sqli_probe(url: str, method: str, body: Dict[str, Any], param: str, payload: str) -> str:
    """
    Fire a single HTTP request with an SQLi payload injected into a parameter.
    Returns status code, response length, and a content snippet for analysis.
    """
    import requests

    injected_body = {**body, param: payload}

    try:
        if method.upper() == "POST":
            resp = requests.post(url, json=injected_body, timeout=8)
        else:
            resp = requests.get(url, params=injected_body, timeout=8)

        return json.dumps({
            "url": url,
            "param": param,
            "payload": payload,
            "status": resp.status_code,
            "length": len(resp.text),
            "snippet": resp.text[:300],
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def baseline_request(url: str, method: str, body: Dict[str, Any]) -> str:
    """
    Fire a clean baseline request to record normal response for delta comparison.
    """
    import requests
    try:
        if method.upper() == "POST":
            resp = requests.post(url, json=body, timeout=8)
        else:
            resp = requests.get(url, params=body, timeout=8)
        return json.dumps({
            "status": resp.status_code,
            "length": len(resp.text),
            "snippet": resp.text[:300],
        })
    except Exception as e:
        return json.dumps({"error": str(e)})

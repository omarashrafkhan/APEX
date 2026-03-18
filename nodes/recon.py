from __future__ import annotations

from typing import Any, Dict
from urllib.parse import urlparse
from pathlib import Path
import sys

try:
    from state import APEXState
    from tools.common.curl import curl_ip_tool
    from tools.sqli.omar_crawler import run_omar_crawler
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from state import APEXState
    from tools.common.curl import curl_ip_tool
    from tools.sqli.omar_crawler import run_omar_crawler


def _normalize_target(target: str) -> Dict[str, Any]:
    target_to_parse = target if "://" in target else f"http://{target}"
    parsed = urlparse(target_to_parse)
    host = parsed.hostname or target
    scheme = parsed.scheme or "http"
    path = parsed.path or "/"
    port = parsed.port
    return {"host": host, "scheme": scheme, "path": path, "port": port}


def recon_node(state: APEXState) -> Dict[str, Any]:
    """Recon node that runs curl and crawler tools against target."""
    target = state.target
    normalized = _normalize_target(target)
    use_https = normalized["scheme"].lower() == "https"
    default_port = normalized["port"] or (443 if use_https else 80)
    path = normalized["path"] if normalized["path"].startswith("/") else f"/{normalized['path']}"
    crawler_url = f"{normalized['scheme']}://{normalized['host']}:{default_port}{path}"

    try:
        curl_result = curl_ip_tool.invoke({
            "ip_address": normalized["host"],
            "port": default_port,
            "use_https": use_https,
        })
    except Exception as e:
        curl_result = {"error": str(e)}

    try:
        crawler_result = run_omar_crawler.invoke({"target_url": crawler_url})
    except Exception as e:
        crawler_result = {"error": str(e), "target_url": crawler_url}

    status_code = None
    if isinstance(curl_result, dict):
        status_code = curl_result.get("status")

    recon_data = {
        "target": target,
        "host": normalized["host"],
        "scheme": normalized["scheme"],
        "base_path": normalized["path"],
        "status_code": status_code,
        "discovered_params": [],
        "suspected_db": "unknown",
        "auth_required": False,
        "notes": [],
        "curl_result": curl_result,
        "crawler_result": crawler_result,
    }

    recon_summary = (
        f"Recon complete for {target}. "
        f"curl status: {status_code or 'unknown'}. "
        f"crawler target: {crawler_url}."
    )

    print("[recon] Completed curl-based recon")
    return {
        "status": "recon-complete",
        "recon_results": recon_data,
        "recon_summary": recon_summary,
    }


if __name__ == "__main__":
    dummy_state = APEXState(
        initial_prompt="Test recon node",
        target="http://127.0.0.1:8000",
        target_ip="127.0.0.1",
        exploit_enabled=False,
        status="running",
    )

    node_output = recon_node(dummy_state)
    next_state = dummy_state.model_copy(update=node_output)

    print("\n=== recon_node output ===")
    print(node_output)
    print("\n=== next state ===")
    print(next_state.model_dump())

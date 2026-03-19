from __future__ import annotations

import logging
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

from ui import ui

logger = logging.getLogger(__name__)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _normalize_target(target: str) -> Dict[str, Any]:
    target = (target or "").strip()
    if "://" in target:
        target_to_parse = target
    elif target.startswith(("http:", "https:")):
        scheme, rest = target.split(":", 1)
        target_to_parse = f"{scheme}://{rest.lstrip('/')}"
    else:
        target_to_parse = f"http://{target}"

    parsed = urlparse(target_to_parse)
    host   = parsed.hostname or target
    scheme = parsed.scheme or "http"
    path   = parsed.path or "/"
    try:
        port = parsed.port
    except ValueError:
        port = None

    return {"host": host, "scheme": scheme, "path": path, "port": port}


# ─── Node ────────────────────────────────────────────────────────────────────

def recon_node(state: APEXState) -> Dict[str, Any]:
    """Recon node — runs curl + crawler against the target and summarises results."""

    ui.agent_start("ReconAgent", goal=f"Enumerate target: {state.target}")

    target     = state.target
    normalized = _normalize_target(target)
    use_https  = normalized["scheme"].lower() == "https"
    default_port = normalized["port"] or (443 if use_https else 80)
    path       = normalized["path"] if normalized["path"].startswith("/") else f"/{normalized['path']}"
    crawler_url = f"{normalized['scheme']}://{normalized['host']}:{default_port}{path}"

    ui.kv_table({
        "Host":    normalized["host"],
        "Scheme":  normalized["scheme"],
        "Port":    default_port,
        "Path":    path,
    }, title="Normalised target")

    # ── curl ─────────────────────────────────────────────────────────────────
    ui.tool_call("curl", {
        "ip_address": normalized["host"],
        "port":       default_port,
        "use_https":  use_https,
    })

    try:
        curl_result = curl_ip_tool.invoke({
            "ip_address": normalized["host"],
            "port":       default_port,
            "use_https":  use_https,
        })
        curl_display = str(curl_result) if not isinstance(curl_result, str) else curl_result
        ui.tool_result("curl", curl_display)
    except Exception as e:
        curl_result = {"error": str(e)}
        ui.error(f"curl failed: {e}")

    # ── crawler ───────────────────────────────────────────────────────────────
    ui.tool_call("omar_crawler", {"target_url": crawler_url})

    try:
        crawler_result = run_omar_crawler.invoke({"target_url": crawler_url})
        crawler_display = str(crawler_result) if not isinstance(crawler_result, str) else crawler_result
        ui.tool_result("omar_crawler", crawler_display)
    except Exception as e:
        crawler_result = {"error": str(e), "target_url": crawler_url}
        ui.error(f"crawler failed: {e}")

    # ── Summarise ─────────────────────────────────────────────────────────────
    status_code = curl_result.get("status") if isinstance(curl_result, dict) else None

    recon_data = {
        "target":            target,
        "host":              normalized["host"],
        "scheme":            normalized["scheme"],
        "base_path":         normalized["path"],
        "status_code":       status_code,
        "discovered_params": [],
        "suspected_db":      "unknown",
        "auth_required":     False,
        "notes":             [],
        "curl_result":       curl_result,
        "crawler_result":    crawler_result,
    }

    recon_summary = (
        f"Recon complete for {target}. "
        f"curl status: {status_code or 'unknown'}. "
        f"crawler target: {crawler_url}."
    )

    ui.agent_done("ReconAgent", summary=f"curl status={status_code or 'unknown'}")

    return {
        "status":        "recon-complete",
        "recon_results": recon_data,
        "recon_summary": recon_summary,
    }


# ─── Manual test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    dummy_state = APEXState(
        initial_prompt="Test recon node",
        target="http://127.0.0.1:8000",
        exploit_enabled=False,
        status="running",
    )
    node_output = recon_node(dummy_state)
    next_state  = dummy_state.model_copy(update=node_output)

    ui.section("recon_node raw output")
    ui.panel(str(node_output), title="node_output", style="dim")
    ui.panel(str(next_state.model_dump()), title="next_state", style="dim")
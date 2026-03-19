from __future__ import annotations

import sys
import json
import logging
from typing import Any, Callable, Dict, Optional

from cli import parse_args, validate_inputs, initialize_state, run_interactive_cli
from graph import app
from state import APEXState
from ui import ui

# Keep file-level logger for internal diagnostics — ui.py owns all user-facing output
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ─── Core graph runner ───────────────────────────────────────────────────────

def stream_and_interrupt_handler(
    initial_state: APEXState,
    progress_callback: Optional[Callable[[str, Dict[str, Any], Dict[str, Any]], None]] = None,
) -> APEXState:
    config = {"configurable": {"thread_id": initial_state.target}}
    logger.info("Starting engagement for target %s", initial_state.target)

    try:
        merged_state: Dict[str, Any] = initial_state.model_dump()

        for chunk in app.stream(initial_state, config=config, stream_mode="updates"):
            if not isinstance(chunk, dict):
                continue
            for node_name, update in chunk.items():
                if not isinstance(update, dict):
                    continue
                merged_state.update(update)
                if progress_callback:
                    progress_callback(node_name, update, merged_state)

        final_state = APEXState(**merged_state)
        final_state.status = "completed"
        return final_state

    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        initial_state.status = "paused"
        raise
    except Exception as e:
        logger.error("Graph execution failed: %s", e, exc_info=True)
        initial_state.status = "failed"
        raise


# ─── Non-interactive (flag-based) run ────────────────────────────────────────

def run_normal(args) -> int:
    """Flag-based CLI flow — used when -t / -p are passed."""
    try:
        validate_inputs(args)
        initial_state = initialize_state(args)

        ui.section("Engagement Started")
        ui.kv_table({
            "Target": initial_state.target,
            "Prompt": initial_state.initial_prompt,
        })

        with ui.live_status(f"Running graph for {initial_state.target}…") as update:
            def _progress(node_name: str, _update: dict, merged: dict) -> None:
                status = merged.get("status", "running")
                update(f"node={node_name}  status={status}")

            final_state = stream_and_interrupt_handler(
                initial_state, progress_callback=_progress
            )

        sqli_agent_spec     = getattr(final_state, "sqli_agent_spec",     {}) or {}
        sqli_attempt_result = getattr(final_state, "sqli_attempt_result", {}) or {}
        tools_used = ", ".join(sqli_agent_spec.get("selected_tools", [])) or "none"

        ui.engagement_summary(
            status=final_state.status,
            data={
                "Target":        final_state.target,
                "Recon summary": final_state.recon_summary or "—",
                "SQLi tools":    tools_used,
            },
        )

        report_text = (
            sqli_attempt_result.get("report")
            or sqli_attempt_result.get("orchestrator_report")
            or ""
        )
        if report_text:
            ui.report(report_text, title="Orchestrator Report")

        return 0

    except ValueError as e:
        ui.error(f"Invalid input: {e}")
        return 1
    except KeyboardInterrupt:
        ui.warn("Aborted by user.")
        return 130
    except Exception as e:
        ui.error(f"Unhandled exception: {e}")
        logger.exception("Unhandled exception in run_normal")
        return 1


# ─── Entry point ─────────────────────────────────────────────────────────────

def main() -> int:
    # No flags → interactive Rich CLI (banner + prompts handled inside run_interactive_cli)
    if len(sys.argv) == 1:
        run_interactive_cli(stream_and_interrupt_handler)
        return 0

    # Flags passed → non-interactive run
    args = parse_args()
    return run_normal(args)


if __name__ == "__main__":
    sys.exit(main())
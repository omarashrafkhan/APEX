from __future__ import annotations

import argparse

from prompt_toolkit import prompt
from prompt_toolkit.styles import Style

from state import APEXState
from ui import ui

prompt_style = Style.from_dict({
    "":       "#ff5308",
    "prompt": "bold #ff5308",
})


# ─── Argument parser ─────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Penetration testing agent runner")
    parser.add_argument("-t", "--target", required=True,
        help="Target URL/IP/identifier")
    parser.add_argument("-p", "--prompt",
        default="Perform SQL injection reconnaissance and planning",
        help="High-level objective for the agent run")
    return parser.parse_args()


def validate_inputs(args: argparse.Namespace) -> None:
    if not isinstance(args.target, str) or not args.target.strip():
        raise ValueError("Target must be a non-empty URL/IP/identifier string")


def initialize_state(args: argparse.Namespace) -> APEXState:
    return APEXState(
        initial_prompt=args.prompt,
        target=args.target,
        exploit_enabled=False,
        status="running",
        orchestrator_plan={},
        recon_results={},
        recon_summary="",
        sqli_agent_spec={},
        sqli_attempt_result={},
    )


# ─── Interactive CLI ──────────────────────────────────────────────────────────

def _get_user_inputs() -> tuple[str, str]:
    """Prompt user for target and objective using prompt_toolkit."""
    ui.section("Target Setup")

    target      = prompt("  🎯 Target IP/URL  : ", style=prompt_style).strip()
    user_prompt = prompt("  📝 Objective      : ", style=prompt_style).strip()

    return target, user_prompt


def run_interactive_cli(runner_fn) -> None:
    """
    Full interactive Rich CLI entry point.
    runner_fn: stream_and_interrupt_handler from main.py
    """
    try:
        ui.banner()
        target, user_prompt = _get_user_inputs()

        if not target:
            ui.error("Target cannot be empty.")
            return

        ui.kv_table({
            "Target":    target,
            "Objective": user_prompt or "(default)",
        })

        args = argparse.Namespace(
            target=target,
            prompt=user_prompt or "Perform SQL injection reconnaissance and planning",
        )
        validate_inputs(args)
        initial_state = initialize_state(args)

        ui.section("Engagement Running")

        with ui.live_status(f"Initialising — target={target}") as update:
            def _on_progress(node_name: str, node_update: dict, merged_state: dict) -> None:
                status    = merged_state.get("status") or "running"
                n_outputs = len(merged_state.get("subagent_outputs") or {})
                update(
                    f"node={node_name}  status={status}  sub-agent iterations={n_outputs}"
                )

            final_state = runner_fn(initial_state, progress_callback=_on_progress)

        # ── Results ───────────────────────────────────────────────────────────
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

        if final_state.subagent_outputs:
            latest_key    = sorted(final_state.subagent_outputs.keys())[-1]
            latest_output = final_state.subagent_outputs.get(latest_key, {})
            latest_text   = (
                latest_output.get("output", "")
                if isinstance(latest_output, dict)
                else str(latest_output)
            )
            ui.nested_panel(
                content=latest_text,
                outer_title="Latest Sub-Agent Output",
                inner_title=latest_key,
                outer_style="accent",
                inner_style="dim",
            )

    except KeyboardInterrupt:
        ui.warn("Aborted by user.")
    except ValueError as e:
        ui.error(f"Invalid input: {e}")
    except Exception as e:
        ui.error(f"Unexpected error: {e}")
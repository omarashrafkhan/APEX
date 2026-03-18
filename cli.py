from __future__ import annotations

import argparse
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from prompt_toolkit import prompt
from prompt_toolkit.styles import Style

from state import APEXState

console = Console()

prompt_style = Style.from_dict({
    "": "#00ffff",
    "prompt": "bold cyan",
})


# ─── Argument Parser (unchanged) ────────────────────────────────────────────

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


# ─── Interactive Rich CLI ────────────────────────────────────────────────────

def show_banner():
    console.clear()
    console.print()
    console.print(Panel(
        "[bold cyan]"
        "  █████╗  ██████╗ ███████╗██╗  ██╗\n"
        " ██╔══██╗ ██╔══██╗██╔════╝╚██╗██╔╝\n"
        " ███████║ ██████╔╝█████╗   ╚███╔╝ \n"
        " ██╔══██║ ██╔═══╝ ██╔══╝   ██╔██╗ \n"
        " ██║  ██║ ██║     ███████╗██╔╝ ██╗\n"
        " ╚═╝  ╚═╝ ╚═╝     ╚══════╝╚═╝  ╚═╝[/bold cyan]\n\n"
        "[dim]  Multi-Agent Penetration Testing System[/dim]\n"
        "[dim]  ──────────────────────────────────────[/dim]\n"
        "[dim]  Press Ctrl+C at any time to abort[/dim]",
        border_style="cyan",
        padding=(1, 4),
    ))
    console.print()


def get_user_inputs() -> tuple[str, str]:
    """Prompt user for target and prompt interactively."""
    console.print("[bold cyan]  Target Setup[/bold cyan]", style="dim")
    console.print()

    target = prompt("  🎯 Target IP/URL  : ", style=prompt_style).strip()
    user_prompt = prompt("  📝 Prompt         : ", style=prompt_style).strip()

    return target, user_prompt


def show_agent_result(agent_name: str, status: str, output: str = ""):
    if status == "done":
        console.print(f"  [green]✔[/green] [bold cyan]{agent_name}[/bold cyan]")
        if output:
            console.print(f"    [dim]{output}[/dim]")
    elif status == "error":
        console.print(f"  [red]✘[/red] [bold red]{agent_name}[/bold red] — failed")


def run_interactive_cli(runner_fn):
    """
    Interactive rich CLI entry point.
    runner_fn: the stream_and_interrupt_handler from main.py
    """
    try:
        show_banner()
        target, user_prompt = get_user_inputs()

        console.print()
        console.print(Panel(
            f"[dim]Target:[/dim]  [white]{target}[/white]\n"
            f"[dim]Prompt:[/dim]  [white]{user_prompt}[/white]",
            title="[cyan]Starting Engagement[/cyan]",
            border_style="dim",
            padding=(0, 2),
        ))
        console.print()

        # Build state and run
        import argparse
        args = argparse.Namespace(target=target, prompt=user_prompt)
        validate_inputs(args)
        initial_state = initialize_state(args)

        # Show spinner while graph runs and update status from streamed node updates
        status_text = Text("  ⠋  Running agents...", style="cyan")

        with Live(status_text, refresh_per_second=10) as live:
            def _on_progress(node_name: str, update: dict, merged_state: dict) -> None:
                status = merged_state.get("status") or "running"
                outputs = merged_state.get("subagent_outputs") or {}
                iter_count = len(outputs)
                live.update(Text(
                    f"  ⠋  Running agents... node={node_name} status={status} iterations={iter_count}",
                    style="cyan",
                ))

            final_state = runner_fn(initial_state, progress_callback=_on_progress)

        # Print results
        sqli_agent_spec = getattr(final_state, "sqli_agent_spec", {}) or {}
        sqli_attempt_result = getattr(final_state, "sqli_attempt_result", {}) or {}

        console.print()
        console.print(Panel(
            f"[dim]Status:[/dim]       [green]{final_state.status}[/green]\n"
            f"[dim]Recon summary:[/dim] {final_state.recon_summary or '[dim]none[/dim]'}\n"
            f"[dim]SQLi tools:[/dim]   "
            + (", ".join(sqli_agent_spec.get("selected_tools", [])) or "[dim]none[/dim]"),
            title="[green]✔ Engagement Complete[/green]",
            border_style="green",
            padding=(0, 2),
        ))

        report_text = (
            sqli_attempt_result.get("report")
            or sqli_attempt_result.get("orchestrator_report")
            or ""
        )
        if report_text:
            console.print()
            console.print(Panel(
                report_text,
                title="[cyan]Orchestrator Report[/cyan]",
                border_style="cyan",
                padding=(0, 2),
            ))

        if final_state.subagent_outputs:
            latest_key = sorted(final_state.subagent_outputs.keys())[-1]
            latest_output = final_state.subagent_outputs.get(latest_key, {})
            latest_text = latest_output.get("output", "") if isinstance(latest_output, dict) else str(latest_output)
            preview = latest_text[:1600] + ("..." if len(latest_text) > 1600 else "")
            console.print()
            console.print(Panel(
                preview or "No sub-agent output text was captured.",
                title=f"[cyan]Latest Sub-Agent Output ({latest_key})[/cyan]",
                border_style="cyan",
                padding=(0, 2),
            ))

    except KeyboardInterrupt:
        console.print("\n\n  [yellow]Aborted by user.[/yellow]")
    except ValueError as e:
        console.print(f"\n  [red]Invalid input:[/red] {e}")
    except Exception as e:
        console.print(f"\n  [red]Error:[/red] {e}")
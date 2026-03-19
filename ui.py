"""
ui.py  —  Singleton Rich CLI renderer for APEX multi-agent system.

Primary accent colour : #ff5308  (orange)
Secondary             : #00bfff  (ice blue, for contrast)
Muted                 : dim white / grey

Usage anywhere in the codebase:

    from ui import ui

    ui.banner()
    ui.agent_start("ReconAgent")
    ui.tool_call("nmap", {"target": "10.0.0.1", "ports": "1-1024"})
    ui.tool_result("nmap", "PORT   STATE SERVICE\n22/tcp open  ssh")
    ui.agent_done("ReconAgent", summary="Found 3 open ports")
    ui.agent_switch("ReconAgent", "SQLiAgent")
    ui.print("Some info message from anywhere")
    ui.warn("Something looks off")
    ui.error("Hard failure")
    ui.section("Phase 2: Exploitation")
    ui.kv("Target", "10.0.0.1")
    ui.panel("Any renderable or string", title="Custom Panel", style="accent")
    ui.nested_panel(outer_title="Agent", inner_title="Tool Output", content="...")
    ui.rule("separator label")
    ui.spinner_start("Thinking...")   # returns a context-manager
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Any, Optional

from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from rich.table import Table
from rich.padding import Padding
from rich.syntax import Syntax
from rich.live import Live
from rich.spinner import Spinner
from rich import box

# ── Palette ──────────────────────────────────────────────────────────────────

ACCENT   = "#ff5308"   # primary orange
ICE      = "#00bfff"   # secondary / cold contrast
GREEN    = "#39d353"
RED      = "#ff4444"
YELLOW   = "#f5c518"
MUTED    = "grey50"
DIM      = "dim"

# Box style used for all panels
BOX = box.ROUNDED


# ── Singleton Console ─────────────────────────────────────────────────────────

class _UI:
    """
    Central UI singleton.  Thread-safe print via Rich Console.
    All public methods return `self` so they can be chained if desired.
    """

    _instance: Optional["_UI"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "_UI":
        with cls._lock:
            if cls._instance is None:
                inst = super().__new__(cls)
                inst._console = Console()
                inst._active_agent: str = ""
                cls._instance = inst
        return cls._instance  # type: ignore[return-value]

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _c(self) -> Console:
        return self._console

    def _accent(self, text: str) -> str:
        return f"[{ACCENT}]{text}[/{ACCENT}]"

    def _ice(self, text: str) -> str:
        return f"[{ICE}]{text}[/{ICE}]"

    def _rule_label(self, label: str, color: str = ACCENT) -> str:
        return f"[bold {color}]{label}[/bold {color}]"

    # ── Banner ────────────────────────────────────────────────────────────────

    def banner(self) -> "_UI":
        """Print the APEX ASCII banner."""
        self._c().print()
        self._c().print(Panel(
            f"[bold {ACCENT}]"
            "  █████╗  ██████╗ ███████╗██╗  ██╗\n"
            " ██╔══██╗ ██╔══██╗██╔════╝╚██╗██╔╝\n"
            " ███████║ ██████╔╝█████╗   ╚███╔╝ \n"
            " ██╔══██║ ██╔═══╝ ██╔══╝   ██╔██╗ \n"
            " ██║  ██║ ██║     ███████╗██╔╝ ██╗\n"
            f" ╚═╝  ╚═╝ ╚═╝     ╚══════╝╚═╝  ╚═╝[/bold {ACCENT}]\n\n"
            f"[{MUTED}]  Multi-Agent Penetration Testing System[/{MUTED}]\n"
            f"[{MUTED}]  ──────────────────────────────────────[/{MUTED}]\n"
            f"[{MUTED}]  Press Ctrl+C at any time to abort[/{MUTED}]",
            border_style=ACCENT,
            box=BOX,
            padding=(1, 4),
        ))
        self._c().print()
        return self

    # ── Section / Rule ────────────────────────────────────────────────────────

    def section(self, label: str) -> "_UI":
        """Bold full-width section divider."""
        self._c().print()
        self._c().print(Rule(self._rule_label(label), style=ACCENT))
        self._c().print()
        return self

    def rule(self, label: str = "", color: str = MUTED) -> "_UI":
        """Thin separator rule, optional label."""
        self._c().print(Rule(
            f"[{color}]{label}[/{color}]" if label else "",
            style=color,
        ))
        return self

    # ── Generic print / warn / error ──────────────────────────────────────────

    def print(self, *args: Any, **kwargs: Any) -> "_UI":
        """Drop-in replacement for print() — supports Rich markup."""
        self._c().print(*args, **kwargs)
        return self

    def log(self, message: str, prefix: str = "•") -> "_UI":
        """Inline log line with muted prefix — good for miscellaneous prints."""
        self._c().print(f"  [{MUTED}]{prefix}[/{MUTED}] {message}")
        return self

    def info(self, message: str) -> "_UI":
        self._c().print(f"  [{ICE}]ℹ[/{ICE}]  {message}")
        return self

    def warn(self, message: str) -> "_UI":
        self._c().print(f"  [{YELLOW}]⚠[/{YELLOW}]  [{YELLOW}]{message}[/{YELLOW}]")
        return self

    def error(self, message: str) -> "_UI":
        self._c().print(f"  [{RED}]✘[/{RED}]  [{RED}]{message}[/{RED}]")
        return self

    def success(self, message: str) -> "_UI":
        self._c().print(f"  [{GREEN}]✔[/{GREEN}]  [{GREEN}]{message}[/{GREEN}]")
        return self

    # ── Key-value pairs ───────────────────────────────────────────────────────

    def kv(self, key: str, value: Any, indent: int = 2) -> "_UI":
        """Single key = value line."""
        pad = " " * indent
        self._c().print(f"{pad}[{MUTED}]{key}:[/{MUTED}]  [{ACCENT}]{value}[/{ACCENT}]")
        return self

    def kv_table(self, data: dict[str, Any], title: str = "") -> "_UI":
        """Render a dict as a two-column table."""
        t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        t.add_column(style=MUTED, no_wrap=True)
        t.add_column(style=f"bold {ACCENT}")
        for k, v in data.items():
            t.add_row(f"{k}:", str(v))
        if title:
            self._c().print(f"  [{MUTED}]{title}[/{MUTED}]")
        self._c().print(Padding(t, (0, 2)))
        return self

    # ── Custom panel (flexible) ───────────────────────────────────────────────

    def panel(
        self,
        content: Any,
        title: str = "",
        subtitle: str = "",
        style: str = "accent",    # "accent" | "ice" | "green" | "red" | "dim"
        padding: tuple = (0, 2),
        expand: bool = True,
    ) -> "_UI":
        """
        Generic panel. style shortcuts:
          "accent"  →  orange border  (default)
          "ice"     →  blue border
          "green"   →  green border
          "red"     →  red border
          "dim"     →  muted grey border
        """
        color_map = {
            "accent": ACCENT,
            "ice":    ICE,
            "green":  GREEN,
            "red":    RED,
            "dim":    MUTED,
        }
        border = color_map.get(style, style)   # also accepts raw colour strings

        title_str  = f"[bold {border}]{title}[/bold {border}]" if title else ""
        sub_str    = f"[{MUTED}]{subtitle}[/{MUTED}]"          if subtitle else ""

        self._c().print(Panel(
            content,
            title=title_str,
            subtitle=sub_str,
            border_style=border,
            box=BOX,
            padding=padding,
            expand=expand,
        ))
        return self

    def nested_panel(
        self,
        content: Any,
        outer_title: str = "",
        inner_title: str = "",
        outer_style: str = "accent",
        inner_style: str = "dim",
        padding: tuple = (0, 2),
    ) -> "_UI":
        """
        Panel-inside-a-panel.  Great for agent output that contains tool output.
        """
        color_map = {
            "accent": ACCENT,
            "ice":    ICE,
            "green":  GREEN,
            "red":    RED,
            "dim":    MUTED,
        }
        inner_border  = color_map.get(inner_style, inner_style)
        outer_border  = color_map.get(outer_style, outer_style)
        outer_title_s = f"[bold {outer_border}]{outer_title}[/bold {outer_border}]" if outer_title else ""
        inner_title_s = f"[{inner_border}]{inner_title}[/{inner_border}]"           if inner_title else ""

        inner = Panel(content, title=inner_title_s, border_style=inner_border, box=BOX, padding=(0, 1))
        outer = Panel(inner,   title=outer_title_s, border_style=outer_border, box=BOX, padding=padding)
        self._c().print(outer)
        return self

    # ── Agent lifecycle ───────────────────────────────────────────────────────

    def agent_start(self, agent_name: str, goal: str = "") -> "_UI":
        """
        Called when an agent begins execution.
        Prints a bold orange header for the agent.
        """
        self._active_agent = agent_name
        self._c().print()
        self._c().print(Rule(
            f"[bold {ACCENT}]▶  {agent_name}[/bold {ACCENT}]"
            + (f"  [{MUTED}]— {goal}[/{MUTED}]" if goal else ""),
            style=ACCENT,
        ))
        return self

    def agent_done(self, agent_name: str = "", summary: str = "") -> "_UI":
        """Called when an agent finishes successfully."""
        name = agent_name or self._active_agent
        line = f"[{GREEN}]✔[/{GREEN}]  [bold {GREEN}]{name} complete[/bold {GREEN}]"
        if summary:
            line += f"  [{MUTED}]— {summary}[/{MUTED}]"
        self._c().print(f"  {line}")
        self._c().print()
        return self

    def agent_error(self, agent_name: str = "", reason: str = "") -> "_UI":
        """Called when an agent fails."""
        name = agent_name or self._active_agent
        line = f"[{RED}]✘[/{RED}]  [bold {RED}]{name} failed[/bold {RED}]"
        if reason:
            line += f"  [{MUTED}]— {reason}[/{MUTED}]"
        self._c().print(f"  {line}")
        self._c().print()
        return self

    def agent_switch(self, from_agent: str, to_agent: str, reason: str = "") -> "_UI":
        """Visualise a handoff between two agents."""
        self._c().print()
        reason_str = f"  [{MUTED}]{reason}[/{MUTED}]" if reason else ""
        self._c().print(
            f"  [{MUTED}]{from_agent}[/{MUTED}]"
            f"  [{ACCENT}]→[/{ACCENT}]"
            f"  [bold {ACCENT}]{to_agent}[/bold {ACCENT}]"
            f"{reason_str}"
        )
        self._active_agent = to_agent
        self._c().print()
        return self

    def agent_thinking(self, agent_name: str = "", message: str = "Thinking…") -> "_UI":
        """Inline thinking indicator (no spinner — safe outside Live context)."""
        name = agent_name or self._active_agent
        self._c().print(f"  [{MUTED}]{'⠿' * 3}  {name}: {message}[/{MUTED}]")
        return self

    # ── Tool call / result ────────────────────────────────────────────────────

    def tool_call(
        self,
        tool_name: str,
        args: dict[str, Any] | str | None = None,
        agent_name: str = "",
    ) -> "_UI":
        """
        Show a tool invocation box.
        args can be a dict or a raw string snippet.
        """
        agent = agent_name or self._active_agent
        header = (
            f"[{MUTED}]{agent} →[/{MUTED}] " if agent else ""
        ) + f"[bold {ACCENT}]{tool_name}[/bold {ACCENT}]"

        if isinstance(args, dict):
            rows = "\n".join(
                f"  [{MUTED}]{k}[/{MUTED}]  [{ICE}]{v}[/{ICE}]"
                for k, v in args.items()
            )
            body = rows or f"[{MUTED}](no args)[/{MUTED}]"
        elif args:
            body = f"[{ICE}]{args}[/{ICE}]"
        else:
            body = f"[{MUTED}](no args)[/{MUTED}]"

        self._c().print(Panel(
            body,
            title=f"[bold]⚙  {header}[/bold]",
            border_style=ICE,
            box=BOX,
            padding=(0, 2),
        ))
        return self

    def tool_result(
        self,
        tool_name: str,
        output: str,
        language: str = "",
        truncate: int = 2000,
        agent_name: str = "",
    ) -> "_UI":
        """
        Show a tool result box.
        Pass language= for syntax highlighting (e.g. "json", "xml", "bash").
        """
        agent = agent_name or self._active_agent
        title = (
            f"[{MUTED}]{agent} ←[/{MUTED}] " if agent else ""
        ) + f"[bold {GREEN}]{tool_name}[/bold {GREEN}]"

        display = output
        was_truncated = False
        if len(output) > truncate:
            display = output[:truncate]
            was_truncated = True

        if language:
            body: Any = Syntax(display, language, theme="monokai", word_wrap=True)
        else:
            body = display

        subtitle = f"[{MUTED}]… truncated[/{MUTED}]" if was_truncated else ""

        self._c().print(Panel(
            body,
            title=f"[bold]◀  {title}[/bold]",
            subtitle=subtitle,
            border_style=GREEN,
            box=BOX,
            padding=(0, 2),
        ))
        return self

    # ── LLM I/O ──────────────────────────────────────────────────────────────

    def llm_prompt(self, text: str, agent_name: str = "", truncate: int = 1000) -> "_UI":
        """Display the prompt being sent to the LLM."""
        agent = agent_name or self._active_agent
        display = text[:truncate] + ("…" if len(text) > truncate else "")
        self._c().print(Panel(
            f"[{MUTED}]{display}[/{MUTED}]",
            title=f"[{MUTED}]↑ Prompt  {agent}[/{MUTED}]",
            border_style=MUTED,
            box=BOX,
            padding=(0, 2),
        ))
        return self

    def llm_response(
        self,
        text: str,
        agent_name: str = "",
        truncate: int = 2000,
    ) -> "_UI":
        """Display the LLM's response."""
        agent = agent_name or self._active_agent
        display = text[:truncate] + ("…" if len(text) > truncate else "")
        self._c().print(Panel(
            display,
            title=f"[bold {ACCENT}]↓ Response  {agent}[/bold {ACCENT}]",
            border_style=ACCENT,
            box=BOX,
            padding=(0, 2),
        ))
        return self

    # ── Final report ──────────────────────────────────────────────────────────

    def report(self, content: str, title: str = "Final Report") -> "_UI":
        """Highlighted final report panel."""
        self._c().print()
        self._c().print(Panel(
            content,
            title=f"[bold {GREEN}]📄  {title}[/bold {GREEN}]",
            border_style=GREEN,
            box=BOX,
            padding=(1, 2),
        ))
        return self

    def engagement_summary(
        self,
        status: str,
        data: dict[str, Any],
    ) -> "_UI":
        """Compact summary panel shown at end of a run."""
        color = GREEN if status.lower() in {"done", "complete", "success"} else YELLOW
        rows = "\n".join(
            f"[{MUTED}]{k}:[/{MUTED}]  [{color}]{v}[/{color}]"
            for k, v in data.items()
        )
        self._c().print()
        self._c().print(Panel(
            rows,
            title=f"[bold {color}]✔ Engagement Complete — {status}[/bold {color}]",
            border_style=color,
            box=BOX,
            padding=(0, 2),
        ))
        return self

    # ── Spinner (context manager) ─────────────────────────────────────────────

    @contextmanager
    def spinner(self, message: str = "Running…", spinner_name: str = "dots"):
        """
        Context-manager spinner.  Prints are suppressed inside Live;
        use ui.log() after the block for output.

        Usage:
            with ui.spinner("Scanning ports…"):
                result = run_nmap(target)
        """
        with self._c().status(
            f"[{ACCENT}]{message}[/{ACCENT}]",
            spinner=spinner_name,
            spinner_style=f"bold {ACCENT}",
        ):
            yield

    # ── Live updatable status line ────────────────────────────────────────────

    @contextmanager
    def live_status(self, initial: str = "Running…"):
        """
        Yields a callable update(message) you can call inside the block
        to rewrite a single status line.

        Usage:
            with ui.live_status("Starting…") as update:
                for step in steps:
                    update(f"Processing {step}…")
                    do_work(step)
        """
        text = Text(f"  ⠋  {initial}", style=f"bold {ACCENT}")
        with Live(text, console=self._c(), refresh_per_second=12) as live:
            def _update(msg: str) -> None:
                live.update(Text(f"  ⠋  {msg}", style=f"bold {ACCENT}"))
            yield _update


# ── Module-level singleton ────────────────────────────────────────────────────

ui = _UI()
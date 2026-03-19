"""
demo_ui.py  —  Visual demo of every ui.py function.

Run with:
    python demo_ui.py
"""

import time
from ui import ui

# ─────────────────────────────────────────────────────────────
# 1. Banner
# ─────────────────────────────────────────────────────────────
ui.banner()

# ─────────────────────────────────────────────────────────────
# 2. Sections & rules
# ─────────────────────────────────────────────────────────────
ui.section("Phase 1: Reconnaissance")
ui.rule("sub-section", color="grey50")

# ─────────────────────────────────────────────────────────────
# 3. Generic prints
# ─────────────────────────────────────────────────────────────
ui.print("This is a [bold]plain print[/bold] with Rich markup — replaces all bare print() calls")
ui.log("This is a muted log line — good for verbose internal state")
ui.info("Something informational happened")
ui.warn("Unexpected response code — continuing anyway")
ui.error("Connection refused on port 443")
ui.success("Credential verified successfully")

# ─────────────────────────────────────────────────────────────
# 4. Key-value helpers
# ─────────────────────────────────────────────────────────────
ui.rule()
ui.kv("Target",   "192.168.1.100")
ui.kv("Protocol", "HTTPS")
ui.kv("Timeout",  "30s")

ui.rule()
ui.kv_table({
    "Target":    "192.168.1.100",
    "Port":      "443",
    "Technique": "Time-based blind SQLi",
    "DBMS":      "MySQL 8.0",
}, title="Engagement config")

# ─────────────────────────────────────────────────────────────
# 5. Agent lifecycle
# ─────────────────────────────────────────────────────────────
ui.section("Phase 2: Agent Execution")

ui.agent_start("OrchestratorAgent", goal="Plan and delegate recon tasks")
ui.agent_thinking("OrchestratorAgent", "Selecting sub-agents…")

ui.agent_switch("OrchestratorAgent", "ReconAgent", reason="starting port scan")

ui.agent_start("ReconAgent", goal="Enumerate open ports and services")

# ─────────────────────────────────────────────────────────────
# 6. Tool call / result
# ─────────────────────────────────────────────────────────────
ui.tool_call("nmap", {
    "target": "192.168.1.100",
    "ports":  "1-1024",
    "flags":  "-sV -T4",
})

time.sleep(0.3)   # simulate tool running

ui.tool_result("nmap", """\
PORT    STATE  SERVICE  VERSION
22/tcp  open   ssh      OpenSSH 8.9
80/tcp  open   http     nginx 1.22
443/tcp open   ssl/http nginx 1.22
3306/tcp open  mysql    MySQL 8.0.32
""")

ui.agent_done("ReconAgent", summary="4 open ports found, MySQL exposed")

# ─────────────────────────────────────────────────────────────
# 7. Agent switch → SQLi agent
# ─────────────────────────────────────────────────────────────
ui.agent_switch("ReconAgent", "SQLiAgent", reason="MySQL detected, pivoting to injection")

ui.agent_start("SQLiAgent", goal="Test login endpoint for SQL injection")

ui.tool_call("sqlmap", {
    "url":     "https://192.168.1.100/login",
    "param":   "username",
    "level":   "3",
    "risk":    "2",
    "dbms":    "mysql",
})

ui.tool_result("sqlmap", """\
[INFO] testing connection to the target URL
[INFO] heuristic (basic) test shows that GET parameter 'username' might be injectable
[INFO] testing for SQL injection on GET parameter 'username'
[CRITICAL] GET parameter 'username' is vulnerable. Do you want to keep testing the others (if any)? [y/N]
[INFO] the back-end DBMS is MySQL
web application technology: Nginx, PHP 8.1
back-end DBMS: MySQL >= 8.0
""", truncate=2000)

ui.agent_done("SQLiAgent", summary="Vulnerability confirmed — time-based blind SQLi")

# ─────────────────────────────────────────────────────────────
# 8. LLM I/O panels
# ─────────────────────────────────────────────────────────────
ui.section("LLM Communication")

ui.llm_prompt(
    "You are a penetration testing agent. Given the following nmap results, "
    "identify the highest-priority target and suggest next steps:\n\n"
    "PORT 3306/tcp open mysql MySQL 8.0.32\n"
    "PORT 22/tcp  open ssh   OpenSSH 8.9",
    agent_name="SQLiAgent",
)

ui.llm_response(
    "Based on the scan results, port 3306 (MySQL) is the highest-priority target. "
    "MySQL 8.0.32 has known vulnerabilities. I recommend:\n"
    "1. Test for unauthenticated access\n"
    "2. Attempt default credential login\n"
    "3. Check for SQL injection on the web login form at port 80/443",
    agent_name="SQLiAgent",
)

# ─────────────────────────────────────────────────────────────
# 9. Generic panels (flexible)
# ─────────────────────────────────────────────────────────────
ui.section("Custom Panels")

ui.panel(
    "This is an [bold]accent-style[/bold] panel — use for general important output.",
    title="Accent Panel",
    style="accent",
)

ui.panel(
    "This is an [italic]ice-blue[/italic] panel — use for informational blocks.",
    title="Info Panel",
    style="ice",
)

ui.panel(
    "This is a [bold red]red panel[/bold red] — use for warnings or errors.",
    title="Warning Panel",
    style="red",
)

# ─────────────────────────────────────────────────────────────
# 10. Nested panel (agent wrapping tool output)
# ─────────────────────────────────────────────────────────────
ui.nested_panel(
    content="PORT 3306/tcp open mysql MySQL 8.0.32\nPORT 22/tcp open ssh OpenSSH 8.9",
    outer_title="SQLiAgent",
    inner_title="nmap output",
    outer_style="accent",
    inner_style="dim",
)

# ─────────────────────────────────────────────────────────────
# 11. Spinner (context manager)
# ─────────────────────────────────────────────────────────────
ui.section("Spinner & Live Status")

with ui.spinner("Running sqlmap — this may take a moment…"):
    time.sleep(1.5)   # simulate slow tool

ui.success("sqlmap completed")

# ─────────────────────────────────────────────────────────────
# 12. Live status updater
# ─────────────────────────────────────────────────────────────
steps = ["Connecting", "Enumerating databases", "Dumping users table", "Done"]
with ui.live_status("Starting…") as update:
    for step in steps:
        update(step)
        time.sleep(0.7)

ui.success("Live status complete")

# ─────────────────────────────────────────────────────────────
# 13. Final report & summary
# ─────────────────────────────────────────────────────────────
ui.section("Results")

ui.report("""\
Target       : 192.168.1.100
Vulnerability: Time-based blind SQL injection (login endpoint)
Parameter    : username
DBMS         : MySQL 8.0.32
Severity     : Critical

Recommended remediation:
  • Use parameterised queries / prepared statements
  • Restrict MySQL to localhost (remove port 3306 from public interfaces)
  • Rotate all database credentials immediately
""", title="Penetration Test Report")

ui.engagement_summary("complete", {
    "Target":          "192.168.1.100",
    "Agents run":      "3  (Orchestrator → Recon → SQLi)",
    "Tools invoked":   "nmap, sqlmap",
    "Critical findings": "1",
    "Duration":        "~4 minutes",
})
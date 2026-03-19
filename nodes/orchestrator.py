"""
APEX Orchestrator Node
======================
Reads recon results + initial prompt, determines pentest category,
builds a specialised sub-agent via create_agent, runs it, and saves output.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage

from config.llm_config import getGeminiLLM

from state import APEXState
from tools.sqli.basic_sqli import http_sqli_probe, baseline_request
from tools.sqli.sqlmap_runner import run_sqlmap
from ui import ui

logger = logging.getLogger(__name__)


# ─── Orchestrator system prompt ───────────────────────────────────────────────

ORCHESTRATOR_SYSTEM_PROMPT = """
You are APEX Orchestrator — the master intelligence of an autonomous penetration-testing framework.

Your responsibilities:
1. Analyse the target, initial prompt, recon results, and recon summary.
2. Identify which penetration-testing category best fits the objective.
3. Direct specialised sub-agents toward achieving the goal (e.g., capturing a flag).
4. Evaluate sub-agent outputs after each iteration and decide whether to continue or conclude.

Supported pentest categories (you MUST pick exactly one):
  - sqli          (SQL Injection)

Tone: precise, methodical, adversarial — think like a senior red-team operator.
""".strip()


# ─── Tool registry ────────────────────────────────────────────────────────────

TOOL_REGISTRY: Dict[str, List[Any]] = {
    "sqli": [http_sqli_probe, baseline_request, run_sqlmap],
}


# ─── Helper 1 — determine pentest category ───────────────────────────────────

def _determine_pentest_category(
    initial_prompt: str,
    recon_summary: str,
    recon_results: Dict[str, Any],
) -> str:
    llm = getGeminiLLM()

    prompt_text = f"""
You are a senior penetration tester. Based on the information below, choose the
single most appropriate pentest category from this list:
{list(TOOL_REGISTRY.keys())}

Respond with ONLY the category string and nothing else.

--- Initial Prompt ---
{initial_prompt}

--- Recon Summary ---
{recon_summary}

--- Recon Results (JSON) ---
{json.dumps(recon_results, indent=2)}
""".strip()

    ui.llm_prompt(prompt_text, agent_name="OrchestratorAgent")
    response = llm.invoke([HumanMessage(content=prompt_text)])
    category = response.content.strip().lower()
    ui.llm_response(response.content, agent_name="OrchestratorAgent")

    if category not in TOOL_REGISTRY:
        ui.warn(f"LLM returned unknown category '{category}', falling back to sqli")
        category = "sqli"

    ui.kv("Pentest category", category)
    return category


# ─── Helper 2 — create specialised sub-agent prompt ──────────────────────────

def _create_specialized_prompt(
    category: str,
    context: Dict[str, Any],
) -> str:
    llm = getGeminiLLM()

    prompt_text = f"""
You are writing a system prompt for a specialised penetration-testing sub-agent.

Category : {category}
Context  : {json.dumps(context, indent=2)}

Write a concise, expert-level system prompt (≤ 200 words) that:
- States the agent's specialisation clearly ({category})
- Includes the target URL / host from the context
- Describes the exact goal (capture the flag / find vulnerability)
- Lists any known constraints or hints from recon
- Instructs the agent to be methodical and report findings verbatim

Return ONLY the system prompt text, no preamble.

IN CASE OF SQLI, I WANT YOU TO WRITE THIS THAT
WHEN YOU TRY BASIC PAYLOAD LIKE ' OR 1=1 , and you get server try, dont worry and
try different uppercase and lowercase combination or , Or, oR etc. YOU MUST TRY ALL POSSIBLE COMBINATION OF CASES. 
SOME SERVERS ARE CASE SENSITIVE AND THIS CAN HELP BYPASSING WAF.

Alwasy start from the simplest payloads and then move to more complex ones. Dont forget to use the 
baseline request tool to understand the normal response before injecting payloads.
SQL Map takes a lot of time to run, so use it only when you have strong evidence of SQLi and have exhausted majority of
the simpler techniques.
""".strip()

    ui.llm_prompt(prompt_text, agent_name="OrchestratorAgent")
    response = llm.invoke([HumanMessage(content=prompt_text)])
    specialized_prompt = response.content.strip()
    ui.llm_response(specialized_prompt, agent_name="OrchestratorAgent")

    return specialized_prompt


# ─── Helper 3 — select tools ─────────────────────────────────────────────────

def _select_tools_for_subagent(
    category: str,
    specialized_prompt: str,
) -> List[Any]:
    available_tools = TOOL_REGISTRY.get(category, [])

    if not available_tools:
        ui.warn(f"No tools registered for category '{category}'.")
        return []

    tool_names = [getattr(t, "name", str(t)) for t in available_tools]
    ui.kv("Tools selected", ", ".join(tool_names))
    return available_tools


# ─── Helper 4 — build sub-agent ──────────────────────────────────────────────

def _build_subagent(
    specialized_prompt: str,
    tools: List[Any],
    category: str,
) -> Any:
    agent = create_agent(
        model=getGeminiLLM(),
        tools=tools,
        system_prompt=specialized_prompt,
        name=f"{category}_specialist",
    )
    ui.info(f"Sub-agent built: {category}_specialist")
    return agent


# ─── Helper 5 — run sub-agent with streaming ─────────────────────────────────

def _run_subagent_with_streaming(subagent: Any, user_message: str) -> Dict[str, Any]:
    input_payload = {"messages": [{"role": "user", "content": user_message}]}

    final_messages: List[Any] = []
    tool_calls: List[Any]     = []
    response_buffer: List[str] = []

    def _render_chunk(event: Any) -> None:
        nonlocal final_messages, tool_calls, response_buffer

        if not isinstance(event, dict):
            return

        event_type = event.get("type")
        data       = event.get("data")

        if event_type == "messages" and isinstance(data, (list, tuple)) and data:
            token = data[0]
            if isinstance(token, AIMessageChunk):
                if token.text:
                    response_buffer.append(token.text)
                if token.tool_call_chunks:
                    for tc in token.tool_call_chunks:
                        if tc.get("name"):
                            ui.tool_call(tc["name"], agent_name=subagent.name)

        elif event_type == "updates" and isinstance(data, dict):
            for step_name, step_update in data.items():
                messages = (
                    step_update.get("messages", [])
                    if isinstance(step_update, dict)
                    else []
                )
                if messages:
                    final_messages = messages
                    msg = messages[-1]

                    if isinstance(msg, AIMessage) and msg.tool_calls:
                        tool_calls.extend(msg.tool_calls)
                        for call in msg.tool_calls:
                            call_name = (
                                call.get("name", "unknown_tool")
                                if isinstance(call, dict)
                                else str(call)
                            )
                            call_args = (
                                call.get("args", {})
                                if isinstance(call, dict)
                                else {}
                            )
                            ui.tool_call(call_name, call_args, agent_name=subagent.name)

                    if isinstance(msg, ToolMessage):
                        ui.tool_result(
                            step_name,
                            str(msg.content),
                            agent_name=subagent.name,
                        )

    # ── Stream ────────────────────────────────────────────────────────────────
    try:
        for event in subagent.stream(
            input_payload,
            stream_mode=["messages", "updates"],
            version="v2",
        ):
            _render_chunk(event)
    except TypeError:
        for event in subagent.stream(
            input_payload,
            stream_mode=["messages", "updates"],
        ):
            _render_chunk(event)
    except Exception:
        ui.warn("Streaming unavailable — falling back to invoke().")
        result = subagent.invoke(input_payload)
        final_messages = result.get("messages", [])

    # Flush buffered streaming tokens as a single LLM-response panel
    if response_buffer:
        ui.llm_response("".join(response_buffer), agent_name=subagent.name)

    return {
        "messages":   final_messages,
        "tool_calls": tool_calls,
    }


# ─── Main orchestrator node ───────────────────────────────────────────────────

def orchestrator_node(state: APEXState) -> Dict[str, Any]:
    """
    LangGraph node — orchestrates specialised sub-agents to achieve the pentest goal.

    Reads  : state.initial_prompt, state.target, state.recon_results, state.recon_summary
    Writes : state.subagent_outputs, state.status
    """

    ui.agent_start("OrchestratorAgent", goal=state.initial_prompt)
    ui.kv("Target", state.target)

    # 1. Determine category
    ui.agent_thinking("OrchestratorAgent", "Determining pentest category…")
    category = _determine_pentest_category(
        initial_prompt=state.initial_prompt,
        recon_summary=state.recon_summary,
        recon_results=state.recon_results,
    )

    # 2. Build context
    context: Dict[str, Any] = {
        "target":         state.target,
        "initial_prompt": state.initial_prompt,
        "recon_summary":  state.recon_summary,
        "recon_results":  state.recon_results,
        "category":       category,
    }

    # 3. Generate specialised system prompt
    ui.agent_thinking("OrchestratorAgent", "Generating specialised system prompt…")
    specialized_prompt = _create_specialized_prompt(category=category, context=context)

    # 4. Select tools
    tools = _select_tools_for_subagent(
        category=category,
        specialized_prompt=specialized_prompt,
    )

    # 5. Build sub-agent
    subagent = _build_subagent(
        specialized_prompt=specialized_prompt,
        tools=tools,
        category=category,
    )

    # 6. Iteration loop
    MAX_ITERATIONS = 3
    subagent_outputs: Dict[str, Any] = dict(state.subagent_outputs)
    flag_captured = False

    for iteration in range(1, MAX_ITERATIONS + 1):
        ui.agent_switch(
            "OrchestratorAgent",
            f"{category}_specialist",
            reason=f"iteration {iteration}/{MAX_ITERATIONS}",
        )
        ui.agent_start(
            f"{category}_specialist",
            goal=f"Iteration {iteration}/{MAX_ITERATIONS} — {state.initial_prompt}",
        )

        prior_output_summary = (
            json.dumps(subagent_outputs, indent=2) if subagent_outputs else "None yet."
        )

        user_message = (
            f"Target: {state.target}\n\n"
            f"Goal: {state.initial_prompt}\n\n"
            f"Recon Summary:\n{state.recon_summary}\n\n"
            f"Previous sub-agent outputs:\n{prior_output_summary}\n\n"
            "Execute your specialised attack. Report findings, any flags captured, "
            "and what you tried in detail."
        )

        result = _run_subagent_with_streaming(subagent=subagent, user_message=user_message)

        # Extract final message text
        final_messages = result.get("messages", [])
        if not final_messages:
            output_text = "No response messages returned by sub-agent."
        else:
            final_message = final_messages[-1]
            raw_content   = (
                final_message.content
                if hasattr(final_message, "content")
                else final_message
            )
            output_text = _coerce_to_text(raw_content)

        output_key = f"{category}_iter_{iteration}"
        subagent_outputs[output_key] = {
            "iteration":  iteration,
            "category":   category,
            "output":     output_text,
            "tool_calls": result.get("tool_calls", []),
        }

        ui.agent_done(
            f"{category}_specialist",
            summary=f"Iteration {iteration} stored as '{output_key}'",
        )

        # 7. Check flag
        if _check_flag_captured(output_text):
            ui.success(f"🚩  Flag captured on iteration {iteration}!")
            flag_captured = True
            break
        else:
            ui.info(f"No flag detected in iteration {iteration} output.")

    # Hand back to orchestrator
    ui.agent_switch(f"{category}_specialist", "OrchestratorAgent", reason="loop complete")

    new_status = "flag_captured" if flag_captured else "subagent_exhausted"
    ui.agent_done("OrchestratorAgent", summary=f"status={new_status}")

    return {
        "subagent_outputs": subagent_outputs,
        "status":           new_status,
    }


# ─── Utilities ───────────────────────────────────────────────────────────────

def _coerce_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, list):
        parts: List[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                parts.append(text if isinstance(text, str) and text else json.dumps(item, ensure_ascii=False))
            else:
                parts.append(str(item))
        return "\n".join(p for p in parts if p)
    if isinstance(value, dict):
        text = value.get("text") if "text" in value else None
        return text if isinstance(text, str) else json.dumps(value, ensure_ascii=False)
    return str(value)


def _check_flag_captured(output: Any) -> bool:
    flag_patterns = [
        r"FLAG\{[^}]+\}",
        r"HTB\{[^}]+\}",
        r"picoCTF\{[^}]+\}",
        r"CTF\{[^}]+\}",
        r"flag\{[^}]+\}",
    ]
    output_text = _coerce_to_text(output)
    return any(re.search(p, output_text, re.IGNORECASE) for p in flag_patterns)
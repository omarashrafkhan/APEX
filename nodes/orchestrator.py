"""
APEX Orchestrator Node
======================
Reads recon results + initial prompt, determines pentest category,
builds a specialised sub-agent via create_agent, runs it, and saves output.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage

from config.llm_config import getGeminiLLM  # your existing helper

from state import APEXState
from tools.sqli.basic_sqli import http_sqli_probe, baseline_request  # example tools
from tools.sqli.sqlmap_runner import run_sqlmap  # example tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Orchestrator system prompt
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Hardcoded tool registry  (populate these lists with your real tools)
# ---------------------------------------------------------------------------

TOOL_REGISTRY: Dict[str, List[Any]] = {
    "sqli":        [http_sqli_probe, baseline_request, run_sqlmap],   # e.g. [run_sqlmap, manual_sqli_probe]
}

# ---------------------------------------------------------------------------
# Helper 1 — derive pentest category via LLM
# ---------------------------------------------------------------------------

def _determine_pentest_category(
    initial_prompt: str,
    recon_summary: str,
    recon_results: Dict[str, Any],
) -> str:
    """
    Uses the orchestrator LLM to pick one category from TOOL_REGISTRY keys.
    Returns a lowercase string like 'sqli'.
    """
    llm = getGeminiLLM()

    prompt = f"""
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

    response = llm.invoke([HumanMessage(content=prompt)])
    category = response.content.strip().lower()

    if category not in TOOL_REGISTRY:
        logger.warning("LLM returned unknown category '%s', falling back to sqli", category)
        category = "sqli"

    logger.info("[Orchestrator] Pentest category determined: %s", category)
    return category


# ---------------------------------------------------------------------------
# Helper 2 — create specialised sub-agent system prompt via LLM
# ---------------------------------------------------------------------------

# TODO: Based on categry merge expert hardcoded prompt 

def _create_specialized_prompt(
    category: str,
    context: Dict[str, Any],
) -> str:
    """
    Given the pentest category and relevant context, asks the LLM to write a
    targeted system prompt for the sub-agent.
    """
    llm = getGeminiLLM()

    prompt = f"""
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
try different uppercase and lwoercase combination or , Or, oR etc. 

""".strip()

    response = llm.invoke([HumanMessage(content=prompt)])
    specialized_prompt = response.content.strip()
    logger.info("[Orchestrator] Specialised prompt created for category: %s", category)
    return specialized_prompt


# ---------------------------------------------------------------------------
# Helper 3 — select tools for the sub-agent via LLM
# ---------------------------------------------------------------------------

def _select_tools_for_subagent(
    category: str,
    specialized_prompt: str,
) -> List[Any]:
    """
    Uses the specialised system prompt to choose the best subset of tools
    from the category's tool pool.  For now it returns all tools in the
    category; swap for LLM-driven selection when your tool list grows.
    """
    available_tools = TOOL_REGISTRY.get(category, [])

    if not available_tools:
        logger.warning("[Orchestrator] No tools registered for category '%s'.", category)
        return []

    # TODO: when tool list is large, add an LLM call here that receives
    #       `specialized_prompt` + tool descriptions and returns a subset.
    return available_tools


# ---------------------------------------------------------------------------
# Helper 4 — build the sub-agent using create_agent (modern API)
# ---------------------------------------------------------------------------

def _build_subagent(
    specialized_prompt: str,
    tools: List[Any],
    category: str,
) -> Any:
    """
    Constructs a LangChain agent using create_agent.
    The agent name is derived from the category for clean graph node naming.
    """
    agent = create_agent(
        model=getGeminiLLM(),           # can swap per-category if needed
        tools=tools,
        system_prompt=specialized_prompt,
        name=f"{category}_specialist",  # snake_case — safe across all providers
    )
    logger.info("[Orchestrator] Sub-agent built: %s_specialist", category)
    return agent


def _run_subagent_with_streaming(subagent: Any, user_message: str) -> Dict[str, Any]:
    """
    Run the sub-agent with streamed updates when available.
    Falls back to invoke() on older/unsupported runtime combinations.
    """
    input_payload = {"messages": [{"role": "user", "content": user_message}]}

    final_messages: List[Any] = []
    tool_calls: List[Any] = []
    printed_any_tokens = False

    def _render_chunk(event: Any) -> None:
        nonlocal printed_any_tokens, final_messages, tool_calls

        if not isinstance(event, dict):
            return

        event_type = event.get("type")
        data = event.get("data")

        if event_type == "messages" and isinstance(data, (list, tuple)) and data:
            token = data[0]
            if isinstance(token, AIMessageChunk):
                if token.text:
                    if not printed_any_tokens:
                        print("[orchestrator] sub-agent response stream:")
                        printed_any_tokens = True
                    print(token.text, end="", flush=True)
                if token.tool_call_chunks:
                    for tc in token.tool_call_chunks:
                        if tc.get("name"):
                            print(f"\n[orchestrator] tool call chunk: {tc['name']}", flush=True)

        elif event_type == "updates" and isinstance(data, dict):
            for step_name, step_update in data.items():
                messages = step_update.get("messages", []) if isinstance(step_update, dict) else []
                if messages:
                    final_messages = messages
                    msg = messages[-1]
                    if isinstance(msg, AIMessage) and msg.tool_calls:
                        tool_calls.extend(msg.tool_calls)
                        for call in msg.tool_calls:
                            call_name = call.get("name", "unknown_tool") if isinstance(call, dict) else str(call)
                            print(f"\n[orchestrator] tool requested: {call_name}", flush=True)
                    if isinstance(msg, ToolMessage):
                        print(f"\n[orchestrator] tool result ({step_name}): {msg.content}", flush=True)

    try:
        for event in subagent.stream(
            input_payload,
            stream_mode=["messages", "updates"],
            version="v2",
        ):
            _render_chunk(event)
    except TypeError:
        # Backward compatibility with versions that don't support `version`
        for event in subagent.stream(
            input_payload,
            stream_mode=["messages", "updates"],
        ):
            _render_chunk(event)
    except Exception:
        # Final fallback to non-streaming invocation
        logger.warning("[Orchestrator] Streaming unavailable, falling back to invoke().")
        result = subagent.invoke(input_payload)
        final_messages = result.get("messages", [])

    if printed_any_tokens:
        print()

    return {
        "messages": final_messages,
        "tool_calls": tool_calls,
    }


# ---------------------------------------------------------------------------
# Main orchestrator node
# ---------------------------------------------------------------------------

def orchestrator_node(state: APEXState) -> Dict[str, Any]:  # noqa: F821
    """
    LangGraph node — orchestrates specialised sub-agents to achieve the pentest goal.

    Reads:
        state.initial_prompt
        state.target
        state.recon_results
        state.recon_summary

    Writes:
        state.subagent_outputs   (dict keyed by category + iteration index)
        state.status
    """

    logger.info("[Orchestrator] Node started. Target: %s", state.target)

    # ------------------------------------------------------------------
    # 1. Determine the pentest category
    # ------------------------------------------------------------------
    category = _determine_pentest_category(
        initial_prompt=state.initial_prompt,
        recon_summary=state.recon_summary,
        recon_results=state.recon_results,
    )

    # ------------------------------------------------------------------
    # 2. Build context dict for prompt + tool selection
    # ------------------------------------------------------------------
    context: Dict[str, Any] = {
        "target":         state.target,
        "initial_prompt": state.initial_prompt,
        "recon_summary":  state.recon_summary,
        "recon_results":  state.recon_results,
        "category":       category,
    }

    # ------------------------------------------------------------------
    # 3. Generate specialised system prompt
    # ------------------------------------------------------------------
    specialized_prompt = _create_specialized_prompt(category=category, context=context)

    # ------------------------------------------------------------------
    # 4. Select tools
    # ------------------------------------------------------------------
    tools = _select_tools_for_subagent(
        category=category,
        specialized_prompt=specialized_prompt,
    )

    # ------------------------------------------------------------------
    # 5. Build the sub-agent (modern create_agent API)
    # ------------------------------------------------------------------
    subagent = _build_subagent(
        specialized_prompt=specialized_prompt,
        tools=tools,
        category=category,
    )

    # ------------------------------------------------------------------
    # 6. Run the sub-agent in an iteration loop (max 3 iterations)
    # ------------------------------------------------------------------
    MAX_ITERATIONS = 3
    subagent_outputs: Dict[str, Any] = dict(state.subagent_outputs)  # copy existing
    flag_captured = False

    for iteration in range(1, MAX_ITERATIONS + 1):
        logger.info("[Orchestrator] Running sub-agent iteration %d/%d", iteration, MAX_ITERATIONS)
        print(f"\n[orchestrator] iteration {iteration}/{MAX_ITERATIONS} started", flush=True)

        # Build the user message for this iteration, including any prior outputs
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

        # Streamed sub-agent invocation with fallback to non-streaming mode
        result = _run_subagent_with_streaming(subagent=subagent, user_message=user_message)

        # Extract the final AI message content
        final_messages = result.get("messages", [])
        if not final_messages:
            output_text = "No response messages returned by sub-agent."
        else:
            final_message = final_messages[-1]
            raw_content = final_message.content if hasattr(final_message, "content") else final_message
            output_text = _coerce_to_text(raw_content)

        # Store output keyed by category + iteration
        output_key = f"{category}_iter_{iteration}"
        subagent_outputs[output_key] = {
            "iteration":  iteration,
            "category":   category,
            "output":     output_text,
            "tool_calls": result.get("tool_calls", []),
        }

        logger.info("[Orchestrator] Iteration %d complete. Output stored as '%s'.", iteration, output_key)

        # ------------------------------------------------------------------
        # 7. Check whether the flag has been captured (simple heuristic;
        #    replace with a proper LLM-based judge if needed)
        # ------------------------------------------------------------------
        if _check_flag_captured(output_text):
            logger.info("[Orchestrator] Flag captured on iteration %d!", iteration)
            flag_captured = True
            break

    # ------------------------------------------------------------------
    # 8. Return state updates
    # ------------------------------------------------------------------
    new_status = "flag_captured" if flag_captured else "subagent_exhausted"
    logger.info("[Orchestrator] Node complete. Status: %s", new_status)

    return {
        "subagent_outputs": subagent_outputs,
        "status": new_status,
    }


# ---------------------------------------------------------------------------
# Utility — basic flag detection  (expand / replace as needed)
# ---------------------------------------------------------------------------

def _coerce_to_text(value: Any) -> str:
    """
    Convert model/tool outputs into a plain text string.
    Handles content-block lists produced by some chat models.
    """
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
                if isinstance(text, str) and text:
                    parts.append(text)
                else:
                    parts.append(json.dumps(item, ensure_ascii=False))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part)
    if isinstance(value, dict):
        text = value.get("text") if "text" in value else None
        if isinstance(text, str):
            return text
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _check_flag_captured(output: Any) -> bool:
    """
    Returns True if the output looks like a flag was found.
    Common CTF flag formats: FLAG{...}, HTB{...}, picoCTF{...}, etc.
    """
    import re
    flag_patterns = [
        r"FLAG\{[^}]+\}",
        r"HTB\{[^}]+\}",
        r"picoCTF\{[^}]+\}",
        r"CTF\{[^}]+\}",
        r"flag\{[^}]+\}",
    ]
    output_text = _coerce_to_text(output)
    for pattern in flag_patterns:
        if re.search(pattern, output_text, re.IGNORECASE):
            return True
    return False
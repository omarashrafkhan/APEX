from __future__ import annotations

import sys
import logging
import json
from typing import Any, Callable, Dict, Optional

from cli import parse_args, validate_inputs, initialize_state, run_interactive_cli
from graph import app
from state import APEXState

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def stream_and_interrupt_handler(
    initial_state: APEXState,
    progress_callback: Optional[Callable[[str, Dict[str, Any], Dict[str, Any]], None]] = None,
) -> APEXState:
    config = {"configurable": {"thread_id": initial_state.target}}
    logger.info(f"Starting engagement for target {initial_state.target}")

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
        logger.error(f"Graph execution failed: {e}", exc_info=True)
        initial_state.status = "failed"
        raise


def run_normal(args):
    """Original CLI flow — used when flags are passed."""
    try:
        validate_inputs(args)
        initial_state = initialize_state(args)
        final_state = stream_and_interrupt_handler(initial_state)

        logger.info("=" * 60)
        logger.info("ENGAGEMENT SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Target: {final_state.target}")
        logger.info(f"Status: {final_state.status}")
        logger.info(f"Recon summary: {final_state.recon_summary}")
        sqli_agent_spec = getattr(final_state, "sqli_agent_spec", {}) or {}
        sqli_attempt_result = getattr(final_state, "sqli_attempt_result", {}) or {}
        logger.info(
            "Selected SQLi tools: %s",
            ", ".join(sqli_agent_spec.get("selected_tools", []))
            if sqli_agent_spec
            else "none",
        )
        logger.info(
            "SQLi attempt result: %s", json.dumps(sqli_attempt_result)
        )
        logger.info("=" * 60)
        return 0

    except ValueError as e:
        logger.error(f"Invalid input: {e}")
        return 1
    except KeyboardInterrupt:
        logger.info("User interrupted execution")
        return 130
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        return 1


def main():
    # No flags passed → launch beautiful interactive CLI
    if len(sys.argv) == 1:
        run_interactive_cli(stream_and_interrupt_handler)
        return 0

    # Flags passed → original behavior
    args = parse_args()
    return run_normal(args)


if __name__ == "__main__":
    sys.exit(main())

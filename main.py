from __future__ import annotations

import sys
import logging
import json

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
) -> APEXState:
    config = {"configurable": {"thread_id": initial_state.target}}
    logger.info(f"Starting engagement for target {initial_state.target}")

    try:
        result = app.invoke(initial_state, config=config)

        if isinstance(result, APEXState):
            final_state = result
        elif isinstance(result, dict):
            merged = initial_state.model_dump()
            merged.update(result)
            final_state = APEXState(**merged)
        else:
            logger.warning(
                "Unexpected graph result type. Falling back to initial state"
            )
            final_state = initial_state

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
        logger.info(
            "Selected SQLi tools: %s",
            ", ".join(final_state.sqli_agent_spec.get("selected_tools", []))
            if final_state.sqli_agent_spec
            else "none",
        )
        logger.info(
            "SQLi attempt result: %s", json.dumps(final_state.sqli_attempt_result)
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

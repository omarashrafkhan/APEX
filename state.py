from __future__ import annotations

from typing import  Dict, Any
from pydantic import BaseModel, Field


class APEXState(BaseModel):
    # === Input ===
    initial_prompt: str
    target: str
    target_ip: str

    # === Execution Flags ===
    status: str = "initializing"

    # === Orchestration ===
    orchestrator_plan: Dict[str, Any] = Field(default_factory=dict)

    # === Recon ===
    recon_results: Dict[str, Any] = Field(default_factory=dict)
    recon_summary: str = ""

    # === SQLi Specialist Agent ===
    sqli_agent_spec: Dict[str, Any] = Field(default_factory=dict)
    sqli_attempt_result: Dict[str, Any] = Field(default_factory=dict)

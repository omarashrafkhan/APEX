from __future__ import annotations

from typing import  Dict, Any
from pydantic import BaseModel, Field


class APEXState(BaseModel):
    # === Input ===
    initial_prompt: str
    target: str

    # === Execution Flags ===
    status: str = "initializing"

    # === Recon ===
    recon_results: Dict[str, Any] = Field(default_factory=dict)
    recon_summary: str = ""

    # === subagent output===
    subagent_outputs: Dict[str, Any] = Field(default_factory=dict)

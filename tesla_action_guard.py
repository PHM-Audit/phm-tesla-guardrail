"""tesla_action_guard.py — deterministic pre-send command guard (reference implementation).

OPEN reference for the proposal in teslamotors/vehicle-command #517: a guard
that sits between your application and the vehicle-command SDK send call.

Checks (all operator-declared, deterministic, no network, no LLM):
  R-policy   command + parameter values within the operator's declared policy
  R-state    command vs declared vehicle state conflicts (e.g. the #509-class:
             climate-keeper mode vs cabin-pressure detection)
  R-unknown  command not in the command surface inventory

The example policy below is illustrative — bounds and conflict rules are
OPERATOR-DECLARED, not Tesla's internal rules (provenance in
tesla_command_surface.json).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).parent


class TeslaActionGuard:
    def __init__(self, policy: Dict[str, Any], surface_path: Optional[str] = None):
        self.policy = policy
        surface_file = Path(surface_path or HERE / "tesla_command_surface.json")
        self.surface = json.loads(surface_file.read_text()) if surface_file.exists() else {"commands": []}
        self.known = {c["command"] for c in self.surface.get("commands", [])}

    def check_command(self, command: str, args: Dict[str, Any],
                      vehicle_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        t0 = time.perf_counter()
        verdict: Dict[str, Any] = {"command": command, "verdict": "PASS", "rule": None, "reason": None}

        # R-unknown: not in the SDK command surface
        if self.known and command not in self.known:
            verdict.update({"verdict": "INTERCEPT", "rule": "R-unknown",
                            "reason": f"command not in SDK command surface: {command}"})
            verdict["guard_us"] = round((time.perf_counter() - t0) * 1e6, 2)
            return verdict

        # R-policy: operator-declared parameter bounds
        pol = self.policy.get("command_bounds", {}).get(command)
        if pol:
            for param, (lo, hi) in pol.items():
                if param in args:
                    v = args[param]
                    if not (lo <= v <= hi):
                        verdict.update({"verdict": "INTERCEPT", "rule": "R-policy",
                                        "reason": f"{command}.{param}={v} outside declared [{lo},{hi}]"})
                        verdict["guard_us"] = round((time.perf_counter() - t0) * 1e6, 2)
                        return verdict

        # R-state: declared state-vs-command conflicts (e.g. #509-class)
        state = vehicle_state or {}
        for rule in self.policy.get("state_conflicts", []):
            if all(state.get(k) == v for k, v in rule.get("if_state", {}).items()):
                denied = rule.get("deny", [])
                if command in denied or f"{command}:{args.get('mode')}" in denied:
                    verdict.update({"verdict": "INTERCEPT", "rule": rule.get("name", "R-state"),
                                    "reason": rule.get("reason", "state-vs-command conflict")})
                    verdict["guard_us"] = round((time.perf_counter() - t0) * 1e6, 2)
                    return verdict

        verdict["guard_us"] = round((time.perf_counter() - t0) * 1e6, 2)
        return verdict

"""demo_command_guard.py — GATE TEST: synthetic command stream through the guard.

Honest scope: commands are SYNTHETIC, checked against an EXAMPLE operator
policy (bounds/conflicts sourced from public community reports and common
documented behavior — NOT Tesla's internal rules). This is not real vehicle
field data. Deterministic, no RNG, no network.

Gate criteria: benign stream FP=0 AND all injected violations caught (FN=0).
Run: python3 demo_command_guard.py   (or bash run_demo.sh)
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from tesla_action_guard import TeslaActionGuard

HERE = Path(__file__).parent

# Example operator policy (operator-declared; NOT Tesla internal rules)
POLICY = {
    "command_bounds": {
        "ChangeChargeLimit": {"chargeLimitPercent": (50, 100)},
    },
    "state_conflicts": [
        {"name": "R-state-#509-class",
         "if_state": {"cpd_enabled": True},
         "deny": ["SetClimateKeeperMode:dog", "SetClimateKeeperMode:camp"],
         "reason": "climate-keeper mode conflicts with cabin pressure detection "
                   "(state-vs-command conflict reported in issue #509)"},
    ],
}

INJECTED = {
    300: {"command": "ChangeChargeLimit", "args": {"chargeLimitPercent": 30},
          "expect_rule": "R-policy"},                       # out-of-declared-bounds
    700: {"command": "SetClimateKeeperMode", "args": {"mode": "camp"},
          "state": {"cpd_enabled": True},
          "expect_rule": "R-state-#509-class"},             # #509-class conflict
    1100: {"command": "OpenFrunkRemotely", "args": {},
           "state": {"cpd_enabled": False},
           "expect_rule": "R-unknown"},                     # not in SDK surface
}


def main() -> dict:
    guard = TeslaActionGuard(POLICY)
    latencies, results, fp, caught = [], [], 0, 0
    benign_frames = 0

    stream = []
    for i in range(1500):
        if i in INJECTED:
            stream.append((i, INJECTED[i], True))
        else:
            # benign alternation inside declared bounds
            cmd = "ChangeChargeLimit" if i % 2 == 0 else "ChargeStart"
            args = {"chargeLimitPercent": 70 + (i % 21)} if i % 2 == 0 else {}
            stream.append((i, {"command": cmd, "args": args,
                               "state": {"cpd_enabled": i % 5 == 0}}, False))

    for i, (idx, case, injected) in enumerate(stream):
        cmd, args = case["command"], case["args"]
        state = case.get("state")
        t0 = time.perf_counter()
        v = guard.check_command(cmd, args, state)
        latencies.append((time.perf_counter() - t0) * 1e6)
        if injected:
            ok = v["verdict"] == "INTERCEPT" and v["rule"] == case["expect_rule"]
            caught += 1 if ok else 0
            if not ok:
                results.append({"frame": idx, "expected": case["expect_rule"],
                                "got": v["verdict"], "rule": v["rule"]})
        else:
            if v["verdict"] == "INTERCEPT":
                fp += 1
                results.append({"frame": idx, "unexpected": v})
            else:
                benign_frames += 1

    lat = sorted(latencies)
    p50 = round(lat[len(lat)//2], 2)
    p95 = round(lat[int(len(lat)*0.95)], 2)
    checks = {"benign_FP_zero": fp == 0, "injected_all_caught": len(results) == 0}
    verdict = "PASS" if all(checks.values()) else "REVIEW"

    out = {
        "test": "tesla vehicle-command pre-send guard gate (synthetic, example operator policy)",
        "date": time.strftime("%F %T"),
        "adk": None, "guard_overhead_us_p50": p50, "guard_overhead_us_p95": p95,
        "n_frames": len(stream), "n_benign": benign_frames, "n_injected": len(INJECTED),
        "FP": fp, "FN": len(results), "failures": results[:10], "checks": checks, "verdict": verdict,
        "honesty_notes": [
            "synthetic command stream; example operator policy is NOT Tesla internal rules",
            "no real vehicle field data; deterministic, no RNG",
            "provenance of command surface: tesla_command_surface.json",
        ],
    }
    out_path = HERE / "results" / "tesla_command_guard_results.json"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    chain = hashlib.sha256(out_path.read_bytes()).hexdigest()
    (HERE / "results" / "tesla_command_guard_results.sha256").write_text(
        chain + "  tesla_command_guard_results.json\n")

    print(f"=== Tesla vehicle-command pre-send guard gate (synthetic) ===")
    print(f"frames={len(stream)} benign={benign_frames} injected={len(INJECTED)} FP={fp} FN={len(results)}")
    print(f"guard p50={p50}us p95={p95}us")
    print(f"GATE: {verdict} | artifact sha256[:16]={chain[:16]}")
    return out


if __name__ == "__main__":
    main()

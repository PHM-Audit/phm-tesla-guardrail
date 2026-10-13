# PHM Tesla Guardrail

Deterministic pre-send command validation for Tesla `vehicle-command` SDK
calls — reference implementation for the proposal in
[teslamotors/vehicle-command #517](https://github.com/teslamotors/vehicle-command/issues/517).

Gate test artifact: 1500-frame synthetic command stream (1497 benign + 3
injected violations, deterministic no RNG) — **0 false positives on benign,
3/3 injected caught**, guard overhead p50 1.67 µs/check (2026-10-13,
`results/`, integrity sidecar included).

## What it checks (operator-declared policy, all deterministic)

- R-unknown: command must be in the SDK command surface (31 commands parsed
  from the `vehicle-command` Go source, `tesla_command_surface.json`)
- R-policy: parameter values within operator-declared bounds
  (e.g. `ChangeChargeLimit.chargeLimitPercent` within declared range)
- R-state: command vs declared vehicle-state conflicts — the #509-class
  (climate-keeper mode vs cabin pressure detection), sourced from community
  report #509

Refusal records are the audit/ledger entries (see the #517 discussion).

## Honest scope

- The example policy is OPERATOR-DECLARED, **not Tesla's internal rules**
  (provenance: `tesla_command_surface.json` — parsed from the SDK source,
  which itself passes parameters through without semantic validation)
- Synthetic command stream; no real vehicle field data
- Single run, n=1500 mechanism demonstration, not a statistical claim
- One self-caught bug during the gate: the initial surface extraction missed
  zero-parameter commands (regex required a trailing comma), which falsely
  flagged all `ChargeStart` calls — fixed and re-run; the extraction harness
  is now covered by the gate itself

## Files

- `tesla_action_guard.py` — the guard (self-contained)
- `tesla_command_surface.json` — command surface parsed from SDK source
- `demo_command_guard.py` / `run_demo.sh` — gate test
- `results/` — raw gate record + sha256 sidecar

## License

MIT.

---

**PHM evidence chain** — aggregate ledger: [phm-evidence-ledger](https://github.com/PHM-Audit/phm-evidence-ledger) (5,000,086,001 units, four layers, open metrics + SHA-256 manifest) · method parent: [agent-action-verifier](https://github.com/PHM-Audit/agent-action-verifier) (AgentDojo-validated) · [PHM-Audit profile](https://github.com/PHM-Audit)

# CogniShift Documentation Map

Updated 2026-09-05. The September 5 audit is the current verification record; earlier blanket acceptance claims are historical, not proof of current live readiness.

| Document | Purpose |
|---|---|
| `LOCAL_OPERATIONS_RUNBOOK.md` | Canonical 23-section local operations runbook, multi-domain setup, and browser acceptance guide |
| `SANDBOX_CAPABILITIES.md` | Real container capabilities, limits, deep test outcomes and remaining hardening gaps |
| `../README.md` | Product overview, installation, runtime, and test entry point |
| `../ARCHITECTURE.md` | Security boundaries, components, and data flows |
| `../CLI.md` | Current Typer CLI syntax and command reference |
| `../BENCHMARKS.md` | Synthetic benchmark scope and verified regression baseline |
| `SIH_OFFLINE_DEMO_RUNBOOK.md` | Authoritative operator startup and live demo sequence |
| `PHASE7_OFFLINE_ACCEPTANCE.md` | Current automated acceptance summary and human gate |
| `SYSTEM_AUDIT_2026-09-05.md` | Current audit, repairs, all 235 automated outcomes and explicit remaining gaps |
| `WORKFLOW_VALIDATION_REPORT.md` | Previous workflow validation record; consult the current audit for limitations |
| `../artifacts/phase6_firewall_final/HUMAN_RECHECK.md` | Independent Windows firewall causality procedure |

Documentation rules:

- Do not claim physical disconnection merely because an interface is down; report adapter state separately from enforced policy.
- Do not publish credentials, bearer tokens, prompts, or confidential payloads.
- Record exact current test counts and all skips/failures.
- Keep one authoritative runbook instead of parallel copies.

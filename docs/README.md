# CogniShift Documentation Map

Updated 2026-09-04. Historical planning and duplicate audit reports were removed from the working tree; they remain recoverable from Git history.

| Document | Purpose |
|---|---|
| `../README.md` | Product overview, installation, runtime, and test entry point |
| `../ARCHITECTURE.md` | Security boundaries, components, and data flows |
| `../CLI.md` | Current Typer CLI syntax and command reference |
| `../BENCHMARKS.md` | Synthetic benchmark scope and verified regression baseline |
| `SIH_OFFLINE_DEMO_RUNBOOK.md` | Authoritative operator startup and live demo sequence |
| `PHASE7_OFFLINE_ACCEPTANCE.md` | Current automated acceptance summary and human gate |
| `WORKFLOW_VALIDATION_REPORT.md` | Latest exhaustive feature/workflow outcome artifact |
| `../artifacts/phase6_firewall_final/HUMAN_RECHECK.md` | Independent Windows firewall causality procedure |

Documentation rules:

- Do not claim physical disconnection merely because an interface is down; report adapter state separately from enforced policy.
- Do not publish credentials, bearer tokens, prompts, or confidential payloads.
- Record exact current test counts and all skips/failures.
- Keep one authoritative runbook instead of parallel copies.

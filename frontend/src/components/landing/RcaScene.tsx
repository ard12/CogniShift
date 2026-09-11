import { useState } from "react";
import { IconCheck, IconShieldCheck } from "@/components/ui/Icon";

export function RcaScene() {
  const [activeView, setActiveView] = useState<"flow" | "report">("flow");

  return (
    <section id="rca-protocol" className="py-20 px-4 sm:px-8 max-w-6xl mx-auto border-b border-surface-border">
      <div className="text-center max-w-3xl mx-auto mb-12 space-y-3">
        <div className="inline-flex items-center gap-2 rounded-full border border-amber-500/40 bg-amber-500/10 px-3 py-0.5 text-xs font-mono text-amber-400">
          <IconShieldCheck className="h-3.5 w-3.5" />
          <span>SECTION 17 INVESTIGATION PROTOCOL</span>
        </div>
        <h2 className="text-2xl sm:text-4xl font-bold text-ink-1">
          Root Cause Analysis &amp; Failure Mode Isolation
        </h2>
        <p className="text-xs sm:text-sm text-ink-2 leading-relaxed">
          Tested against 7/7 live industrial benchmark scenarios (100% RCSA, 100% PCA, 0.0% Hallucination).
          CogniShift systematically generates hypotheses, challenges them against distractor signals, and produces legally compliant RCA dossiers.
        </p>
      </div>

      {/* Mode switcher */}
      <div className="flex justify-center gap-2 mb-6">
        <button
          type="button"
          onClick={() => setActiveView("flow")}
          className={`rounded-lg px-4 py-1.5 font-mono text-xs font-semibold border transition cursor-pointer ${
            activeView === "flow"
              ? "bg-brand text-black border-brand shadow-sm"
              : "bg-surface-2 text-ink-2 border-surface-border hover:bg-surface-3"
          }`}
        >
          Observation Convergence Flow
        </button>
        <button
          type="button"
          onClick={() => setActiveView("report")}
          className={`rounded-lg px-4 py-1.5 font-mono text-xs font-semibold border transition cursor-pointer ${
            activeView === "report"
              ? "bg-brand text-black border-brand shadow-sm"
              : "bg-surface-2 text-ink-2 border-surface-border hover:bg-surface-3"
          }`}
        >
          Section 17 Protocol Dossier
        </button>
      </div>

      {activeView === "flow" ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Step 1: Physical Telemetry Observations */}
          <div className="rounded-xl border border-surface-border bg-surface-2/70 p-5 space-y-3">
            <span className="font-mono text-[10px] text-brand font-bold uppercase tracking-wider block">
              1. Physical Telemetry Observations
            </span>
            <div className="space-y-2 font-mono text-xs text-ink-2">
              <div className="rounded border border-surface-border bg-surface-1 p-2.5">
                <div className="text-ink-1 font-semibold">Sensor PT-101 (Discharge)</div>
                <div className="text-[11px] text-amber-300">Surge to 495 PSI (MAWP 450 PSI)</div>
              </div>
              <div className="rounded border border-surface-border bg-surface-1 p-2.5">
                <div className="text-ink-1 font-semibold">Vibration Transmitter VT-104</div>
                <div className="text-[11px] text-amber-300">High frequency 7.8 mm/s on DE Bearing</div>
              </div>
              <div className="rounded border border-surface-border bg-surface-1 p-2.5">
                <div className="text-ink-1 font-semibold">Flow Meter FT-302</div>
                <div className="text-[11px] text-amber-300">Erratic flow oscillation (-32% swing)</div>
              </div>
            </div>
          </div>

          {/* Step 2: Counter-Hypothesis Rejection */}
          <div className="rounded-xl border border-surface-border bg-surface-2/70 p-5 space-y-3">
            <span className="font-mono text-[10px] text-status-warning font-bold uppercase tracking-wider block">
              2. Counter-Hypothesis Testing
            </span>
            <div className="space-y-2 font-mono text-xs">
              <div className="rounded border border-status-error/30 bg-status-error/10 p-2.5 text-status-error">
                <div className="font-bold flex items-center justify-between">
                  <span>H1: Sensor Calibration Drift</span>
                  <span>REJECTED</span>
                </div>
                <p className="text-[10px] text-ink-3 mt-1 font-sans">
                  Dual sensor PT-102 correlates within 1.2%. Drift disproven by independent transmitter cross-check.
                </p>
              </div>

              <div className="rounded border border-status-error/30 bg-status-error/10 p-2.5 text-status-error">
                <div className="font-bold flex items-center justify-between">
                  <span>H2: Motor Electrical Overheat</span>
                  <span>REJECTED</span>
                </div>
                <p className="text-[10px] text-ink-3 mt-1 font-sans">
                  Winding temperatures nominal (64°C). Current draw within continuous rated FLA.
                </p>
              </div>
            </div>
          </div>

          {/* Step 3: Confirmed Primary Cause */}
          <div className="rounded-xl border-2 border-emerald-500/50 bg-emerald-500/5 p-5 space-y-3 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono text-[10px] text-emerald-400 font-bold uppercase tracking-wider">
                  3. Verified Primary Cause
                </span>
                <span className="rounded bg-emerald-500/20 px-2 py-0.5 font-mono text-[10px] font-bold text-emerald-300">
                  96.4% CONFIDENCE
                </span>
              </div>
              <h3 className="font-mono text-base font-bold text-ink-1">
                MEC_PUMP_CAVITATION
              </h3>
              <p className="font-mono text-xs text-brand font-semibold mt-1">
                Asset: P-101A (Booster Pump)
              </p>
              <p className="text-xs text-ink-2 font-sans mt-2 leading-relaxed">
                Suction strainer DP reached 1.8 bar causing Net Positive Suction Head Available (NPSHa) to drop below NPSHr, inducing vapor collapse at impeller eye.
              </p>
            </div>

            <div className="pt-3 border-t border-emerald-500/20 font-mono text-[11px] text-emerald-300 flex items-center gap-1.5">
              <IconCheck className="h-4 w-4" />
              <span>Grounded Citations: [E1: p.42] [E3: API-610]</span>
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-xl border border-surface-border bg-surface-1 p-6 font-mono text-xs space-y-4">
          <div className="flex items-center justify-between border-b border-surface-border pb-3">
            <span className="text-brand font-bold uppercase">
              SECTION 17 ROOT CAUSE INVESTIGATION REPORT #RCA-2026-004
            </span>
            <span className="rounded bg-emerald-500/20 px-2 py-0.5 text-emerald-400 font-bold">
              STATUS: CONFIRMED_CAUSE
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-surface-2 p-3 rounded-lg text-[11px]">
            <div><span className="text-ink-3 block">Target Asset:</span> <strong>P-101A</strong></div>
            <div><span className="text-ink-3 block">Process Unit:</span> <strong>Hydrotreater U-04</strong></div>
            <div><span className="text-ink-3 block">Failure Code:</span> <strong className="text-amber-300">MEC_PUMP_CAVITATION</strong></div>
            <div><span className="text-ink-3 block">Investigator:</span> <strong>CogniShift Sovereign Engine</strong></div>
          </div>

          <div className="space-y-2 text-ink-2 leading-relaxed font-sans text-xs">
            <p className="font-bold font-mono text-ink-1 text-xs">17.1 PHYSICAL SEQUENCE OF EVENTS</p>
            <p>
              At 02:48:10 IST, transmitter PT-101 registered discharge pressure fluctuations from 380 PSI to 495 PSI.
              Concurrently, vibration sensor VT-104 indicated blade-pass frequency harmonics characteristic of cavitation vortex collapse.
            </p>

            <p className="font-bold font-mono text-ink-1 text-xs mt-3">17.2 IMMEDIATE MITIGATING ACTIONS</p>
            <ul className="list-disc pl-5 space-y-1 text-[11px] font-mono">
              <li>Energize auxiliary bypass valve FV-302 to restore minimum recirculation flow.</li>
              <li>Trip motorized suction block valve if discharge pressure fails to stabilize within 90 seconds.</li>
              <li>Schedule maintenance permit for suction strainer basket cleanout.</li>
            </ul>
          </div>
        </div>
      )}
    </section>
  );
}

import { useEffect } from "react";
import {
  LandingHeader,
  HeroScene,
  SovereigntyScene,
  HybridRagScene,
  VisualEvidenceScene,
  RcaScene,
  GovernanceScene,
  LocalExecutionScene,
  ArtifactScene,
  WorkbenchTransition,
  LandingFooter,
} from "@/components/landing";

export function LandingPage() {
  useEffect(() => {
    document.title = "CogniShift — Sovereign Industrial AI Workbench";
  }, []);

  const handleScrollTo = (sectionId: string) => {
    const el = document.getElementById(sectionId);
    if (el) {
      el.scrollIntoView({ behavior: "smooth" });
    }
  };

  return (
    <div className="min-h-screen bg-surface-1 text-ink-1 flex flex-col selection:bg-brand/30">
      <LandingHeader onScrollTo={handleScrollTo} />
      <main className="flex-1">
        <HeroScene />
        <SovereigntyScene />
        <HybridRagScene />
        <VisualEvidenceScene />
        <RcaScene />
        <GovernanceScene />
        <LocalExecutionScene />
        <ArtifactScene />
        <WorkbenchTransition />
      </main>
      <LandingFooter />
    </div>
  );
}

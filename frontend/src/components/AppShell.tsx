import { useState } from "react";
import { Outlet } from "react-router-dom";
import { useAuth } from "@/auth/useAuth";
import { Sidebar } from "@/components/Sidebar";
import { StatusBeacon } from "@/components/StatusBeacon";
import { WorkspacePicker } from "@/components/WorkspacePicker";
import { Button } from "@/components/ui/Button";
import { IconLogOut, IconX } from "@/components/ui/Icon";
import { cn } from "@/lib/cn";

function Brand() {
  return (
    <div className="flex h-14 shrink-0 items-center gap-2 border-b border-surface-border px-4">
      <span className="text-lg text-brand" aria-hidden="true">
        ⬡
      </span>
      <span className="font-mono text-sm font-bold tracking-widest text-ink-1">COGNISHIFT</span>
      <span className="ml-auto rounded border border-surface-border bg-surface-3 px-1.5 py-0.5 font-mono text-[9px] font-medium text-ink-3">
        SIH26117
      </span>
    </div>
  );
}

export function AppShell() {
  const { role, sovereignty, signOut } = useAuth();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const sovereigntyTone = sovereignty?.sovereignty_enforced ? "success" : "warning";
  const sovereigntyLabel = sovereignty?.sovereignty_enforced
    ? "SOVEREIGN POLICY ACTIVE"
    : sovereignty
    ? "PUBLIC EGRESS ALLOWED"
    : "SOVEREIGNTY UNKNOWN";

  return (
    <div className="flex h-screen overflow-hidden bg-surface-1 text-ink-1">
      {/* Desktop sidebar */}
      <aside className="hidden w-56 shrink-0 flex-col border-r border-surface-border bg-surface-2 lg:flex">
        <Brand />
        <Sidebar />
      </aside>

      {/* Mobile drawer */}
      {mobileNavOpen && (
        <div className="fixed inset-0 z-40 flex lg:hidden">
          <div className="absolute inset-0 bg-black/70" onClick={() => setMobileNavOpen(false)} />
          <aside className="relative z-10 flex w-64 flex-col border-r border-surface-border bg-surface-2">
            <div className="flex items-center justify-between">
              <Brand />
              <button
                type="button"
                className="mr-3 rounded p-1 text-ink-3 hover:bg-surface-3 hover:text-ink-1"
                onClick={() => setMobileNavOpen(false)}
                aria-label="Close navigation"
              >
                <IconX className="h-4 w-4" />
              </button>
            </div>
            <Sidebar onNavigate={() => setMobileNavOpen(false)} />
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top status bar */}
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-surface-border bg-surface-2 px-3 sm:px-4">
          <button
            type="button"
            className="rounded p-1.5 text-ink-2 hover:bg-surface-3 lg:hidden"
            onClick={() => setMobileNavOpen(true)}
            aria-label="Open navigation"
          >
            <span className="block h-4 w-4">
              <span className="mb-1 block h-0.5 w-full bg-current" />
              <span className="mb-1 block h-0.5 w-full bg-current" />
              <span className="block h-0.5 w-full bg-current" />
            </span>
          </button>

          <div className="flex items-center gap-1.5 text-[11px] text-ink-3">
            <span className="hidden font-mono uppercase tracking-wide sm:inline">WS</span>
            <WorkspacePicker className="w-40 sm:w-56" />
          </div>

          <div
            className={cn(
              "ml-auto hidden items-center gap-2 rounded-full border border-surface-border bg-surface-3/60 px-3 py-1 md:flex"
            )}
          >
            <StatusBeacon tone={sovereigntyTone} label={sovereigntyLabel} />
          </div>

          <div className="flex items-center gap-2 pl-2">
            {role && (
              <span className="hidden rounded border border-surface-border bg-surface-3 px-2 py-1 font-mono text-[10px] uppercase tracking-wide text-ink-2 sm:inline">
                {role}
              </span>
            )}
            <Button variant="ghost" size="sm" onClick={signOut} title="Sign out">
              <IconLogOut className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Sign out</span>
            </Button>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-4 sm:p-6">
          <div className="mx-auto flex max-w-[1600px] flex-col gap-6">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
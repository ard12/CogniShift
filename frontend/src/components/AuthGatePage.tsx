import { useState, type FormEvent } from "react";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/ui/Button";
import { InlineError } from "@/components/ui/States";

export function AuthGatePage() {
  const { signIn, verifying, error } = useAuth();
  const [tokenInput, setTokenInput] = useState("");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    await signIn(tokenInput);
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-1 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-2 text-center">
          <span className="text-2xl text-brand" aria-hidden="true">
            ⬡
          </span>
          <h1 className="font-mono text-lg font-bold tracking-widest text-ink-1">COGNISHIFT</h1>
          <p className="text-xs text-ink-3">Sovereign Industrial Workbench — Operator Sign-In</p>
        </div>

        <form onSubmit={handleSubmit} className="panel flex flex-col gap-4 p-5">
          <div>
            <label htmlFor="token" className="label mb-1.5 block">
              Access token
            </label>
            <input
              id="token"
              type="text"
              autoComplete="off"
              spellCheck={false}
              className="input font-mono"
              placeholder="zara, rohit, sitanshu…"
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
              autoFocus
            />
            
            <div className="mt-3 flex flex-col gap-1.5">
              <span className="text-[10px] font-mono uppercase tracking-wider text-ink-3">Quick Connect Personas:</span>
              <div className="grid grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={() => { setTokenInput("zara"); void signIn("zara"); }}
                  className="rounded border border-surface-border bg-surface-2 px-2 py-2 text-center text-xs font-mono font-medium text-ink-1 hover:border-brand hover:bg-brand/10 transition"
                >
                  <span className="block font-bold text-brand">Zara</span>
                  <span className="text-[10px] text-ink-3">Operator</span>
                </button>
                <button
                  type="button"
                  onClick={() => { setTokenInput("rohit"); void signIn("rohit"); }}
                  className="rounded border border-surface-border bg-surface-2 px-2 py-2 text-center text-xs font-mono font-medium text-ink-1 hover:border-status-warning hover:bg-status-warning/10 transition"
                >
                  <span className="block font-bold text-status-warning">Rohit</span>
                  <span className="text-[10px] text-ink-3">Supervisor</span>
                </button>
                <button
                  type="button"
                  onClick={() => { setTokenInput("sitanshu"); void signIn("sitanshu"); }}
                  className="rounded border border-surface-border bg-surface-2 px-2 py-2 text-center text-xs font-mono font-medium text-ink-1 hover:border-status-knowledge hover:bg-status-knowledge/10 transition"
                >
                  <span className="block font-bold text-status-knowledge">Sitanshu</span>
                  <span className="text-[10px] text-ink-3">Admin</span>
                </button>
              </div>
            </div>

            <p className="mt-2 text-[11px] leading-relaxed text-ink-3">
              Enter your access token or select a quick-connect role above.
            </p>
          </div>

          {error && <InlineError message={error} />}

          <Button type="submit" variant="primary" loading={verifying} disabled={!tokenInput.trim()}>
            Connect
          </Button>
        </form>

        <p className="mt-4 text-center text-[11px] text-ink-3">
          Runs entirely on local infrastructure — no cloud AI APIs, no external egress.
        </p>
      </div>
    </div>
  );
}
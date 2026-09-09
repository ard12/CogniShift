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
    <div className="flex min-h-screen items-center justify-center bg-transparent px-4">
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
              type="password"
              autoComplete="off"
              spellCheck={false}
              className="input font-mono"
              placeholder="cog_op_…"
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
              autoFocus
            />
            <p className="mt-1.5 text-[11px] leading-relaxed text-ink-3">
              CogniShift has no username/password login — every request is authenticated with a
              server-issued bearer credential. Ask an administrator to run{" "}
              <code className="kbd">scripts/bootstrap_demo_auth.py</code> and share a token with
              you.
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
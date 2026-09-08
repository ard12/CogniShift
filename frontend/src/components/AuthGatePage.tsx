import { useState, type FormEvent } from "react";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/ui/Button";
import { InlineError } from "@/components/ui/States";

export function AuthGatePage() {
  const { signIn, verifying, error, deviceStatus, retryVerification } = useAuth();
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
              placeholder="Paste an issued access token"
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
              autoFocus
            />

            <p className="mt-2 text-[11px] leading-relaxed text-ink-3">
              Enter your issued sovereign access token to connect.
            </p>
          </div>

          {error && (
            deviceStatus === "unknown" ? (
              <div className="rounded border border-status-warning/50 bg-status-warning/10 p-3 font-mono text-xs leading-6 text-status-warning whitespace-pre-line">
                {error}
                <div className="mt-3">
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    loading={verifying}
                    onClick={() => void retryVerification()}
                    className="w-full border-status-warning/50 text-status-warning hover:bg-status-warning/20 font-sans text-xs"
                  >
                    Retry Device Verification
                  </Button>
                </div>
              </div>
            ) : <InlineError message={error} />
          )}

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

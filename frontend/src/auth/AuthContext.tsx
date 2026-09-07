import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { ApiError } from "@/api/clients";
import { systemApi } from "@/api/system";
import { getStoredToken, setStoredToken } from "../lib/token-storage";
import type { SovereigntyStatus } from "@/types";
import { AuthContext, type AuthContextValue } from "./auth-context";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [sovereignty, setSovereignty] = useState<SovereigntyStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const verify = useCallback(async (candidate: string): Promise<boolean> => {
    setVerifying(true);
    setError(null);
    try {
      const status = await systemApi.sovereignty(candidate);
      setSovereignty(status);
      setToken(candidate);
      setStoredToken(candidate);
      return true;
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("That token was not recognized. Check the credential and try again.");
      } else if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Could not reach the CogniShift backend. Is the server running?");
      }
      setToken(null);
      setStoredToken(null);
      return false;
    } finally {
      setVerifying(false);
    }
  }, []);

  useEffect(() => {
    const stored = getStoredToken();
    if (!stored) {
      setReady(true);
      return;
    }
    void verify(stored).finally(() => setReady(true));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const signIn = useCallback(
    async (rawToken: string) => {
      const trimmed = rawToken.trim();
      if (!trimmed) {
        setError("Enter a credential token.");
        return false;
      }
      return verify(trimmed);
    },
    [verify]
  );

  const signOut = useCallback(() => {
    setToken(null);
    setSovereignty(null);
    setError(null);
    setStoredToken(null);
  }, []);

  const refreshSovereignty = useCallback(async () => {
    if (!token) return;
    try {
      const status = await systemApi.sovereignty(token);
      setSovereignty(status);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        signOut();
      }
    }
  }, [token, signOut]);

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      ready,
      verifying,
      role: sovereignty?.user_role ?? null,
      sovereignty,
      error,
      signIn,
      signOut,
      refreshSovereignty,
    }),
    [token, ready, verifying, sovereignty, error, signIn, signOut, refreshSovereignty]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { ApiError } from "@/api/clients";
import { authApi } from "@/api/auth";
import { systemApi } from "@/api/system";
import { ensureDeviceIdentity, setDeviceSession } from "@/lib/device-identity";
import { getStoredToken, setStoredToken } from "../lib/token-storage";
import type { SovereigntyStatus } from "@/types";
import { AuthContext, type AuthContextValue } from "./auth-context";

const DEMO_SESSION_KEY = "cognishift_demo_session";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [sovereignty, setSovereignty] = useState<SovereigntyStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deviceStatus, setDeviceStatus] = useState<"trusted" | "unknown" | "not_verified">("not_verified");

  const verify = useCallback(async (candidate: string): Promise<boolean> => {
    setVerifying(true);
    setError(null);
    try {
      const identity = await ensureDeviceIdentity();
      const challenge = await authApi.challenge(candidate, {
        device_id: identity.deviceId,
        display_name: identity.displayName,
        public_key_jwk: identity.publicKeyJwk,
      });
      const signature = await identity.sign(challenge.challenge);
      const verifiedDevice = await authApi.verifyDevice(candidate, {
        device_id: identity.deviceId,
        challenge_id: challenge.challenge_id,
        signature,
      });
      setDeviceSession(verifiedDevice.device_session);
      setDeviceStatus("trusted");
      const status = await systemApi.sovereignty(candidate);
      setSovereignty(status);
      setToken(candidate);
      setStoredToken(candidate);
      localStorage.removeItem(DEMO_SESSION_KEY);
      return true;
    } catch (err) {
      if (err instanceof ApiError && err.status === 403 && typeof err.detail === "object" && err.detail && (err.detail as {code?: string}).code === "UNKNOWN_DEVICE") {
        setDeviceStatus("unknown");
        setError("⚠ Unknown Device\nCredentials Verified\nDevice Verification Failed\nAdministrator Approval Required");
      } else if (err instanceof ApiError && err.status === 401) {
        setError("That token was not recognized. Check the credential and try again.");
      } else if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Could not reach the CogniShift backend. Is the server running?");
      }
      setToken(null);
      setDeviceSession(null);
      setStoredToken(null);
      localStorage.removeItem(DEMO_SESSION_KEY);
      return false;
    } finally {
      setVerifying(false);
    }
  }, []);

  const signInDemo = useCallback(async (personaId: string) => {
    setVerifying(true);
    setError(null);
    try {
      const session = await authApi.demoSession(personaId);
      return await verify(session.session_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Demo session unavailable.");
      return false;
    } finally {
      setVerifying(false);
    }
  }, [verify]);

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
      localStorage.removeItem(DEMO_SESSION_KEY);
      return verify(trimmed);
    },
    [verify]
  );

  const signOut = useCallback(() => {
    setToken(null);
    setSovereignty(null);
    setError(null);
    setStoredToken(null);
    setDeviceSession(null);
    localStorage.removeItem(DEMO_SESSION_KEY);
    setDeviceStatus("not_verified");
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
      deviceStatus,
      signIn,
      signInDemo,
      signOut,
      refreshSovereignty,
    }),
    [token, ready, verifying, sovereignty, error, deviceStatus, signIn, signInDemo, signOut, refreshSovereignty]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

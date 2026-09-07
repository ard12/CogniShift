import { createContext } from "react";
import type { SovereigntyStatus, UserRole } from "@/types";

export interface AuthContextValue {
  /** The raw bearer token, or null if not signed in. */
  token: string | null;
  /** True once the initial token verification attempt has finished. */
  ready: boolean;
  /** True while verifying a token against the backend. */
  verifying: boolean;
  /** The authenticated user's role, known once sovereignty status has loaded. */
  role: UserRole | null;
  /** Full sovereignty snapshot fetched at sign-in time, refreshed on demand. */
  sovereignty: SovereigntyStatus | null;
  /** Set when the stored/submitted token is rejected by the backend. */
  error: string | null;
  signIn: (rawToken: string) => Promise<boolean>;
  signOut: () => void;
  refreshSovereignty: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { workspacesApi } from "@/api/workspaces";
import { useAuth } from "@/auth/useAuth";
import type { Workspace } from "@/types";
import { WorkspaceContext, type WorkspaceContextValue } from "./workspace-context";

const SELECTED_WORKSPACE_KEY = "cognishift.selected_workspace_id";

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { token } = useAuth();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<number | null>(() => {
    const stored = window.localStorage.getItem(SELECTED_WORKSPACE_KEY);
    return stored ? Number(stored) : null;
  });

  const load = useCallback(async () => {
    if (!token) {
      setWorkspaces([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const list = await workspacesApi.list();
      setWorkspaces(list);
      setSelectedWorkspaceId((current) => {
        if (current && list.some((w) => w.id === current)) return current;
        return list[0]?.id ?? null;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load workspaces.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  const selectWorkspace = useCallback((id: number) => {
    setSelectedWorkspaceId(id);
    window.localStorage.setItem(SELECTED_WORKSPACE_KEY, String(id));
  }, []);

  const selectedWorkspace = useMemo(
    () => workspaces.find((w) => w.id === selectedWorkspaceId) ?? null,
    [workspaces, selectedWorkspaceId]
  );

  const value = useMemo<WorkspaceContextValue>(
    () => ({
      workspaces,
      loading,
      error,
      selectedWorkspaceId,
      selectedWorkspace,
      selectWorkspace,
      refresh: load,
    }),
    [workspaces, loading, error, selectedWorkspaceId, selectedWorkspace, selectWorkspace, load]
  );

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

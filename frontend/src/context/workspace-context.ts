import { createContext } from "react";
import type { Workspace } from "@/types";

export interface WorkspaceContextValue {
  workspaces: Workspace[];
  loading: boolean;
  error: string | null;
  selectedWorkspaceId: number | null;
  selectedWorkspace: Workspace | null;
  selectWorkspace: (id: number) => void;
  refresh: () => Promise<void>;
}

export const WorkspaceContext = createContext<WorkspaceContextValue | undefined>(undefined);

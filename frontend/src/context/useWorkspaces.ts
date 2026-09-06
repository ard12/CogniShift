import { useContext } from "react";
import { WorkspaceContext, type WorkspaceContextValue } from "./workspace-context";

export function useWorkspaces(): WorkspaceContextValue {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) {
    throw new Error("useWorkspaces must be used within a WorkspaceProvider");
  }
  return ctx;
}

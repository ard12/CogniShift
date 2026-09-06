import { useWorkspaces } from "@/context/useWorkspaces";

export function WorkspacePicker({ className }: { className?: string }) {
  const { workspaces, loading, selectedWorkspaceId, selectWorkspace } = useWorkspaces();

  if (!loading && workspaces.length === 0) {
    return <span className="text-xs font-mono text-ink-3">No workspaces</span>;
  }

  return (
    <select
      className={className}
      value={selectedWorkspaceId ?? ""}
      disabled={loading || workspaces.length === 0}
      onChange={(e) => selectWorkspace(Number(e.target.value))}
      aria-label="Active workspace"
    >
      {loading && <option>Loading…</option>}
      {workspaces.map((ws: (typeof workspaces)[number]) => (
        <option key={ws.id} value={ws.id}>
          {ws.name}
        </option>
      ))}
    </select>
  );
}
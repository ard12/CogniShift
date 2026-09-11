import { useEffect, useRef, useState } from "react";
import { ApiError } from "@/api/clients";
import { knowledgeApi } from "@/api/knowledge";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { IconBook, IconTrash, IconUpload } from "@/components/ui/Icon";
import { PageHeader } from "@/components/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { EmptyState, ErrorState, InlineError, LoadingState } from "@/components/ui/States";
import { useWorkspaces } from "@/context/useWorkspaces";
import { formatRelativeTime, processingStatusTone } from "@/lib/format";
import type { KnowledgeSource } from "@/types";

export function KnowledgePage() {
  const { selectedWorkspaceId, selectedWorkspace } = useWorkspaces();
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<KnowledgeSource | null>(null);
  const [deleting, setDeleting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const load = async () => {
    if (!selectedWorkspaceId) {
      setSources([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const list = await knowledgeApi.list(selectedWorkspaceId);
      setSources(list);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load knowledge sources.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedWorkspaceId]);

  async function handleFileSelected(file: File | undefined) {
    if (!file || !selectedWorkspaceId) return;
    setUploading(true);
    setUploadError(null);
    try {
      await knowledgeApi.upload(file, selectedWorkspaceId);
      await load();
    } catch (err) {
      setUploadError(err instanceof ApiError ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function confirmDelete() {
    if (!pendingDelete) return;
    setDeleting(true);
    try {
      await knowledgeApi.remove(pendingDelete.id);
      setPendingDelete(null);
      await load();
    } catch (err) {
      setUploadError(err instanceof ApiError ? err.message : "Delete failed.");
      setPendingDelete(null);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Sovereign Knowledge Vault"
        description={
          selectedWorkspace
            ? `Documents (Word DOCX, PDF), operational spreadsheets (XLSX, CSV), and inspection photos (PNG, JPEG) ingested for ${selectedWorkspace.name}. Ingested materials are semantically indexed into local ChromaDB for agent RAG and sandboxed data analysis.`
            : "Documents, operational spreadsheets, and inspection photos ingested for retrieval and sandboxed analysis during agent runs."
        }
        actions={
          selectedWorkspaceId ? (
            <>
              <input
                ref={fileInputRef}
                type="file"
                accept=".docx,.xlsx,.csv,.pdf,.png,.jpg,.jpeg"
                className="hidden"
                onChange={(e) => void handleFileSelected(e.target.files?.[0])}
              />
              <Button
                variant="primary"
                size="sm"
                onClick={() => fileInputRef.current?.click()}
                loading={uploading}
                title="Upload Word document (.docx), Excel spreadsheet (.xlsx), CSV, PDF manual, or inspection photo"
              >
                <IconUpload className="h-3.5 w-3.5" /> Upload document / spreadsheet
              </Button>
            </>
          ) : undefined
        }
      />

      {uploadError && <InlineError message={uploadError} />}

      {!selectedWorkspaceId ? (
        <EmptyState title="Select a workspace" description="Choose a workspace from the top bar to view its knowledge vault." />
      ) : (
        <div
          onDragOver={(e: React.DragEvent<HTMLDivElement>) => {
            e.preventDefault();
            e.stopPropagation();
          }}
          onDrop={(e: React.DragEvent<HTMLDivElement>) => {
            e.preventDefault();
            e.stopPropagation();
            const f = e.dataTransfer.files?.[0];
            if (f) void handleFileSelected(f);
          }}
        >
          <Panel>
            <PanelHeader
              icon={<IconBook className="h-3.5 w-3.5" />}
              title="Ingested Sources"
              meta={<span className="font-mono text-[10px] text-ink-3">{sources.length}</span>}
            />
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-surface-border bg-surface-2/60 px-4 py-2 text-xs text-ink-3">
              <span>Drag and drop any file here or use the upload button above.</span>
              <div className="flex flex-wrap items-center gap-1.5 font-mono text-[10px]">
                <span className="rounded border border-surface-border bg-surface-1 px-1.5 py-0.5 text-indigo-300 font-medium">Word (.docx)</span>
                <span className="rounded border border-surface-border bg-surface-1 px-1.5 py-0.5 text-emerald-300 font-medium">Excel (.xlsx)</span>
                <span className="rounded border border-surface-border bg-surface-1 px-1.5 py-0.5 text-ink-2">CSV (.csv)</span>
                <span className="rounded border border-surface-border bg-surface-1 px-1.5 py-0.5 text-sky-300">PDF (.pdf)</span>
                <span className="rounded border border-surface-border bg-surface-1 px-1.5 py-0.5 text-ink-2">Images (.png, .jpg)</span>
              </div>
            </div>
          <PanelBody className="p-0">
            {loading ? (
              <LoadingState />
            ) : error ? (
              <ErrorState message={error} />
            ) : sources.length === 0 ? (
              <EmptyState
                icon={<IconBook className="h-6 w-6" />}
                title="No documents ingested"
                description="Upload an operational spreadsheet (XLSX/XLS/CSV), PDF manual, or inspection photo (PNG/JPEG) to begin."
              />
            ) : (
              <ul className="divide-y divide-surface-border">
                {sources.map((source) => (
                  <li key={source.id} className="flex items-center gap-3 px-4 py-3">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-ink-1">{source.name}</p>
                      <p className="truncate font-mono text-[10px] text-ink-3">
                        {source.original_filename ?? source.source_type} · {source.chunk_count} chunks ·{" "}
                        {formatRelativeTime(source.created_at)}
                      </p>
                    </div>
                    <Badge tone={processingStatusTone(source.processing_status)}>{source.processing_status}</Badge>
                    <button
                      type="button"
                      onClick={() => setPendingDelete(source)}
                      className="rounded p-1.5 text-ink-3 hover:bg-status-error/10 hover:text-status-error"
                      aria-label={`Delete ${source.name}`}
                    >
                      <IconTrash className="h-4 w-4" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </PanelBody>
          </Panel>
        </div>
      )}

      <ConfirmDialog
        open={!!pendingDelete}
        title="Delete knowledge source"
        description={
          <>
            This permanently removes <strong className="text-ink-1">{pendingDelete?.name}</strong> and its
            indexed chunks from the vault. Agents that reference it will lose that retrieval context.
          </>
        }
        confirmLabel="Delete"
        danger
        loading={deleting}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}
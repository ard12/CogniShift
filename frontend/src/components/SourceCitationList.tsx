import { IconBook, IconFileText } from "@/components/ui/Icon";

interface CitationItem {
  raw: string;
  source: string;
  locator: string;
  modality: string;
}

function parseCitations(sourcesUsed?: string | null): CitationItem[] {
  if (!sourcesUsed) return [];
  const text = sourcesUsed.trim();
  if (!text) return [];

  const items: CitationItem[] = [];
  const regex = /\[([^\]]+)\]/g;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    const inner = match[1].trim();
    const parts = inner.split("|").map((p) => p.trim());
    if (parts.length === 1) {
      items.push({
        raw: match[0],
        source: parts[0],
        locator: "",
        modality: parts[0].toLowerCase().endsWith(".xlsx") ? "SPREADSHEET" : "DOCUMENT",
      });
    } else if (parts.length === 2) {
      items.push({
        raw: match[0],
        source: parts[0],
        locator: parts[1],
        modality: parts[0].toLowerCase().endsWith(".xlsx") ? "SPREADSHEET" : "DOCUMENT",
      });
    } else {
      items.push({
        raw: match[0],
        source: parts[0],
        locator: parts.slice(1, -1).join(" | "),
        modality: parts[parts.length - 1].toUpperCase(),
      });
    }
  }

  if (items.length === 0) {
    const rawParts = text.split(/[,\n]+/).map((s) => s.trim()).filter(Boolean);
    for (const p of rawParts) {
      items.push({
        raw: p,
        source: p,
        locator: "",
        modality: "SOURCE",
      });
    }
  }

  return items;
}

export function SourceCitationList({ sourcesUsed }: { sourcesUsed?: string | null }) {
  const citations = parseCitations(sourcesUsed);
  if (citations.length === 0) return null;

  const getModalityTone = (mod: string) => {
    switch (mod) {
      case "SPREADSHEET":
      case "XLSX":
        return "border-emerald-500/40 bg-emerald-500/10 text-emerald-300";
      case "PDF":
        return "border-sky-500/40 bg-sky-500/10 text-sky-300";
      case "DOCUMENT":
      case "DOCX":
      case "HYBRID":
        return "border-indigo-500/40 bg-indigo-500/10 text-indigo-300";
      case "TOPOLOGY":
      case "GRAPH":
        return "border-amber-500/40 bg-amber-500/10 text-amber-300";
      case "VISUAL":
      case "IMAGE":
        return "border-fuchsia-500/40 bg-fuchsia-500/10 text-fuchsia-300";
      default:
        return "border-surface-border bg-surface-2 text-ink-2";
    }
  };

  return (
    <div className="space-y-2 rounded-lg border border-surface-border bg-surface-2/40 p-3">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1.5 font-mono text-xs font-bold uppercase tracking-wider text-ink-1">
          <IconBook className="h-3.5 w-3.5 text-brand" />
          Grounded Citations ({citations.length})
        </span>
        <span className="font-mono text-[10px] text-ink-3">VERIFIED EVIDENCE SOURCES</span>
      </div>

      <div className="flex flex-wrap gap-2 pt-1">
        {citations.map((cite, idx) => {
          const toneClasses = getModalityTone(cite.modality);
          return (
            <div
              key={idx}
              className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-mono shadow-sm transition hover:brightness-110 ${toneClasses}`}
              title={cite.raw}
            >
              <IconFileText className="h-3 w-3 shrink-0 opacity-70" />
              <span className="font-semibold text-ink-1">{cite.source}</span>
              {cite.locator && (
                <>
                  <span className="opacity-40">·</span>
                  <span className="text-[11px] font-medium opacity-90">{cite.locator}</span>
                </>
              )}
              {cite.modality && (
                <span className="ml-1 rounded bg-black/30 px-1 py-0.2 text-[9px] font-bold uppercase tracking-wider">
                  {cite.modality}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

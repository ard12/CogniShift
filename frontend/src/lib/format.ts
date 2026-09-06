export function formatRelativeTime(iso?: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";

  const diffMs = date.getTime() - Date.now();
  const diffSec = Math.round(diffMs / 1000);
  const abs = Math.abs(diffSec);

  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["year", 31536000],
    ["month", 2592000],
    ["week", 604800],
    ["day", 86400],
    ["hour", 3600],
    ["minute", 60],
    ["second", 1],
  ];

  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  for (const [unit, secondsInUnit] of units) {
    if (abs >= secondsInUnit || unit === "second") {
      const value = Math.round(diffSec / secondsInUnit);
      return rtf.format(value, unit);
    }
  }
  return "just now";
}

export function formatDateTime(iso?: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function formatBytes(bytes?: number | null): string {
  if (bytes === undefined || bytes === null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex++;
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[unitIndex]}`;
}

export type Tone = "neutral" | "info" | "success" | "warning" | "danger";

/** Run statuses are free-text on the backend; these are the ones the engine emits. */
export function runStatusTone(status: string): Tone {
  switch (status) {
    case "completed":
      return "success";
    case "paused":
      return "warning";
    case "failed":
      return "danger";
    case "running":
    case "resuming":
      return "info";
    default:
      return "neutral";
  }
}

export function runStatusLabel(status: string): string {
  switch (status) {
    case "paused":
      return "Awaiting approval";
    case "resuming":
      return "Resuming";
    default:
      return status.charAt(0).toUpperCase() + status.slice(1);
  }
}

export function approvalStatusTone(status: string): Tone {
  switch (status) {
    case "approved":
      return "success";
    case "rejected":
      return "danger";
    case "pending":
      return "warning";
    default:
      return "neutral";
  }
}

export function processingStatusTone(status: string): Tone {
  switch (status) {
    case "completed":
    case "ready":
      return "success";
    case "processing":
    case "pending":
      return "info";
    case "deleting":
      return "warning";
    case "failed":
    case "deletion_failed":
      return "danger";
    default:
      return "neutral";
  }
}

export function riskLevelTone(riskLevel?: string | null): Tone {
  switch (riskLevel) {
    case "read_only":
    case "low_risk":
      return "success";
    case "sensitive":
      return "warning";
    case "service_interrupting":
      return "danger";
    default:
      return "neutral";
  }
}

export function titleCase(value: string): string {
  return value
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

/** Safely pretty-prints a JSON string the backend stores as free text (parameters, structured_data, metadata). */
export function prettyJson(value?: string | null): string | null {
  if (!value) return null;
  try {
    return JSON.stringify(JSON.parse(value), null, 2);
  } catch {
    return value;
  }
}

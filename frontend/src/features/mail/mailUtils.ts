export function getSeverityBadge(sev: string) {
  switch (sev.toUpperCase()) {
    case "CRITICAL":
      return "bg-status-error/15 text-status-error border border-status-error/30";
    case "HIGH":
      return "bg-orange-500/15 text-orange-400 border border-orange-500/30";
    case "MEDIUM":
      return "bg-status-warning/15 text-status-warning border border-status-warning/30";
    case "LOW":
    default:
      return "bg-blue-500/15 text-blue-400 border border-blue-500/30";
  }
}

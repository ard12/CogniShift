import { cn } from "@/lib/cn";
type Tone = "neutral" | "info" | "success" | "warning" | "danger";

const DOT_CLASSES: Record<Tone, string> = {
  neutral: "bg-ink-3",
  info: "bg-brand",
  success: "bg-status-success",
  warning: "bg-status-warning",
  danger: "bg-status-error",
};

export function StatusBeacon({
  tone,
  label,
  pulse = true,
  className,
}: {
  tone: Tone;
  label: string;
  pulse?: boolean;
  className?: string;
}) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-[11px] font-mono", className)}>
      <span
        className={cn("h-1.5 w-1.5 shrink-0 rounded-full", DOT_CLASSES[tone], pulse && "beacon-active")}
        aria-hidden="true"
      />
      {label}
    </span>
  );
}
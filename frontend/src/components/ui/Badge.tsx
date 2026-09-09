import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

type Tone = "neutral" | "info" | "success" | "warning" | "danger";

const TONE_CLASSES: Record<Tone, string> = {
  neutral: "bg-surface-3 text-ink-2 border-surface-border",
  info: "bg-brand/10 text-brand border-brand/30",
  success: "bg-status-success/10 text-status-success border-status-success/30",
  warning: "bg-status-warning/10 text-status-warning border-status-warning/30",
  danger: "bg-status-error/10 text-status-error border-status-error/30",
};

export function Badge({
  tone = "neutral",
  children,
  pulse = false,
  className,
}: {
  tone?: Tone;
  children: ReactNode;
  pulse?: boolean;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "badge-shine inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-[11px] font-mono font-semibold uppercase tracking-wide",

        TONE_CLASSES[tone],
        className
      )}
    >
      {pulse && (
        <span className={cn("h-1.5 w-1.5 rounded-full bg-current", "beacon-active")} aria-hidden="true" />
      )}
      {children}
    </span>
  );
}
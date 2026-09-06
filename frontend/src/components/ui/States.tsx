import type { ReactNode } from "react";
import { IconAlertTriangle, IconLoader } from "./Icon";

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-10 text-sm text-ink-3">
      <IconLoader className="h-5 w-5" />
      <span>{label}</span>
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">
      {icon && <div className="mb-1 text-ink-3">{icon}</div>}
      <p className="text-sm font-medium text-ink-2">{title}</p>
      {description && <p className="max-w-sm text-xs text-ink-3">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong",
  message,
  action,
}: {
  title?: string;
  message: string;
  action?: ReactNode;
}) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center gap-2 rounded border border-status-error/30 bg-status-error/5 px-4 py-8 text-center"
    >
      <IconAlertTriangle className="h-5 w-5 text-status-error" />
      <p className="text-sm font-semibold text-status-error">{title}</p>
      <p className="max-w-md text-xs text-ink-2">{message}</p>
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function InlineError({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded border border-status-error/30 bg-status-error/5 px-3 py-2 text-xs text-status-error"
    >
      <IconAlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
      <span>{message}</span>
    </div>
  );
}
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export function Panel({
  children,
  className,
  padded = false,
}: {
  children: ReactNode;
  className?: string;
  padded?: boolean;
}) {
  return <div className={cn("panel flex flex-col overflow-hidden", padded && "p-4", className)}>{children}</div>;
}

export function PanelHeader({
  icon,
  title,
  meta,
  action,
}: {
  icon?: ReactNode;
  title: ReactNode;
  meta?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex h-10 shrink-0 items-center justify-between border-b border-surface-border bg-surface-3/40 px-4">
      <div className="flex items-center gap-2 text-xs font-mono font-semibold uppercase tracking-wider text-ink-1">
        {icon && <span className="text-brand">{icon}</span>}
        <span>{title}</span>
        {meta}
      </div>
      {action}
    </div>
  );
}

export function PanelBody({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("flex-1 p-4", className)}>{children}</div>;
}
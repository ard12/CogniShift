import type { SelectHTMLAttributes } from "react";
import { cn } from "@/lib/cn";
import { IconChevronDown } from "./Icon";

interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, "className"> {
  className?: string;
}

export function Select({ className, children, ...rest }: SelectProps) {
  return (
    <div className={cn("relative", className)}>
      <select
        className="input w-full appearance-none pr-8 font-mono text-xs"
        {...rest}
      >
        {children}
      </select>
      <IconChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-3" />
    </div>
  );
}
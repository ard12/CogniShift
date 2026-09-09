import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";
import { IconLoader } from "./Icon";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "success";
type Size = "sm" | "md";

interface ButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className"> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: ReactNode;
  className?: string;
}

const SIZE_CLASSES: Record<Size, string> = {
  sm: "text-xs px-2.5 py-1",
  md: "text-sm px-3.5 py-2",
};

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  icon,
  disabled,
  children,
  className,
  ...rest
}: ButtonProps) {
  return (
    <button
      type="button"
      className={cn("btn", `btn-${variant}`, SIZE_CLASSES[size], className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? <IconLoader className="h-3.5 w-3.5" /> : icon}
      {children}
    </button>
  );
}
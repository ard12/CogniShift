import { NavLink } from "react-router-dom";
import { cn } from "@/lib/cn";
import {
  IconArchive,
  IconBook,
  IconBot,
  IconCpu,
  IconGauge,
  IconLayers,
  IconPlayCircle,
  IconShieldCheck,
  IconTerminal,
} from "@/components/ui/Icon";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard", icon: IconGauge },
  { to: "/operator", label: "Operator", icon: IconTerminal },
  { to: "/workspaces", label: "Workspaces", icon: IconLayers },
  { to: "/agents", label: "Agents", icon: IconBot },
  { to: "/knowledge", label: "Knowledge", icon: IconBook },
  { to: "/runs", label: "Runs", icon: IconPlayCircle },
  { to: "/approvals", label: "Approvals", icon: IconShieldCheck },
  { to: "/artifacts", label: "Artifacts", icon: IconArchive },
  { to: "/system", label: "System", icon: IconCpu },
];

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto p-2" aria-label="Primary">
      {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          onClick={onNavigate}
          className={({ isActive }) =>
            cn(
              "flex items-center gap-2.5 rounded px-3 py-2 text-xs font-mono font-medium uppercase tracking-wide transition-colors",
              isActive
                ? "bg-brand/10 text-brand"
                : "text-ink-2 hover:bg-surface-3 hover:text-ink-1"
            )
          }
        >
          <Icon className="h-4 w-4 shrink-0" />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}
import { NavLink } from "react-router-dom";
import { useAuth } from "@/auth/useAuth";
import { cn } from "@/lib/cn";
import {
  IconArchive,
  IconBook,
  IconBot,
  IconCpu,
  IconGauge,
  IconLayers,
  IconMail,
  IconPlayCircle,
  IconShieldCheck,
  IconTerminal,
} from "@/components/ui/Icon";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard", icon: IconGauge, roles: ["operator","supervisor","administrator"] },
  { to: "/operator", label: "Operator", icon: IconTerminal, roles: ["operator","supervisor","administrator"] },
  { to: "/workspaces", label: "Workspaces", icon: IconLayers, roles: ["supervisor","administrator"] },
  { to: "/agents", label: "Agents", icon: IconBot, roles: ["administrator"] },
  { to: "/knowledge", label: "Knowledge", icon: IconBook, roles: ["supervisor","administrator"] },
  { to: "/runs", label: "Runs", icon: IconPlayCircle, roles: ["operator","supervisor","administrator"] },
  { to: "/approvals", label: "Approvals", icon: IconShieldCheck, roles: ["supervisor","administrator"] },
  { to: "/mailbox", label: "Mailbox", icon: IconMail, roles: ["operator","supervisor","administrator"] },
  { to: "/artifacts", label: "Artifacts", icon: IconArchive, roles: ["operator","supervisor","administrator"] },
  { to: "/security", label: "Security", icon: IconShieldCheck, roles: ["operator","supervisor","administrator"] },
  { to: "/system", label: "System", icon: IconCpu, roles: ["administrator"] },
];

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { role } = useAuth();
  return (
    <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto p-2" aria-label="Primary">
      {NAV_ITEMS.filter((item) => role && item.roles.includes(role)).map(({ to, label, icon: Icon }) => (
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

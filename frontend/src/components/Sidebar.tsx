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
import type { UserRole } from "@/types";

interface NavGroup {
  title: string;
  items: {
    to: string;
    label: string;
    icon: typeof IconGauge;
    roles: UserRole[];
    badge?: string;
  }[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    title: "OPERATE",
    items: [
      { to: "/operator", label: "Operator", icon: IconTerminal, roles: ["operator", "supervisor", "administrator"] },
      { to: "/runs", label: "Runs & Traces", icon: IconPlayCircle, roles: ["operator", "supervisor", "administrator"] },
      { to: "/dashboard", label: "Plant Overview", icon: IconGauge, roles: ["operator", "supervisor", "administrator"] },
    ],
  },
  {
    title: "INTELLIGENCE",
    items: [
      { to: "/knowledge", label: "Knowledge Vault", icon: IconBook, roles: ["supervisor", "administrator"] },
      { to: "/agents", label: "Sovereign Agents", icon: IconBot, roles: ["administrator"] },
    ],
  },
  {
    title: "COMMUNICATION",
    items: [
      { to: "/mailbox", label: "Operations Mail", icon: IconMail, roles: ["operator", "supervisor", "administrator"] },
    ],
  },
  {
    title: "OUTPUT",
    items: [
      { to: "/artifacts", label: "Artifacts & Exports", icon: IconArchive, roles: ["operator", "supervisor", "administrator"] },
    ],
  },
  {
    title: "GOVERNANCE",
    items: [
      { to: "/approvals", label: "Approvals & Gates", icon: IconShieldCheck, roles: ["supervisor", "administrator"] },
      { to: "/security", label: "Sovereign Security", icon: IconShieldCheck, roles: ["operator", "supervisor", "administrator"] },
    ],
  },
  {
    title: "SYSTEM",
    items: [
      { to: "/workspaces", label: "Workspaces", icon: IconLayers, roles: ["supervisor", "administrator"] },
      { to: "/system", label: "System & Nodes", icon: IconCpu, roles: ["administrator"] },
    ],
  },
];

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { role } = useAuth();

  return (
    <nav className="flex flex-1 flex-col gap-3 overflow-y-auto p-2" aria-label="Primary">
      {NAV_GROUPS.map((group) => {
        const visibleItems = group.items.filter(
          (item) => role && item.roles.includes(role as UserRole)
        );
        if (visibleItems.length === 0) return null;

        return (
          <div key={group.title} className="flex flex-col gap-0.5">
            <div className="px-2.5 pt-1.5 pb-1 text-[9px] font-mono font-semibold tracking-wider text-ink-3/80 uppercase select-none">
              {group.title}
            </div>
            {visibleItems.map(({ to, label, icon: Icon, badge }) => (
              <NavLink
                key={to}
                to={to}
                onClick={onNavigate}
                className={({ isActive }) =>
                  cn(
                    "group relative flex items-center justify-between rounded px-2.5 py-1.5 text-xs font-mono font-medium tracking-wide transition-colors",
                    isActive
                      ? "bg-brand/10 text-brand font-semibold shadow-xs"
                      : "text-ink-2 hover:bg-surface-3 hover:text-ink-1"
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <div className="flex items-center gap-2.5">
                      {isActive && (
                        <span className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-r bg-brand" />
                      )}
                      <Icon
                        className={cn(
                          "h-3.5 w-3.5 shrink-0 transition-colors",
                          isActive ? "text-brand" : "text-ink-3 group-hover:text-ink-1"
                        )}
                      />
                      <span>{label}</span>
                    </div>
                    {badge && (
                      <span className="rounded bg-brand/15 px-1 py-0.2 font-mono text-[9px] text-brand">
                        {badge}
                      </span>
                    )}
                  </>
                )}
              </NavLink>
            ))}
          </div>
        );
      })}
    </nav>
  );
}


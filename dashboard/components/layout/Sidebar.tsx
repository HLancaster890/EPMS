"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/store";
import { useTheme } from "./ThemeProvider";
import { ThemeSwitcher } from "@/components/ui/ThemeSwitcher";

const allNavItems = [
  { href: "/", label: "Dashboard", icon: "◉", minRole: "employee" },
  { href: "/executive/", label: "Executive", icon: "◈", minRole: "manager" },
  { href: "/inventory/", label: "Inventory", icon: "⊞", minRole: "manager" },
  { href: "/health/", label: "Health", icon: "♡", minRole: "manager" },
  { href: "/devices/", label: "Devices", icon: "⊡", minRole: "employee" },
  { href: "/activity/", label: "Activity", icon: "↻", minRole: "employee" },
  { href: "/browsers/", label: "Browsers", icon: "◎", minRole: "employee" },
  { href: "/editors/", label: "Editors", icon: "⌨", minRole: "employee" },
  { href: "/productivity/", label: "Productivity", icon: "▲", minRole: "employee" },
  { href: "/team/", label: "Team", icon: "👥", minRole: "manager" },
  { href: "/users/", label: "Users", icon: "👤", minRole: "manager" },
  { href: "/rules/", label: "Rules", icon: "⚙", minRole: "manager" },
  { href: "/alerts/", label: "Alerts", icon: "⚠", minRole: "employee" },
  { href: "/reports/", label: "Reports", icon: "▤", minRole: "employee" },
  { href: "/org/", label: "Organization", icon: "🏢", minRole: "admin" },
  { href: "/settings/", label: "Settings", icon: "⚙", minRole: "employee" },
];

const roleRank: Record<string, number> = {
  employee: 0, manager: 1, admin: 2, super_admin: 3,
};

export default function Sidebar() {
  const pathname = usePathname();
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);
  const { theme } = useTheme();
  const userRank = roleRank[user?.role || "employee"];

  const visibleItems = allNavItems.filter(
    (item) => (roleRank[item.minRole] || 0) <= userRank
  );

  return (
    <aside className="w-60 bg-sidebar text-white flex flex-col flex-shrink-0 border-r border-white/5">
      <div className="px-5 py-4 border-b border-white/5">
        <h1 className="text-lg font-bold tracking-tight">
          <span className="gradient-text">EPMS</span>
        </h1>
        <p className="text-xs text-white/30 mt-0.5">Enterprise PM</p>
      </div>

      <nav className="flex-1 py-2 overflow-y-auto space-y-0.5 px-2">
        {visibleItems.map((item) => {
          const fullHref = item.href === "/" ? "/dashboard/" : `/dashboard${item.href}`;
          const active = pathname === fullHref || (item.href !== "/" && pathname.startsWith(fullHref));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2.5 text-sm rounded-lg transition-all duration-200 ${
                active
                  ? "bg-sidebar-active/20 text-white font-medium"
                  : "text-white/50 hover:text-white hover:bg-sidebar-hover"
              }`}
            >
              <span className="w-5 text-center text-base">{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-white/5 px-3 py-3 space-y-2">
        <ThemeSwitcher minimal />
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-white/30">Role:</span>
          <span className="text-[10px] text-white/50 font-medium capitalize">{user?.role}</span>
        </div>
        <p className="text-[10px] text-white/30 truncate">{user?.email}</p>
        <button
          onClick={logout}
          className="text-[10px] text-white/30 hover:text-danger transition-colors"
        >
          Sign out
        </button>
      </div>
    </aside>
  );
}

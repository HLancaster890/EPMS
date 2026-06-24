"use client";

import { usePathname } from "next/navigation";
import { useTheme } from "./ThemeProvider";

const pageTitles: Record<string, string> = {
  "/dashboard/": "Dashboard",
  "/dashboard/devices/": "Devices",
  "/dashboard/activity/": "Activity Timeline",
  "/dashboard/browsers/": "Browser Usage",
  "/dashboard/editors/": "Editor Usage",
  "/dashboard/productivity/": "Productivity Analytics",
  "/dashboard/team/": "Team Overview",
  "/dashboard/users/": "Users",
  "/dashboard/rules/": "Productivity Rules",
  "/dashboard/alerts/": "Alerts",
  "/dashboard/reports/": "Reports",
  "/dashboard/org/": "Organization",
  "/dashboard/settings/": "Settings",
  "/dashboard/executive/": "Executive Overview",
  "/dashboard/inventory/": "Node Inventory",
  "/dashboard/health/": "Device Health",
  "/dashboard/nodes/": "Node Details",
};

export default function Header() {
  const pathname = usePathname();
  const { theme } = useTheme();
  const title = pageTitles[pathname] || "EPMS";

  return (
    <header className="h-14 bg-card border-b border-border flex items-center justify-between px-6 flex-shrink-0">
      <h2 className="text-lg font-semibold text-foreground">{title}</h2>
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 text-xs text-muted">
          <span className="w-2 h-2 rounded-full bg-success animate-pulse" />
          <span>All systems normal</span>
        </div>
      </div>
    </header>
  );
}

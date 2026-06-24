"use client";

import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/store";
import { Providers } from "@/lib/providers";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import { Card } from "@/components/ui/Card";
import { GlassCard } from "@/components/ui/GlassCard";
import { ThemeSwitcher } from "@/components/ui/ThemeSwitcher";
import { useTheme } from "@/components/layout/ThemeProvider";

function SettingsContent() {
  const router = useRouter();
  const user = useAuth((s) => s.user);
  const isAuthenticated = useAuth((s) => s.isAuthenticated);
  const { theme, themeId, setTheme } = useTheme();

  if (!isAuthenticated) {
    router.push("/login/");
    return null;
  }

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          <div>
            <h3 className="text-lg font-semibold text-foreground">Settings</h3>
            <p className="text-sm text-muted mt-0.5">Profile, preferences, and system configuration</p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card title="Profile">
              <div className="space-y-4">
                <GlassCard>
                  <p className="text-[10px] text-muted uppercase tracking-wider">Email</p>
                  <p className="text-sm text-foreground mt-0.5">{user?.email ?? "-"}</p>
                </GlassCard>
                <GlassCard>
                  <p className="text-[10px] text-muted uppercase tracking-wider">Role</p>
                  <p className="text-sm text-foreground mt-0.5 capitalize">{user?.role ?? "-"}</p>
                </GlassCard>
                <GlassCard>
                  <p className="text-[10px] text-muted uppercase tracking-wider">Organization ID</p>
                  <p className="text-sm text-foreground mt-0.5 font-mono text-xs">{user?.organization_id ?? "-"}</p>
                </GlassCard>
              </div>
            </Card>

            <Card title="Theme & Appearance">
              <div className="space-y-4">
                <p className="text-xs text-muted">Choose from 8 professionally designed themes to match your preference.</p>
                <ThemeSwitcher />
                <div className="mt-4">
                  <p className="text-xs text-muted mb-2">Currently active:</p>
                  <GlassCard>
                    <div className="flex items-center gap-3">
                      <span
                        className="w-6 h-6 rounded-full"
                        style={{ background: `linear-gradient(135deg, ${theme.colors.primary}, ${theme.colors.accent})` }}
                      />
                      <div>
                        <p className="text-sm font-medium text-foreground">{theme.name}</p>
                        <p className="text-xs text-muted">{theme.description}</p>
                      </div>
                      <span className="ml-auto text-xs text-muted capitalize bg-card-border/50 px-2 py-0.5 rounded-full">
                        {theme.mode}
                      </span>
                    </div>
                  </GlassCard>
                </div>
              </div>
            </Card>

            <Card title="API Configuration">
              <div className="space-y-4">
                <GlassCard>
                  <p className="text-[10px] text-muted uppercase tracking-wider">API Base URL</p>
                  <p className="text-sm text-foreground mt-0.5 font-mono">/api/v1</p>
                </GlassCard>
                <GlassCard>
                  <p className="text-[10px] text-muted uppercase tracking-wider">Data Refresh</p>
                  <p className="text-sm text-foreground mt-0.5">Every 30 seconds</p>
                </GlassCard>
              </div>
            </Card>

            <Card title="System Info">
              <div className="space-y-4">
                <GlassCard>
                  <p className="text-[10px] text-muted uppercase tracking-wider">Dashboard Version</p>
                  <p className="text-sm text-foreground mt-0.5">v4.5.0</p>
                </GlassCard>
                <GlassCard>
                  <p className="text-[10px] text-muted uppercase tracking-wider">Build Target</p>
                  <p className="text-sm text-foreground mt-0.5">Static Export (Next.js)</p>
                </GlassCard>
              </div>
            </Card>
          </div>
        </main>
      </div>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <Providers>
      <SettingsContent />
    </Providers>
  );
}

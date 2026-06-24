"use client";

import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/store";
import { Providers } from "@/lib/providers";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import { Card } from "@/components/ui/Card";
import { StatCard } from "@/components/ui/StatCard";
import { GlassCard } from "@/components/ui/GlassCard";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";

function OrgContent() {
  const router = useRouter();
  const isAuthenticated = useAuth((s) => s.isAuthenticated);

  const { data: orgData, isLoading } = useQuery({
    queryKey: ["organizations"],
    queryFn: () => api.organizations.list(),
    enabled: isAuthenticated,
  });

  const { data: teamData } = useQuery({
    queryKey: ["teams"],
    queryFn: () => api.teams.list(),
    enabled: isAuthenticated,
  });

  const { data: userData } = useQuery({
    queryKey: ["users"],
    queryFn: () => api.users.list(),
    enabled: isAuthenticated,
  });

  if (!isAuthenticated) {
    router.push("/login/");
    return null;
  }

  if (isLoading) return <LoadingSpinner />;

  const orgs = orgData?.organizations ?? [];
  const teams = teamData?.teams ?? [];
  const users = userData?.users ?? [];
  const totalTeams = teams.length;
  const totalUsers = users.length;
  const totalDevices = orgs.reduce((s, o) => s + (o.device_count || 0), 0);

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <StatCard label="Organizations" value={orgs.length} icon="🏢" variant="glass" />
            <StatCard label="Teams" value={totalTeams} icon="👥" variant="glass" />
            <StatCard label="Total Users" value={totalUsers} icon="👤" variant="glass" />
            <StatCard label="Total Devices" value={totalDevices} icon="⊞" variant="glass" />
          </div>

          {orgs.length > 0 ? (
            <div className="space-y-4">
              {orgs.map((org) => (
                <Card key={org.id} title={org.name || org.domain}>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <GlassCard>
                      <p className="text-[10px] text-muted uppercase tracking-wider">Domain</p>
                      <p className="text-sm font-medium text-foreground mt-0.5">{org.domain}</p>
                    </GlassCard>
                    <GlassCard>
                      <p className="text-[10px] text-muted uppercase tracking-wider">Teams</p>
                      <p className="text-sm font-medium text-foreground mt-0.5">{org.team_count ?? teams.length}</p>
                    </GlassCard>
                    <GlassCard>
                      <p className="text-[10px] text-muted uppercase tracking-wider">Devices</p>
                      <p className="text-sm font-medium text-foreground mt-0.5">{org.device_count ?? "-"}</p>
                    </GlassCard>
                  </div>
                </Card>
              ))}
            </div>
          ) : (
            <Card>
              <p className="text-muted text-sm text-center py-8">No organizations found</p>
            </Card>
          )}
        </main>
      </div>
    </div>
  );
}

export default function OrgPage() {
  return (
    <Providers>
      <OrgContent />
    </Providers>
  );
}

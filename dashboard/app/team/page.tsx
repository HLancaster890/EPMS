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

function TeamContent() {
  const router = useRouter();
  const isAuthenticated = useAuth((s) => s.isAuthenticated);

  const { data, isLoading } = useQuery({
    queryKey: ["teams"],
    queryFn: () => api.teams.list(),
    enabled: isAuthenticated,
  });

  if (!isAuthenticated) {
    router.push("/login/");
    return null;
  }

  if (isLoading) return <LoadingSpinner />;

  const teams = data?.teams ?? [];

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <StatCard label="Total Teams" value={teams.length} icon="👥" variant="glass" />
            <StatCard label="Teams" value={teams.filter((t) => t.name).length} icon="✓" color="text-success" variant="glass" />
          </div>

          <Card title="Team Overview">
            {teams.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {teams.map((team) => (
                  <GlassCard key={team.id} hover>
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="text-sm font-semibold text-foreground">{team.name}</p>
                        {team.description && (
                          <p className="text-xs text-muted mt-1">{team.description}</p>
                        )}
                        <div className="flex gap-3 mt-3">
                          <div className="text-xs text-muted">
                            <span className="text-foreground font-medium">{team.member_count ?? "-"}</span> members
                          </div>
                          <div className="text-xs text-muted">
                            <span className="text-foreground font-medium">{team.device_count ?? "-"}</span> devices
                          </div>
                        </div>
                      </div>
                    </div>
                  </GlassCard>
                ))}
              </div>
            ) : (
              <p className="text-muted text-sm text-center py-8">No teams found</p>
            )}
          </Card>
        </main>
      </div>
    </div>
  );
}

export default function TeamPage() {
  return (
    <Providers>
      <TeamContent />
    </Providers>
  );
}

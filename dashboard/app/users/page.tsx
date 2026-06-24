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
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { Badge } from "@/components/ui/Badge";

function UsersContent() {
  const router = useRouter();
  const isAuthenticated = useAuth((s) => s.isAuthenticated);

  const { data, isLoading } = useQuery({
    queryKey: ["users"],
    queryFn: () => api.users.list(),
    enabled: isAuthenticated,
  });

  if (!isAuthenticated) {
    router.push("/login/");
    return null;
  }

  if (isLoading) return <LoadingSpinner />;

  const users = data?.users ?? [];

  const activeUsers = users.filter((u) => u.is_active).length;

  const roleCounts: Record<string, number> = {};
  users.forEach((u) => {
    roleCounts[u.role] = (roleCounts[u.role] || 0) + 1;
  });

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <StatCard label="Total Users" value={users.length} icon="👤" variant="glass" />
            <StatCard label="Active" value={activeUsers} icon="●" color="text-success" variant="glass" />
            <StatCard label="Inactive" value={users.length - activeUsers} icon="○" color="text-muted" variant="glass" />
          </div>

          <Card title={`Users (${users.length})`}>
            {users.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-muted uppercase tracking-wider border-b border-border">
                      <th className="text-left py-3 px-2 font-medium">Email</th>
                      <th className="text-left py-3 px-2 font-medium">Display Name</th>
                      <th className="text-left py-3 px-2 font-medium">Role</th>
                      <th className="text-center py-3 px-2 font-medium">Status</th>
                      <th className="text-left py-3 px-2 font-medium">Last Login</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((u) => (
                      <tr key={u.id} className="border-b border-border/50 hover:bg-table-row-hover transition-colors">
                        <td className="py-3 px-2 text-foreground">{u.email}</td>
                        <td className="py-3 px-2 text-muted">{u.display_name || "-"}</td>
                        <td className="py-3 px-2">
                          <Badge variant={u.role === "admin" || u.role === "super_admin" ? "productive" : u.role === "manager" ? "neutral" : "info"}>
                            {u.role}
                          </Badge>
                        </td>
                        <td className="py-3 px-2 text-center">
                          <Badge variant={u.is_active ? "online" : "offline"}>
                            {u.is_active ? "Active" : "Inactive"}
                          </Badge>
                        </td>
                        <td className="py-3 px-2 text-xs text-muted">
                          {u.last_login ? new Date(u.last_login).toLocaleDateString() : "Never"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-muted text-sm text-center py-8">No users found</p>
            )}
          </Card>
        </main>
      </div>
    </div>
  );
}

export default function UsersPage() {
  return (
    <Providers>
      <UsersContent />
    </Providers>
  );
}

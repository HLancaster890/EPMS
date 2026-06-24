"use client";

import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/store";
import { Providers } from "@/lib/providers";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import { Card } from "@/components/ui/Card";
import { StatCard } from "@/components/ui/StatCard";
import { GlassCard } from "@/components/ui/GlassCard";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { Badge } from "@/components/ui/Badge";

function RulesContent() {
  const router = useRouter();
  const isAuthenticated = useAuth((s) => s.isAuthenticated);
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [pattern, setPattern] = useState("");
  const [category, setCategory] = useState<"productive" | "neutral" | "distracting">("productive");
  const [ruleType, setRuleType] = useState<"glob" | "regex" | "exact">("glob");
  const [description, setDescription] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["rules"],
    queryFn: () => api.rules.list(),
    enabled: isAuthenticated,
  });

  const createMutation = useMutation({
    mutationFn: () => api.rules.create({ pattern, category, rule_type: ruleType, description }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rules"] });
      setShowCreate(false);
      setPattern("");
      setDescription("");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.rules.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["rules"] }),
  });

  if (!isAuthenticated) {
    router.push("/login/");
    return null;
  }

  if (isLoading) return <LoadingSpinner />;

  const rules = data?.rules ?? [];

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-foreground">Productivity Rules</h3>
              <p className="text-sm text-muted mt-0.5">Define patterns to categorize applications as productive, neutral, or distracting</p>
            </div>
            <button
              onClick={() => setShowCreate(!showCreate)}
              className="px-4 py-2 rounded-lg bg-primary text-white text-sm font-medium hover:bg-primary-hover transition-colors"
            >
              {showCreate ? "Cancel" : "+ New Rule"}
            </button>
          </div>

          {showCreate && (
            <Card title="Create Rule">
              <div className="space-y-4">
                <input
                  type="text"
                  placeholder="Pattern (e.g., *.py, *.code., slack.com*)"
                  value={pattern}
                  onChange={(e) => setPattern(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-input-bg border border-input-border text-foreground placeholder:text-muted text-sm focus:outline-none focus:border-primary"
                />
                <div className="flex gap-4">
                  <div className="flex-1">
                    <p className="text-xs text-muted mb-1 font-medium">Category</p>
                    <div className="flex gap-2">
                      {(["productive", "neutral", "distracting"] as const).map((c) => (
                        <button
                          key={c}
                          onClick={() => setCategory(c)}
                          className={`px-3 py-1.5 rounded-lg text-xs transition-colors ${
                            category === c
                              ? c === "productive" ? "bg-success/20 text-success" :
                                c === "neutral" ? "bg-primary/20 text-primary" : "bg-danger/20 text-danger"
                              : "bg-card-border/50 text-muted hover:bg-table-row-hover"
                          }`}
                        >
                          {c}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="flex-1">
                    <p className="text-xs text-muted mb-1 font-medium">Type</p>
                    <div className="flex gap-2">
                      {(["glob", "regex", "exact"] as const).map((t) => (
                        <button
                          key={t}
                          onClick={() => setRuleType(t)}
                          className={`px-3 py-1.5 rounded-lg text-xs transition-colors ${
                            ruleType === t
                              ? "bg-primary text-white"
                              : "bg-card-border/50 text-muted hover:bg-table-row-hover"
                          }`}
                        >
                          {t}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
                <input
                  type="text"
                  placeholder="Description (optional)"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-input-bg border border-input-border text-foreground placeholder:text-muted text-sm focus:outline-none focus:border-primary"
                />
                <button
                  onClick={() => createMutation.mutate()}
                  disabled={!pattern || createMutation.isPending}
                  className="w-full py-2 rounded-lg bg-primary text-white text-sm font-medium hover:bg-primary-hover disabled:opacity-50 transition-colors"
                >
                  {createMutation.isPending ? "Creating..." : "Create Rule"}
                </button>
              </div>
            </Card>
          )}

          <Card title={`Rules (${rules.length})`}>
            {rules.length > 0 ? (
              <div className="space-y-2">
                {rules.map((rule) => (
                  <GlassCard key={rule.id}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <Badge variant={rule.category}>{rule.category}</Badge>
                        <div>
                          <p className="text-sm font-mono font-medium text-foreground">{rule.pattern}</p>
                          <p className="text-[10px] text-muted flex items-center gap-2">
                            <span>{rule.rule_type}</span>
                            {rule.description && <span>· {rule.description}</span>}
                            <span>· {rule.is_active ? "Active" : "Inactive"}</span>
                          </p>
                        </div>
                      </div>
                      <button
                        onClick={() => deleteMutation.mutate(rule.id)}
                        className="text-xs text-danger hover:text-danger/80 px-2 py-1 rounded border border-card-border hover:bg-danger/10 transition-colors"
                      >
                        Delete
                      </button>
                    </div>
                  </GlassCard>
                ))}
              </div>
            ) : (
              <p className="text-muted text-sm text-center py-8">No rules defined</p>
            )}
          </Card>
        </main>
      </div>
    </div>
  );
}

export default function RulesPage() {
  return (
    <Providers>
      <RulesContent />
    </Providers>
  );
}

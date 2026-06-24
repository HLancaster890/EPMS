"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/store";
import { ThemeProvider } from "@/components/layout/ThemeProvider";

function LoginForm() {
  const [email, setEmail] = useState("admin@corp.local");
  const [password, setPassword] = useState("MyP@ss1");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const isAuthenticated = useAuth((s) => s.isAuthenticated);
  const login = useAuth((s) => s.login);

  useEffect(() => {
    if (isAuthenticated) router.push("/");
  }, [isAuthenticated, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await api.auth.login(email, password);
      login(res.user, res.access_token);
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold tracking-tight text-foreground">EPMS</h1>
          <p className="text-muted text-sm mt-1">
            Enterprise Productivity Management
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="bg-card border border-card-border rounded-2xl p-6"
        >
          <h2 className="text-lg font-semibold text-foreground mb-5">Sign in</h2>

          {error && (
            <div className="mb-4 p-3 rounded-lg bg-danger/10 border border-danger/20 text-sm text-danger">
              {error}
            </div>
          )}

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-input-bg border border-input-border text-foreground placeholder:text-muted text-sm focus:outline-none focus:border-primary"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-input-bg border border-input-border text-foreground placeholder:text-muted text-sm focus:outline-none focus:border-primary"
                required
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 bg-primary hover:bg-primary-hover text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
            >
              {loading ? "Signing in..." : "Sign in"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <ThemeProvider>
      <LoginForm />
    </ThemeProvider>
  );
}

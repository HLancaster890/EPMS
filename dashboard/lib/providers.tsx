"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, useEffect, type ReactNode } from "react";
import { useAuth } from "./store";
import { ThemeProvider } from "@/components/layout/ThemeProvider";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchInterval: 30000,
      retry: 1,
      staleTime: 10000,
    },
  },
});

export function Providers({ children }: { children: ReactNode }) {
  const hydrate = useAuth((s) => s.hydrate);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    hydrate();
    setHydrated(true);
  }, [hydrate]);

  if (!hydrated) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <div className="flex flex-col items-center gap-3">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-primary border-t-transparent" />
          <p className="text-sm text-muted">Loading EPMS...</p>
        </div>
      </div>
    );
  }

  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </ThemeProvider>
  );
}

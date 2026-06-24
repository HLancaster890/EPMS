# EPMS Dashboard

This is a Next.js static export (TypeScript + React + Tailwind + Chart.js + React Query).

## Structure
```
app/              # App Router pages
  login/          # Login form → POST /api/v1/auth/login
  dashboard/      # Main dashboard with stat cards + charts
  devices/        # Device management table
  activity/       # Activity timeline with category split
  browsers/       # Browser usage chart + table
  editors/        # Editor usage chart + table
  productivity/   # 30-day productivity trend + breakdown
  alerts/         # Alert management with acknowledge
  reports/        # Report generation + download
  settings/       # Profile + config info
components/
  layout/         # Sidebar, Header
  ui/             # Card, StatCard, Badge, LoadingSpinner
  charts/         # LineChart, BarChart, DoughnutChart
  features/       # ActivityTable, DeviceTable, AlertsPanel, ProductivityScore
lib/
  types.ts        # All TypeScript interfaces
  api.ts          # Typed API client (auto-auth from localStorage)
  store.ts        # Zustand auth store
  providers.tsx   # React Query provider + auth hydration
```

## Key patterns
- All pages use `"use client"` + `<Providers>` + auth guard pattern
- React Query auto-refetches every 30s
- `basePath: "/dashboard"` — pages are served at `/dashboard/login/`, etc.
- Static export — no SSR, all data fetched client-side

# EPMS Dashboard — Next.js Static Export

Modern React/TypeScript dashboard served by FastAPI at `/dashboard/`.

## Stack
- Next.js 16 (static export, `output: "export"`)
- React 19 + Tailwind v4 + Chart.js v4
- @tanstack/react-query (API data), zustand (auth state)

## Commands
```powershell
npm run dev          # Dev server on :3000
npm run build        # Static export to out/
```

## Deploy
After `npm run build`, copy `out/` contents to the FastAPI web-ui dir:
```powershell
Get-ChildItem out | Copy-Item -Destination "..\activitywatch_Source code\epms-server-installer\Resources\services\web-ui" -Recurse -Force
```

## API
- Auth: `POST /api/v1/auth/login` → JWT stored in localStorage
- All data: `/api/v1/dashboard/*`, `/api/v1/analytics/*`
- Charts: LineChart, BarChart, DoughnutChart wrappers in `components/charts/`
- Auth store: `lib/store.ts` (zustand), auto-redirects to `/dashboard/login/` on 401

## Security (server-side, enforced in API service)
- JWT tokens include `org_id` claim — dashboard endpoints filter by org
- All API calls require `Authorization: Bearer <token>` header
- See root `AGENTS.md` for full security env var requirements

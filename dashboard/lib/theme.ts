export interface ThemeColors {
  background: string;
  foreground: string;
  primary: string;
  primaryHover: string;
  sidebar: string;
  sidebarHover: string;
  sidebarActive: string;
  card: string;
  cardBorder: string;
  border: string;
  success: string;
  warning: string;
  danger: string;
  muted: string;
  accent: string;
  gradientFrom: string;
  gradientTo: string;
  chartLine: string;
  chartPoint: string;
  tableRowHover: string;
  inputBg: string;
  inputBorder: string;
}

export interface Theme {
  id: string;
  name: string;
  description: string;
  mode: "light" | "dark";
  colors: ThemeColors;
}

export const themes: Theme[] = [
  {
    id: "midnight-indigo",
    name: "Midnight Indigo",
    description: "Deep navy with vibrant indigo accents",
    mode: "dark",
    colors: {
      background: "#0f172a",
      foreground: "#e2e8f0",
      primary: "#6366f1",
      primaryHover: "#4f46e5",
      sidebar: "#0f1119",
      sidebarHover: "#1e293b",
      sidebarActive: "#6366f1",
      card: "#1e293b",
      cardBorder: "#334155",
      border: "#1e293b",
      success: "#22c55e",
      warning: "#eab308",
      danger: "#ef4444",
      muted: "#64748b",
      accent: "#818cf8",
      gradientFrom: "#6366f1",
      gradientTo: "#8b5cf6",
      chartLine: "#6366f1",
      chartPoint: "#818cf8",
      tableRowHover: "#334155",
      inputBg: "#0f172a",
      inputBorder: "#334155",
    },
  },
  {
    id: "emerald-city",
    name: "Emerald City",
    description: "Dark teal with emerald green highlights",
    mode: "dark",
    colors: {
      background: "#0d1f1a",
      foreground: "#e0f2e9",
      primary: "#10b981",
      primaryHover: "#059669",
      sidebar: "#081410",
      sidebarHover: "#134e3f",
      sidebarActive: "#10b981",
      card: "#134e3f",
      cardBorder: "#1a6b55",
      border: "#1a6b55",
      success: "#22c55e",
      warning: "#eab308",
      danger: "#ef4444",
      muted: "#6b8f7f",
      accent: "#34d399",
      gradientFrom: "#10b981",
      gradientTo: "#059669",
      chartLine: "#10b981",
      chartPoint: "#34d399",
      tableRowHover: "#1a6b55",
      inputBg: "#0d1f1a",
      inputBorder: "#1a6b55",
    },
  },
  {
    id: "sunset-ember",
    name: "Sunset Ember",
    description: "Warm dark with amber and orange glow",
    mode: "dark",
    colors: {
      background: "#1a1210",
      foreground: "#f5e6d3",
      primary: "#f59e0b",
      primaryHover: "#d97706",
      sidebar: "#140e0c",
      sidebarHover: "#292524",
      sidebarActive: "#f59e0b",
      card: "#292524",
      cardBorder: "#44403c",
      border: "#44403c",
      success: "#22c55e",
      warning: "#eab308",
      danger: "#ef4444",
      muted: "#a8a29e",
      accent: "#fbbf24",
      gradientFrom: "#f59e0b",
      gradientTo: "#ef4444",
      chartLine: "#f59e0b",
      chartPoint: "#fbbf24",
      tableRowHover: "#44403c",
      inputBg: "#1a1210",
      inputBorder: "#44403c",
    },
  },
  {
    id: "ocean-depths",
    name: "Ocean Depths",
    description: "Deep blue with cyan highlights",
    mode: "dark",
    colors: {
      background: "#0c1929",
      foreground: "#dbeafe",
      primary: "#0ea5e9",
      primaryHover: "#0284c7",
      sidebar: "#081220",
      sidebarHover: "#0c4a6e",
      sidebarActive: "#0ea5e9",
      card: "#0c4a6e",
      cardBorder: "#155e75",
      border: "#155e75",
      success: "#22c55e",
      warning: "#eab308",
      danger: "#ef4444",
      muted: "#5b8ba8",
      accent: "#38bdf8",
      gradientFrom: "#0ea5e9",
      gradientTo: "#06b6d4",
      chartLine: "#0ea5e9",
      chartPoint: "#38bdf8",
      tableRowHover: "#155e75",
      inputBg: "#0c1929",
      inputBorder: "#155e75",
    },
  },
  {
    id: "royal-purple",
    name: "Royal Purple",
    description: "Rich violet and plum tones",
    mode: "dark",
    colors: {
      background: "#140b1e",
      foreground: "#ede9fe",
      primary: "#8b5cf6",
      primaryHover: "#7c3aed",
      sidebar: "#0f0718",
      sidebarHover: "#2e1065",
      sidebarActive: "#8b5cf6",
      card: "#2e1065",
      cardBorder: "#4c1d95",
      border: "#4c1d95",
      success: "#22c55e",
      warning: "#eab308",
      danger: "#ef4444",
      muted: "#7c6a9a",
      accent: "#a78bfa",
      gradientFrom: "#8b5cf6",
      gradientTo: "#6d28d9",
      chartLine: "#8b5cf6",
      chartPoint: "#a78bfa",
      tableRowHover: "#4c1d95",
      inputBg: "#140b1e",
      inputBorder: "#4c1d95",
    },
  },
  {
    id: "forest-canopy",
    name: "Forest Canopy",
    description: "Deep forest green with moss accents",
    mode: "dark",
    colors: {
      background: "#0f1a12",
      foreground: "#dcfce7",
      primary: "#22c55e",
      primaryHover: "#16a34a",
      sidebar: "#0a140d",
      sidebarHover: "#14532d",
      sidebarActive: "#22c55e",
      card: "#14532d",
      cardBorder: "#166534",
      border: "#166534",
      success: "#22c55e",
      warning: "#eab308",
      danger: "#ef4444",
      muted: "#6b8f72",
      accent: "#4ade80",
      gradientFrom: "#22c55e",
      gradientTo: "#16a34a",
      chartLine: "#22c55e",
      chartPoint: "#4ade80",
      tableRowHover: "#166534",
      inputBg: "#0f1a12",
      inputBorder: "#166534",
    },
  },
  {
    id: "arctic-frost",
    name: "Arctic Frost",
    description: "Crisp white with ice blue tones",
    mode: "light",
    colors: {
      background: "#ecfdf5",
      foreground: "#1e293b",
      primary: "#06b6d4",
      primaryHover: "#0891b2",
      sidebar: "#0f172a",
      sidebarHover: "#1e293b",
      sidebarActive: "#06b6d4",
      card: "#ffffff",
      cardBorder: "#e2e8f0",
      border: "#e2e8f0",
      success: "#10b981",
      warning: "#f59e0b",
      danger: "#ef4444",
      muted: "#94a3b8",
      accent: "#22d3ee",
      gradientFrom: "#06b6d4",
      gradientTo: "#67e8f9",
      chartLine: "#06b6d4",
      chartPoint: "#22d3ee",
      tableRowHover: "#f1f5f9",
      inputBg: "#ffffff",
      inputBorder: "#e2e8f0",
    },
  },
  {
    id: "graphite",
    name: "Graphite",
    description: "Professional light gray with slate accents",
    mode: "light",
    colors: {
      background: "#f1f5f9",
      foreground: "#0f172a",
      primary: "#64748b",
      primaryHover: "#475569",
      sidebar: "#1e293b",
      sidebarHover: "#334155",
      sidebarActive: "#64748b",
      card: "#ffffff",
      cardBorder: "#e2e8f0",
      border: "#e2e8f0",
      success: "#22c55e",
      warning: "#eab308",
      danger: "#ef4444",
      muted: "#94a3b8",
      accent: "#94a3b8",
      gradientFrom: "#64748b",
      gradientTo: "#94a3b8",
      chartLine: "#64748b",
      chartPoint: "#94a3b8",
      tableRowHover: "#f8fafc",
      inputBg: "#ffffff",
      inputBorder: "#e2e8f0",
    },
  },
];

export function getThemeById(id: string): Theme {
  return themes.find((t) => t.id === id) || themes[0];
}

export function getDefaultTheme(): Theme {
  return themes[0];
}

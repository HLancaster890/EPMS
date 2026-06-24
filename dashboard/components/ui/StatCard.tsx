import { GlassCard } from "./GlassCard";

export function StatCard({
  label,
  value,
  icon,
  trend,
  color = "text-foreground",
  variant = "default",
}: {
  label: string;
  value: string | number;
  icon: string;
  trend?: { value: string; positive: boolean };
  color?: string;
  variant?: "default" | "glass" | "gradient";
}) {
  if (variant === "glass") {
    return (
      <GlassCard>
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs text-muted font-medium">{label}</p>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
            {trend && (
              <p className={`text-xs mt-1 flex items-center gap-0.5 ${
                trend.positive ? "text-success" : "text-danger"
              }`}>
                <span>{trend.positive ? "↑" : "↓"}</span>
                <span>{trend.value}</span>
              </p>
            )}
          </div>
          <span className="text-xl opacity-50">{icon}</span>
        </div>
      </GlassCard>
    );
  }

  if (variant === "gradient") {
    return (
      <div className="rounded-2xl p-5 gradient-bg relative overflow-hidden">
        <div className="absolute inset-0 bg-black/10" />
        <div className="relative z-10">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs text-white/70 font-medium">{label}</p>
              <p className="text-2xl font-bold text-white mt-1">{value}</p>
              {trend && (
                <p className={`text-xs mt-1 flex items-center gap-0.5 ${
                  trend.positive ? "text-white/90" : "text-white/70"
                }`}>
                  <span>{trend.positive ? "↑" : "↓"}</span>
                  <span>{trend.value}</span>
                </p>
              )}
            </div>
            <span className="text-xl text-white/40">{icon}</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-card border border-card-border rounded-2xl p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs text-muted font-medium">{label}</p>
          <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
          {trend && (
            <p className={`text-xs mt-1 flex items-center gap-0.5 ${
              trend.positive ? "text-success" : "text-danger"
            }`}>
              <span>{trend.positive ? "↑" : "↓"}</span>
              <span>{trend.value}</span>
            </p>
          )}
        </div>
        <span className="text-xl text-muted/30">{icon}</span>
      </div>
    </div>
  );
}

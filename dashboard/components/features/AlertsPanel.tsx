import { Badge } from "@/components/ui/Badge";
import type { Alert } from "@/lib/types";

export function AlertsPanel({
  alerts,
  onAcknowledge,
}: {
  alerts: Alert[];
  onAcknowledge: (id: string) => void;
}) {
  if (!alerts.length) {
    return (
      <p className="text-zinc-400 text-sm py-8 text-center">No alerts</p>
    );
  }
  return (
    <div className="space-y-3">
      {alerts.map((a) => (
        <div
          key={a.id}
          className={`flex items-start gap-4 p-4 rounded-lg border ${
            a.acknowledged ? "opacity-50" : ""
          } ${severityBorder(a.severity)}`}
        >
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <Badge variant={a.severity}>{a.severity}</Badge>
              <Badge variant="info">{a.type}</Badge>
              {a.acknowledged && (
                <span className="text-xs text-zinc-400">Acknowledged</span>
              )}
            </div>
            <p className="text-sm">{a.message}</p>
            <p className="text-xs text-zinc-400 mt-1">
              {new Date(a.created_at).toLocaleString()} &middot; Agent:{" "}
              {a.agent_id}
            </p>
          </div>
          {!a.acknowledged && (
            <button
              onClick={() => onAcknowledge(a.id)}
              className="text-xs text-primary hover:text-primary-hover font-medium whitespace-nowrap mt-1"
            >
              Acknowledge
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

function severityBorder(s: string): string {
  switch (s) {
    case "critical":
      return "border-danger/20 bg-danger/5";
    case "warning":
      return "border-warning/20 bg-warning/5";
    default:
      return "border-border";
  }
}

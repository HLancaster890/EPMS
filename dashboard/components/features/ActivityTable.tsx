import { Badge } from "@/components/ui/Badge";
import type { ActivityEvent } from "@/lib/types";

export function ActivityTable({ events }: { events: ActivityEvent[] }) {
  if (!events.length) {
    return <p className="text-zinc-400 text-sm py-8 text-center">No activity data</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-zinc-400 border-b border-border">
            <th className="pb-3 font-medium">Time</th>
            <th className="pb-3 font-medium">App</th>
            <th className="pb-3 font-medium">Title</th>
            <th className="pb-3 font-medium">Category</th>
            <th className="pb-3 font-medium text-right">Duration</th>
          </tr>
        </thead>
        <tbody>
          {events.map((ev) => (
            <tr key={ev.id} className="border-b border-border/50">
              <td className="py-3 text-zinc-500">
                {new Date(ev.timestamp).toLocaleTimeString()}
              </td>
              <td className="py-3 font-medium">{ev.app}</td>
              <td className="py-3 text-zinc-600 max-w-xs truncate">
                {ev.title}
              </td>
              <td className="py-3">
                <Badge variant={ev.category}>{ev.category}</Badge>
              </td>
              <td className="py-3 text-right text-zinc-500">
                {formatDuration(ev.duration_seconds)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatDuration(s: number): string {
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`;
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
}

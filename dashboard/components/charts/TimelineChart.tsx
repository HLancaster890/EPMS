"use client";

import type { ActivityEvent } from "@/lib/types";

export function TimelineChart({ events }: { events: ActivityEvent[] }) {
  if (!events || events.length === 0) {
    return <p className="text-muted text-sm text-center py-8">No events to display</p>;
  }

  const hours = Array.from({ length: 24 }, (_, i) => i);
  const maxCount = Math.max(1, events.length);

  return (
    <div className="space-y-1">
      <div className="flex items-end gap-0.5 h-32">
        {hours.map((hour) => {
          const count = events.filter((e) => {
            const d = new Date(e.time);
            return d.getHours() === hour;
          }).length;
          const height = (count / maxCount) * 100;
          return (
            <div
              key={hour}
              className="flex-1 flex flex-col items-center justify-end h-full"
            >
              <div
                className="w-full rounded-t-sm transition-all duration-300"
                style={{
                  height: `${Math.max(height, count > 0 ? 4 : 0)}%`,
                  backgroundColor: count > 0 ? "var(--primary)" : "var(--card-border)",
                  opacity: count > 0 ? 0.4 + (count / maxCount) * 0.6 : 0.2,
                }}
              />
            </div>
          );
        })}
      </div>
      <div className="flex justify-between text-[10px] text-muted">
        <span>00:00</span>
        <span>06:00</span>
        <span>12:00</span>
        <span>18:00</span>
        <span>23:00</span>
      </div>
    </div>
  );
}

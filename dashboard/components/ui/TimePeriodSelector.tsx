"use client";

import type { PeriodType } from "@/lib/types";

const periods: { value: PeriodType; label: string }[] = [
  { value: "today", label: "Today" },
  { value: "week", label: "This Week" },
  { value: "month", label: "This Month" },
  { value: "custom", label: "Custom" },
];

export function TimePeriodSelector({
  value,
  onChange,
  startDate,
  endDate,
  onStartDateChange,
  onEndDateChange,
}: {
  value: PeriodType;
  onChange: (p: PeriodType) => void;
  startDate?: string;
  endDate?: string;
  onStartDateChange?: (d: string) => void;
  onEndDateChange?: (d: string) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex border border-border rounded-lg overflow-hidden">
        {periods.map((p) => (
          <button
            key={p.value}
            onClick={() => onChange(p.value)}
            className={`px-3 py-1.5 text-xs font-medium transition-colors ${
              value === p.value
                ? "bg-primary text-white"
                : "bg-card text-muted hover:bg-table-row-hover"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>
      {value === "custom" && (
        <div className="flex items-center gap-2">
          <input
            type="date"
            value={startDate || ""}
            onChange={(e) => onStartDateChange?.(e.target.value)}
            className="px-2 py-1.5 text-xs border border-input-border rounded-lg bg-input-bg text-foreground"
          />
          <span className="text-xs text-muted">to</span>
          <input
            type="date"
            value={endDate || ""}
            onChange={(e) => onEndDateChange?.(e.target.value)}
            className="px-2 py-1.5 text-xs border border-input-border rounded-lg bg-input-bg text-foreground"
          />
        </div>
      )}
    </div>
  );
}

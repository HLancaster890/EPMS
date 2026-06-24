"use client";

export function GaugeChart({
  value,
  max = 100,
  label,
  size = 120,
  strokeWidth = 10,
  color,
  bgColor = "var(--card-border)",
  threshold = { warning: 40, danger: 20 },
}: {
  value: number;
  max?: number;
  label?: string;
  size?: number;
  strokeWidth?: number;
  color?: string;
  bgColor?: string;
  threshold?: { warning: number; danger: number };
}) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const percentage = Math.min(value / max, 1);
  const dashOffset = circumference * (1 - percentage);

  const getColor = () => {
    if (color) return color;
    const pct = (value / max) * 100;
    if (pct >= threshold.warning) return "var(--success)";
    if (pct >= threshold.danger) return "var(--warning)";
    return "var(--danger)";
  };

  const displayValue = max <= 1 ? `${(value * 100).toFixed(0)}%` : value.toFixed(0);

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={size} height={size} className="transform -rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={bgColor}
          strokeWidth={strokeWidth}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={getColor()}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          strokeLinecap="round"
          className="transition-all duration-1000 ease-out"
        />
      </svg>
      <div className="absolute flex flex-col items-center justify-center" style={{ width: size, height: size }}>
        <span className="text-xl font-bold" style={{ color: getColor() }}>
          {displayValue}
        </span>
      </div>
      {label && <span className="text-xs text-muted mt-1">{label}</span>}
    </div>
  );
}

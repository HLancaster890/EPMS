export function ProductivityScore({ score }: { score: number }) {
  const color =
    score >= 70 ? "text-success" : score >= 40 ? "text-warning" : "text-danger";
  const ringColor =
    score >= 70
      ? "stroke-success"
      : score >= 40
      ? "stroke-warning"
      : "stroke-danger";
  const r = 36;
  const circ = 2 * Math.PI * r;
  const offset = circ - (score / 100) * circ;

  return (
    <div className="flex items-center gap-3">
      <svg width="80" height="80" className="-rotate-90">
        <circle
          cx="40"
          cy="40"
          r={r}
          fill="none"
          stroke="#f1f5f9"
          strokeWidth="6"
        />
        <circle
          cx="40"
          cy="40"
          r={r}
          fill="none"
          className={ringColor}
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={offset}
        />
      </svg>
      <div>
        <p className={`text-2xl font-bold ${color}`}>{score.toFixed(0)}</p>
        <p className="text-xs text-zinc-400">out of 100</p>
      </div>
    </div>
  );
}

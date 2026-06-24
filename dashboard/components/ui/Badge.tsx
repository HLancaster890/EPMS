const variants: Record<string, string> = {
  online: "bg-success/10 text-success",
  idle: "bg-warning/10 text-warning",
  offline: "bg-zinc-100 text-zinc-500",
  productive: "bg-success/10 text-success",
  neutral: "bg-blue-50 text-blue-600",
  distracting: "bg-danger/10 text-danger",
  info: "bg-blue-50 text-blue-600",
  warning: "bg-warning/10 text-warning",
  critical: "bg-danger/10 text-danger",
  completed: "bg-success/10 text-success",
  generating: "bg-warning/10 text-warning",
  failed: "bg-danger/10 text-danger",
  pending: "bg-zinc-100 text-zinc-500",
};

export function Badge({
  variant = "info",
  children,
}: {
  variant?: string;
  children: string;
}) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
        variants[variant] || variants.info
      }`}
    >
      {children}
    </span>
  );
}

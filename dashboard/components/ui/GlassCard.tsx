import type { ReactNode } from "react";

export function GlassCard({
  children,
  className = "",
  gradient = false,
  hover = false,
  onClick,
}: {
  children: ReactNode;
  className?: string;
  gradient?: boolean;
  hover?: boolean;
  onClick?: () => void;
}) {
  return (
    <div
      onClick={onClick}
      className={`
        glass rounded-2xl p-5
        ${gradient ? "gradient-border border-2" : "border"}
        ${hover ? "hover:scale-[1.02] cursor-pointer transition-all duration-300" : ""}
        ${className}
      `}
    >
      {children}
    </div>
  );
}

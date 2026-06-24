"use client";

import { Chart as ChartJS, ArcElement, Tooltip, Legend } from "chart.js";
import { Doughnut } from "react-chartjs-2";

ChartJS.register(ArcElement, Tooltip, Legend);

export function DoughnutChart({
  labels,
  data,
  colors,
}: {
  labels: string[];
  data: number[];
  colors: string[];
}) {
  const total = data.reduce((s, v) => s + v, 0);

  return (
    <div className="relative flex items-center justify-center">
      <Doughnut
        data={{
          labels,
          datasets: [
            {
              data,
              backgroundColor: colors,
              borderColor: "transparent",
              hoverOffset: 4,
            },
          ],
        }}
        options={{
          responsive: true,
          maintainAspectRatio: false,
          cutout: "65%",
          plugins: {
            legend: {
              display: true,
              position: "bottom",
              labels: {
                color: "#94a3b8",
                boxWidth: 10,
                padding: 12,
                font: { size: 11 },
              },
            },
            tooltip: {
              backgroundColor: "#1e293b",
              titleColor: "#e2e8f0",
              bodyColor: "#94a3b8",
              borderColor: "#334155",
              borderWidth: 1,
              padding: 8,
              cornerRadius: 8,
              callbacks: {
                label: (ctx) => {
                  const val = ctx.parsed;
                  return `${ctx.label}: ${val} (${total > 0 ? ((val / total) * 100).toFixed(1) : 0}%)`;
                },
              },
            },
          },
        }}
        height={220}
      />
    </div>
  );
}

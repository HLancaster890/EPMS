"use client";

import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Filler,
} from "chart.js";
import { Line } from "react-chartjs-2";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Filler);

export function LineChart({
  labels,
  datasets,
}: {
  labels: string[];
  datasets: {
    label: string;
    data: number[];
    color?: string;
    fill?: boolean;
    pointColor?: string;
  }[];
}) {
  return (
    <div className="relative">
      <Line
        data={{
          labels,
          datasets: datasets.map((ds) => ({
            label: ds.label,
            data: ds.data,
            borderColor: ds.color || "#6366f1",
            backgroundColor: ds.fill
              ? (ds.color || "#6366f1") + "20"
              : "transparent",
            pointBackgroundColor: ds.pointColor || ds.color || "#6366f1",
            pointBorderColor: ds.color || "#6366f1",
            pointRadius: 3,
            pointHoverRadius: 5,
            borderWidth: 2,
            fill: ds.fill || false,
            tension: 0.3,
          })),
        }}
        options={{
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: true, position: "top", labels: { color: "#94a3b8", boxWidth: 12, padding: 12 } },
            tooltip: {
              backgroundColor: "#1e293b",
              titleColor: "#e2e8f0",
              bodyColor: "#94a3b8",
              borderColor: "#334155",
              borderWidth: 1,
              padding: 8,
              cornerRadius: 8,
            },
          },
          scales: {
            x: {
              grid: { color: "rgba(148, 163, 184, 0.1)" },
              ticks: { color: "#64748b", maxTicksLimit: 10 },
            },
            y: {
              grid: { color: "rgba(148, 163, 184, 0.1)" },
              ticks: { color: "#64748b" },
              beginAtZero: true,
            },
          },
        }}
        height={250}
      />
    </div>
  );
}

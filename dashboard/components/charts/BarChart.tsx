"use client";

import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from "chart.js";
import { Bar } from "react-chartjs-2";

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

export function BarChart({
  labels,
  datasets,
  horizontal = false,
}: {
  labels: string[];
  datasets: {
    label: string;
    data: number[];
    color?: string;
  }[];
  horizontal?: boolean;
}) {
  return (
    <div className="relative">
      <Bar
        data={{
          labels,
          datasets: datasets.map((ds) => ({
            label: ds.label,
            data: ds.data,
            backgroundColor: ds.color || "#6366f1",
            hoverBackgroundColor: ds.color ? ds.color + "cc" : "#6366f1cc",
            borderRadius: 4,
            borderSkipped: false,
          })),
        }}
        options={{
          indexAxis: horizontal ? "y" : "x",
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: datasets.length > 1, position: "top", labels: { color: "#94a3b8", boxWidth: 12, padding: 12 } },
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
              ticks: { color: "#64748b" },
            },
            y: {
              grid: { color: "rgba(148, 163, 184, 0.1)" },
              ticks: { color: "#64748b" },
              beginAtZero: true,
            },
          },
        }}
        height={horizontal ? 200 : 250}
      />
    </div>
  );
}

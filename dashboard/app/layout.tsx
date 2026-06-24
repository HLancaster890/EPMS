import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "EPMS - Enterprise Productivity Management",
  description: "Enterprise Productivity Management System",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="h-full" data-theme="midnight-indigo">
      <body className="min-h-full">{children}</body>
    </html>
  );
}

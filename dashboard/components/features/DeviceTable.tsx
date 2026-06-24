import { Badge } from "@/components/ui/Badge";
import type { Device } from "@/lib/types";

export function DeviceTable({ devices }: { devices: Device[] }) {
  if (!devices.length) {
    return <p className="text-zinc-400 text-sm py-8 text-center">No devices registered</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-zinc-400 border-b border-border">
            <th className="pb-3 font-medium">Hostname</th>
            <th className="pb-3 font-medium">User</th>
            <th className="pb-3 font-medium">Platform</th>
            <th className="pb-3 font-medium">IP</th>
            <th className="pb-3 font-medium">Status</th>
            <th className="pb-3 font-medium">Last Seen</th>
          </tr>
        </thead>
        <tbody>
          {devices.map((d) => (
            <tr key={d.id} className="border-b border-border/50">
              <td className="py-3 font-medium">{d.hostname}</td>
              <td className="py-3 text-zinc-600">{d.user_name}</td>
              <td className="py-3 text-zinc-500">{d.platform}</td>
              <td className="py-3 text-zinc-500 font-mono text-xs">
                {d.ip_address}
              </td>
              <td className="py-3">
                <Badge variant={d.status}>{d.status}</Badge>
              </td>
              <td className="py-3 text-zinc-500">
                {timeAgo(d.last_seen)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function timeAgo(ts: string): string {
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  return `${hrs}h ${mins % 60}m ago`;
}

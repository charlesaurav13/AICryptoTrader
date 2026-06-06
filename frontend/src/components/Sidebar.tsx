"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { api } from "@/lib/api";

const NAV = [
  { href: "/overview",  icon: "📊", label: "Overview" },
  { href: "/trades",    icon: "💼", label: "Trades" },
  { href: "/positions", icon: "📈", label: "Positions" },
  { href: "/agents",    icon: "🤖", label: "Agents" },
  { href: "/signals",   icon: "🧠", label: "ML Signals" },
];

export default function Sidebar() {
  const path = usePathname();
  const router = useRouter();
  async function logout() {
    try { await api.logout(); } catch {}
    router.push("/login");
  }
  return (
    <aside className="w-[220px] min-w-[220px] bg-s1 border-r border-b1 flex flex-col h-screen sticky top-0">
      <div className="flex items-center gap-2.5 p-5 border-b border-b1">
        <div className="w-8 h-8 bg-gradient-to-br from-bl to-pu rounded-lg flex items-center justify-center">⚡</div>
        <div>
          <div className="text-[15px] font-bold">CryptoSwarm</div>
          <div className="text-[10px] text-t2">Phase 3 · Paper Trading</div>
        </div>
      </div>
      <nav className="flex-1 p-2 space-y-0.5">
        {NAV.map(({ href, icon, label }) => (
          <Link key={href} href={href}
            className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
              path === href ? "bg-bl/15 text-bl font-medium" : "text-t2 hover:bg-s3 hover:text-t1"
            }`}>
            <span className="text-base w-5 text-center">{icon}</span>{label}
          </Link>
        ))}
      </nav>
      <div className="p-4 border-t border-b1">
        <button onClick={logout}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-t2 hover:bg-s3 hover:text-t1 transition-colors">
          <span>🚪</span> Logout
        </button>
      </div>
    </aside>
  );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import {
  LayoutDashboard,
  Database,
  ShieldAlert,
  Users,
  Activity,
  Settings,
  Hexagon,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { icon: LayoutDashboard, href: "/console", label: "Command Center", exact: true },
  { icon: Database, href: "/console/airlock", label: "SQL Airlock" },
  { icon: ShieldAlert, href: "/console/security", label: "Security Events" },
  { icon: Users, href: "/console/tenants", label: "Tenant Intelligence" },
  { icon: Activity, href: "/console/observability", label: "Observability" },
];

function NavItem({
  icon: Icon,
  href,
  label,
  exact,
}: {
  icon: React.ElementType;
  href: string;
  label: string;
  exact?: boolean;
}) {
  const pathname = usePathname();
  const isActive = exact ? pathname === href : pathname.startsWith(href);

  return (
    <Link href={href} className="group relative flex items-center justify-center" title={label}>
      {isActive && (
        <motion.div
          layoutId="rail-indicator"
          className="absolute left-0 h-7 w-[2px] rounded-r-full bg-ae-cyan shadow-glow-cyan-sm"
          transition={{ type: "spring", stiffness: 400, damping: 30 }}
        />
      )}
      <div
        className={cn(
          "flex h-10 w-10 items-center justify-center rounded-xl transition-all duration-200",
          isActive
            ? "bg-ae-cyan/10 text-ae-cyan"
            : "text-ae-muted hover:bg-white/[0.04] hover:text-ae-text"
        )}
      >
        <Icon size={17} strokeWidth={isActive ? 1.75 : 1.5} />
      </div>
      {/* Tooltip */}
      <div className="pointer-events-none absolute left-14 z-50 whitespace-nowrap rounded-lg border border-white/10 bg-ae-elevated px-3 py-1.5 text-xs font-medium text-ae-text opacity-0 shadow-panel transition-opacity group-hover:opacity-100">
        {label}
        <div className="absolute -left-1.5 top-1/2 h-2 w-2 -translate-y-1/2 rotate-45 border-b border-l border-white/10 bg-ae-elevated" />
      </div>
    </Link>
  );
}

export function LeftRail() {
  return (
    <aside className="flex h-full w-14 flex-col items-center border-r border-white/[0.06] bg-ae-surface/60 py-4">
      {/* Logo */}
      <Link
        href="/console"
        className="mb-6 flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-ae-cyan/20 to-ae-violet/20 text-ae-cyan transition-all hover:from-ae-cyan/30 hover:to-ae-violet/30"
      >
        <Hexagon size={18} strokeWidth={1.5} fill="rgba(0,212,255,0.1)" />
      </Link>

      {/* Divider */}
      <div className="mb-4 h-px w-6 bg-white/[0.06]" />

      {/* Navigation */}
      <nav className="flex flex-1 flex-col items-center gap-1">
        {navItems.map((item) => (
          <NavItem key={item.href} {...item} />
        ))}
      </nav>

      {/* Settings at bottom */}
      <div className="flex flex-col items-center gap-1">
        <div className="mb-1 h-px w-6 bg-white/[0.06]" />
        <NavItem icon={Settings} href="/console/settings" label="Settings" />
      </div>
    </aside>
  );
}

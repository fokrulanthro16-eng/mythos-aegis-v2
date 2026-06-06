"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ShieldX,
  Database,
  Zap,
  KeyRound,
  Activity,
  Lock,
  CheckCircle2,
  Radio,
} from "lucide-react";
import { securityEvents, type SecurityEvent } from "@/lib/mock-data";
import { cn } from "@/lib/utils";
import { RelativeTime } from "@/components/relative-time";

const TYPE_CONFIG = {
  jwt_failure: { icon: KeyRound, color: "text-ae-red", bg: "bg-ae-red/10", border: "border-ae-red/20", label: "JWT" },
  rbac_denial: { icon: Lock, color: "text-ae-amber", bg: "bg-ae-amber/10", border: "border-ae-amber/20", label: "RBAC" },
  sql_block: { icon: Database, color: "text-ae-violet", bg: "bg-ae-violet/10", border: "border-ae-violet/20", label: "SQL" },
  rate_limit: { icon: Zap, color: "text-ae-cyan", bg: "bg-ae-cyan/10", border: "border-ae-cyan/20", label: "RATE" },
  health_change: { icon: Activity, color: "text-ae-green", bg: "bg-ae-green/10", border: "border-ae-green/20", label: "HLTH" },
  secret_rotation: { icon: KeyRound, color: "text-ae-violet", bg: "bg-ae-violet/10", border: "border-ae-violet/20", label: "KEY" },
  tenant_isolation: { icon: ShieldX, color: "text-ae-red", bg: "bg-ae-red/10", border: "border-ae-red/20", label: "ISO" },
  auth_success: { icon: CheckCircle2, color: "text-ae-green", bg: "bg-ae-green/10", border: "border-ae-green/20", label: "AUTH" },
};

const SEVERITY_DOT = {
  critical: "bg-ae-red shadow-glow-red",
  high: "bg-ae-amber shadow-glow-amber",
  medium: "bg-ae-cyan",
  low: "bg-ae-muted",
  info: "bg-ae-green",
};

function EventRow({ event }: { event: SecurityEvent }) {
  const cfg = TYPE_CONFIG[event.type];
  const Icon = cfg.icon;

  return (
    <motion.div
      initial={{ opacity: 0, x: 12 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -12 }}
      transition={{ duration: 0.2 }}
      className="group relative cursor-default px-3 py-2.5 hover:bg-white/[0.02]"
    >
      <div className="flex items-start gap-2.5">
        {/* Icon */}
        <div className={cn("mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md", cfg.bg)}>
          <Icon size={12} className={cfg.color} />
        </div>

        {/* Content */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span className={cn("text-[10px] font-bold tracking-wider", cfg.color)}>
              {cfg.label}
            </span>
            <span
              className={cn(
                "h-1.5 w-1.5 rounded-full",
                SEVERITY_DOT[event.severity]
              )}
            />
            <span className="text-[10px] text-ae-faint">{event.tenant.toUpperCase()}</span>
          </div>
          <p className="mt-0.5 text-[11px] leading-snug text-ae-text/80 line-clamp-2">
            {event.message}
          </p>
          <RelativeTime date={event.timestamp} className="mt-0.5 text-[10px] text-ae-muted" />
        </div>
      </div>

      {/* Left border accent */}
      <div className={cn("absolute inset-y-0 left-0 w-[1.5px] opacity-0 transition-opacity group-hover:opacity-100 rounded-r", cfg.color.replace("text-", "bg-"))} />
    </motion.div>
  );
}

export function LiveEventStream() {
  const [events, setEvents] = useState<SecurityEvent[]>(
    [...securityEvents].sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
  );
  const scrollRef = useRef<HTMLDivElement>(null);

  // Simulate new events coming in
  useEffect(() => {
    const messages = [
      { type: "sql_block" as const, message: "Airlock blocked SELECT *", tenant: "beta", severity: "medium" as const },
      { type: "rate_limit" as const, message: "Rate limit hit — AUTHENTICATED policy", tenant: "alpha", severity: "low" as const },
      { type: "auth_success" as const, message: "Session authenticated via JWT", tenant: "gamma", severity: "info" as const },
      { type: "rbac_denial" as const, message: "Permission denied: orders.cancel", tenant: "beta", severity: "high" as const },
      { type: "jwt_failure" as const, message: "Token signature invalid", tenant: "alpha", severity: "high" as const },
    ];

    const id = setInterval(() => {
      const template = messages[Math.floor(Math.random() * messages.length)];
      const newEvent: SecurityEvent = {
        id: `live-${Date.now()}`,
        type: template.type,
        severity: template.severity,
        message: template.message,
        detail: "",
        tenant: template.tenant,
        timestamp: new Date(),
        resolved: true,
      };
      setEvents((prev) => [newEvent, ...prev.slice(0, 49)]);
    }, 3500 + Math.random() * 4000);

    return () => clearInterval(id);
  }, []);

  return (
    <aside className="flex h-full w-72 flex-col border-l border-white/[0.06] bg-ae-surface/40">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3">
        <div className="flex items-center gap-2">
          <Radio size={13} className="text-ae-cyan" />
          <span className="text-xs font-semibold uppercase tracking-widest text-ae-muted">
            Live Feed
          </span>
        </div>
        <div className="flex items-center gap-1.5 rounded-full bg-ae-cyan/10 px-2 py-0.5">
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-ae-cyan opacity-50" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-ae-cyan" />
          </span>
          <span className="font-mono text-[10px] font-semibold text-ae-cyan">LIVE</span>
        </div>
      </div>

      {/* Event list */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="divide-y divide-white/[0.04]">
          <AnimatePresence initial={false}>
            {events.map((event) => (
              <EventRow key={event.id} event={event} />
            ))}
          </AnimatePresence>
        </div>
      </div>
    </aside>
  );
}

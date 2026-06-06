"use client";

import { motion } from "framer-motion";
import { SecurityRadar } from "@/components/security-radar";
import { MetricGlassCard } from "@/components/metric-glass-card";
import { securityEvents, systemStatus, sparkline7d } from "@/lib/mock-data";
import { ShieldAlert, KeyRound, Lock, Database } from "lucide-react";
import { cn } from "@/lib/utils";
import { RelativeTime } from "@/components/relative-time";

const SEVERITY_STYLE: Record<string, string> = {
  critical: "border-ae-red/40 bg-ae-red/10 text-ae-red",
  high:     "border-ae-amber/30 bg-ae-amber/10 text-ae-amber",
  medium:   "border-ae-cyan/25 bg-ae-cyan/5 text-ae-cyan",
  low:      "border-white/10 bg-white/[0.02] text-ae-muted",
  info:     "border-ae-green/25 bg-ae-green/10 text-ae-green",
};

const TYPE_ICON: Record<string, React.ElementType> = {
  jwt_failure: KeyRound,
  rbac_denial: Lock,
  sql_block:   Database,
  tenant_isolation: ShieldAlert,
  rate_limit:  ShieldAlert,
  secret_rotation: KeyRound,
  health_change: ShieldAlert,
  auth_success:  ShieldAlert,
};

export default function SecurityPage() {
  const critical = securityEvents.filter((e) => e.severity === "critical" || e.severity === "high");
  const unresolved = securityEvents.filter((e) => !e.resolved);

  return (
    <div className="h-full overflow-y-auto">
      <div className="flex flex-col gap-4 p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="font-mono text-[9px] font-bold uppercase tracking-[0.2em] text-ae-muted">SECURITY EVENTS</p>
            <h2 className="text-xl font-semibold tracking-tight text-ae-text" style={{ letterSpacing: "-0.02em" }}>
              Threat Intelligence
            </h2>
          </div>
          {unresolved.length > 0 && (
            <motion.div
              className="flex items-center gap-2 rounded-xl border border-ae-red/30 bg-ae-red/10 px-3 py-1.5"
              animate={{ boxShadow: ["0 0 0px rgba(239,68,68,0)", "0 0 16px rgba(239,68,68,0.2)", "0 0 0px rgba(239,68,68,0)"] }}
              transition={{ duration: 2, repeat: Infinity }}
            >
              <ShieldAlert size={13} className="text-ae-red" />
              <span className="font-mono text-[10px] font-bold text-ae-red">{unresolved.length} UNRESOLVED</span>
            </motion.div>
          )}
        </div>

        <div className="grid grid-cols-4 gap-3">
          <MetricGlassCard label="JWT Failures" value={systemStatus.jwtFailuresToday} change={-12} changeLabel="vs yesterday" accent="red"
            sparkline={sparkline7d.slice(0, 14).map((v) => v % 12)} />
          <MetricGlassCard label="RBAC Denials" value={systemStatus.rbacDenialsToday} change={8} changeLabel="vs avg" accent="amber"
            sparkline={sparkline7d.map((v) => (v * 0.35) | 0)} />
          <MetricGlassCard label="SQL Blocks" value={systemStatus.sqlBlocksToday} change={-22} changeLabel="vs avg" accent="violet"
            sparkline={sparkline7d.slice(0, 14).map((v) => v % 18)} />
          <MetricGlassCard label="Isolation Events" value={3} change={0} changeLabel="vs avg" accent="cyan"
            sparkline={sparkline7d.slice(0, 14).map((v) => v % 4)} />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <SecurityRadar />
          <div className="overflow-hidden rounded-2xl border border-white/[0.07] bg-ae-surface/40 p-4">
            <p className="font-mono text-[9px] font-bold uppercase tracking-[0.18em] text-ae-muted mb-3">
              CRITICAL &amp; HIGH SEVERITY
            </p>
            <div className="flex flex-col gap-2">
              {critical.map((event, i) => {
                const Icon = TYPE_ICON[event.type] ?? ShieldAlert;
                return (
                  <motion.div
                    key={event.id}
                    initial={{ opacity: 0, x: 8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.06 }}
                    className={cn("flex items-start gap-2.5 rounded-xl border p-2.5", SEVERITY_STYLE[event.severity])}
                  >
                    <Icon size={12} className="mt-0.5 shrink-0" />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <p className="font-mono text-[10px] font-semibold">{event.message}</p>
                        <RelativeTime date={event.timestamp} className="shrink-0 font-mono text-[9px] opacity-50" />
                      </div>
                      <p className="mt-0.5 text-[10px] opacity-60">{event.detail}</p>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </div>
        </div>

        <div className="overflow-hidden rounded-2xl border border-white/[0.07] bg-ae-surface/40 p-4">
          <p className="font-mono text-[9px] font-bold uppercase tracking-[0.18em] text-ae-muted mb-3">
            EVENT LOG — {securityEvents.length} EVENTS
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-[10px]">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  {["SEVERITY", "TYPE", "MESSAGE", "TENANT", "TIME", "STATUS"].map((h) => (
                    <th key={h} className="pb-2 pr-4 text-left font-mono text-[9px] font-bold uppercase tracking-wider text-ae-muted first:pl-0">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.03]">
                {securityEvents.map((e) => (
                  <tr key={e.id} className="hover:bg-white/[0.015] transition-colors">
                    <td className="py-2 pr-4">
                      <span className={cn("font-mono text-[9px] font-bold uppercase",
                        e.severity === "critical" && "text-ae-red",
                        e.severity === "high" && "text-ae-amber",
                        e.severity === "medium" && "text-ae-cyan",
                        e.severity === "low" && "text-ae-muted",
                        e.severity === "info" && "text-ae-green"
                      )}>{e.severity}</span>
                    </td>
                    <td className="py-2 pr-4 font-mono text-ae-muted">{e.type.replace(/_/g, " ")}</td>
                    <td className="py-2 pr-4 text-ae-text max-w-xs truncate">{e.message}</td>
                    <td className="py-2 pr-4 font-mono text-ae-muted">{e.tenant.toUpperCase()}</td>
                    <td className="py-2 pr-4"><RelativeTime date={e.timestamp} className="font-mono text-ae-faint" /></td>
                    <td className="py-2">
                      <span className={cn("font-mono text-[9px] font-bold", e.resolved ? "text-ae-green" : "text-ae-red")}>
                        {e.resolved ? "RESOLVED" : "OPEN"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

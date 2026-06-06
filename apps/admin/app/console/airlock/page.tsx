"use client";

import { motion } from "framer-motion";
import { AirlockVisualizer } from "@/components/airlock-visualizer";
import { MetricGlassCard } from "@/components/metric-glass-card";
import { systemStatus, sparkline7d } from "@/lib/mock-data";

const RULES = [
  { id: "r1", rule: "SELECT-only enforcement", detail: "No INSERT / UPDATE / DELETE permitted" },
  { id: "r2", rule: "Table whitelist", detail: "Allowed: users, orders, products, order_items" },
  { id: "r3", rule: "Column masking", detail: "email → [REDACTED], password_hash → [REMOVED]" },
  { id: "r4", rule: "Tenant injection", detail: "WHERE tenant_id=$tenant auto-appended to all queries" },
  { id: "r5", rule: "90-day date bound", detail: "created_at > NOW() - INTERVAL '90 days' enforced" },
  { id: "r6", rule: "LIMIT clamp", detail: "Maximum rows: 100 (SQL_MAX_LIMIT)" },
  { id: "r7", rule: "AST subquery depth", detail: "Nested queries max depth: 2" },
  { id: "r8", rule: "Parameterized execution", detail: "Zero string interpolation permitted" },
];

export default function AirlockPage() {
  return (
    <div className="h-full overflow-y-auto">
      <div className="flex flex-col gap-4 p-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <p className="font-mono text-[9px] font-bold uppercase tracking-[0.2em] text-ae-muted">SQL AIRLOCK</p>
            <h2 className="text-xl font-semibold tracking-tight text-ae-text" style={{ letterSpacing: "-0.02em" }}>
              Query Validation Pipeline
            </h2>
          </div>
          <motion.div
            className="flex items-center gap-2 rounded-xl border border-ae-green/20 bg-ae-green/10 px-3 py-1.5"
            animate={{ boxShadow: ["0 0 0px rgba(16,185,129,0)", "0 0 12px rgba(16,185,129,0.15)", "0 0 0px rgba(16,185,129,0)"] }}
            transition={{ duration: 3, repeat: Infinity }}
          >
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-ae-green opacity-60" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-ae-green" />
            </span>
            <span className="font-mono text-[10px] font-bold text-ae-green">AIRLOCK ACTIVE</span>
          </motion.div>
        </div>

        {/* Metrics */}
        <div className="grid grid-cols-4 gap-3">
          <MetricGlassCard label="Queries Today" value={1847} change={15} changeLabel="vs yesterday" accent="cyan"
            sparkline={sparkline7d.slice(0, 14)} />
          <MetricGlassCard label="Blocked" value={systemStatus.sqlBlocksToday} change={-22} changeLabel="vs avg" accent="red"
            sparkline={sparkline7d.slice(0, 14).map((v) => v % 8)} />
          <MetricGlassCard label="Rewritten" value={234} change={3} changeLabel="vs avg" accent="amber"
            sparkline={sparkline7d.map((v) => (v * 0.3) | 0)} />
          <MetricGlassCard label="Avg Query Time" value={21} unit="ms" change={-8} changeLabel="vs avg" accent="green"
            sparkline={sparkline7d.slice(0, 14).map((v) => 10 + v * 0.15)} />
        </div>

        {/* Visualizer */}
        <AirlockVisualizer />

        {/* Rules */}
        <div className="rounded-2xl border border-white/[0.07] bg-ae-surface/40 p-5">
          <p className="font-mono text-[9px] font-bold uppercase tracking-[0.18em] text-ae-muted mb-4">
            ENFORCED RULES — 8 ACTIVE
          </p>
          <div className="grid grid-cols-2 gap-2.5">
            {RULES.map((item, i) => (
              <motion.div
                key={item.id}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.05 }}
                className="flex items-start gap-2.5 rounded-xl border border-ae-green/15 bg-ae-green/5 p-3"
              >
                <div className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-ae-green" style={{ boxShadow: "0 0 6px #10b981" }} />
                <div>
                  <p className="font-mono text-[10px] font-semibold text-ae-green">{item.rule}</p>
                  <p className="mt-0.5 text-[10px] text-ae-muted">{item.detail}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

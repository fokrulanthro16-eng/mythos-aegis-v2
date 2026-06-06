"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { SystemTopology } from "@/components/system-topology";
import { ThreatHeatmap } from "@/components/threat-heatmap";
import { RiskPrediction } from "@/components/risk-prediction";
import { ActivityTimeline } from "@/components/activity-timeline";
import { systemStatus, tenants } from "@/lib/mock-data";

function LiveMetric({
  label, value, color = "#00d4ff", delta,
}: {
  label: string;
  value: string | number;
  color?: string;
  delta?: string;
}) {
  return (
    <div className="flex flex-col items-center gap-0.5 px-4 py-2 border-r border-white/[0.05] last:border-0">
      <span className="font-mono text-[10px] uppercase tracking-widest text-ae-muted">{label}</span>
      <span className="font-mono text-lg font-bold" style={{ color, textShadow: `0 0 12px ${color}40` }}>
        {value}
      </span>
      {delta && (
        <span className="font-mono text-[9px] text-ae-muted">{delta}</span>
      )}
    </div>
  );
}

function SystemStatusBar() {
  const [time, setTime] = useState("");
  useEffect(() => {
    const t = () =>
      setTime(
        new Date().toLocaleTimeString("en-US", { hour12: false, timeZoneName: "short" })
      );
    t();
    const id = setInterval(t, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-center justify-between shrink-0 rounded-xl border border-white/[0.06] bg-ae-surface/60"
      style={{ boxShadow: "0 0 0 1px rgba(255,255,255,0.03)" }}
    >
      {/* Left: tenant status */}
      <div className="flex items-center gap-2 px-4 py-2 border-r border-white/[0.05]">
        <span className="font-mono text-[9px] font-bold uppercase tracking-[0.2em] text-ae-muted">
          TENANTS
        </span>
        {tenants.map((t, idx) => (
          <div key={t.id} className="flex items-center gap-1">
            <motion.div
              className="h-1.5 w-1.5 rounded-full"
              style={{ background: t.health === "healthy" ? "#10b981" : "#f59e0b" }}
              animate={{ opacity: [1, 0.5, 1] }}
              transition={{ duration: 2.5, repeat: Infinity, delay: idx * 0.8 }}
            />
            <span className="font-mono text-[9px] text-ae-muted">{t.slug.toUpperCase()}</span>
          </div>
        ))}
      </div>

      {/* Center: live metrics */}
      <div className="flex flex-1 items-stretch divide-x divide-white/[0.05]">
        <LiveMetric label="REQ/24H" value={(systemStatus.requestsLast24h / 1000).toFixed(1) + "K"} color="#00d4ff" />
        <LiveMetric label="AVG LATENCY" value={`${systemStatus.avgLatencyMs}ms`} color="#8b5cf6" />
        <LiveMetric label="SQL BLOCKS" value={systemStatus.sqlBlocksToday} color="#f59e0b" />
        <LiveMetric label="JWT FAILS" value={systemStatus.jwtFailuresToday} color="#ef4444" />
        <LiveMetric label="UPTIME" value={`${systemStatus.uptimePercent}%`} color="#10b981" />
        <LiveMetric label="POLICIES" value={systemStatus.activePolicies} color="#00d4ff" />
      </div>

      {/* Right: clock + risk */}
      <div className="flex items-center gap-3 px-4 py-2 border-l border-white/[0.05]">
        <div className="flex items-center gap-1.5 rounded-full border border-ae-green/25 bg-ae-green/10 px-2.5 py-1">
          <motion.span
            className="h-1.5 w-1.5 rounded-full bg-ae-green"
            animate={{ opacity: [1, 0.3, 1] }}
            transition={{ duration: 1.2, repeat: Infinity }}
          />
          <span className="font-mono text-[9px] font-bold text-ae-green">OPERATIONAL</span>
        </div>
        <span className="font-mono text-[10px] text-ae-muted">{time}</span>
      </div>
    </motion.div>
  );
}

export default function ConsolePage() {
  return (
    <div className="flex h-full flex-col gap-2.5 overflow-hidden p-3">
      {/* Status bar */}
      <SystemStatusBar />

      {/* Main 3-column grid */}
      <div className="flex flex-1 gap-2.5 overflow-hidden min-h-0">
        {/* Left column: heatmap */}
        <motion.div
          initial={{ opacity: 0, x: -16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.1 }}
          className="flex w-[240px] shrink-0 flex-col gap-2.5 overflow-hidden min-h-0"
        >
          <div className="flex-1 min-h-0">
            <ThreatHeatmap />
          </div>

          {/* Mini tenant constellation summary */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
            className="shrink-0 rounded-xl border border-white/[0.06] bg-ae-surface/60 p-3"
          >
            <p className="font-mono text-[9px] font-bold uppercase tracking-[0.18em] text-ae-muted mb-2">
              ISOLATION STATUS
            </p>
            <div className="flex flex-col gap-1.5">
              {tenants.map((t) => (
                <div key={t.id} className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <div
                      className="h-1.5 w-1.5 rounded-full"
                      style={{
                        background: t.health === "healthy" ? "#10b981" : "#f59e0b",
                        boxShadow: `0 0 4px ${t.health === "healthy" ? "#10b981" : "#f59e0b"}`,
                      }}
                    />
                    <span className="font-mono text-[9px] text-ae-muted">{t.name}</span>
                  </div>
                  <span
                    className="font-mono text-[9px] font-bold"
                    style={{ color: t.health === "healthy" ? "#10b981" : "#f59e0b" }}
                  >
                    {t.health.toUpperCase()}
                  </span>
                </div>
              ))}
            </div>
            <div className="mt-2 pt-2 border-t border-white/[0.05] flex justify-between text-[9px]">
              <span className="font-mono text-ae-muted">SQL BLOCKS</span>
              <span className="font-mono text-ae-amber">{systemStatus.sqlBlocksToday}</span>
            </div>
            <div className="flex justify-between text-[9px]">
              <span className="font-mono text-ae-muted">RBAC DENIALS</span>
              <span className="font-mono text-ae-red">{systemStatus.rbacDenialsToday}</span>
            </div>
          </motion.div>
        </motion.div>

        {/* Center: topology */}
        <motion.div
          initial={{ opacity: 0, scale: 0.97 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.05 }}
          className="flex-1 min-w-0 min-h-0"
        >
          <SystemTopology />
        </motion.div>

        {/* Right column: risk prediction */}
        <motion.div
          initial={{ opacity: 0, x: 16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.1 }}
          className="flex w-[268px] shrink-0 min-h-0"
        >
          <RiskPrediction />
        </motion.div>
      </div>

      {/* Bottom: activity timeline */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="h-28 shrink-0"
      >
        <ActivityTimeline />
      </motion.div>
    </div>
  );
}

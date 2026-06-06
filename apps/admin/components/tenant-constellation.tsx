"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { tenants, type Tenant } from "@/lib/mock-data";
import { ShieldCheck, TrendingUp, Users, Zap } from "lucide-react";

const CORE = { x: 260, y: 200 };
const NODE_POSITIONS = [
  { x: 80, y: 90 },   // Alpha
  { x: 440, y: 90 },  // Beta
  { x: 260, y: 340 }, // Gamma
];

const HEALTH_COLOR: Record<Tenant["health"], string> = {
  healthy: "#10b981",
  degraded: "#f59e0b",
  critical: "#ef4444",
};

const HEALTH_BG: Record<Tenant["health"], string> = {
  healthy: "rgba(16,185,129,0.12)",
  degraded: "rgba(245,158,11,0.12)",
  critical: "rgba(239,68,68,0.12)",
};

function TenantDetail({ tenant }: { tenant: Tenant }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: 12 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 12 }}
      className="absolute right-0 top-0 bottom-0 w-56 rounded-xl border border-white/[0.08] bg-ae-elevated/90 p-4 backdrop-blur-sm"
      style={{ boxShadow: "0 0 0 1px rgba(255,255,255,0.06)" }}
    >
      <div className="flex items-center gap-2 mb-4">
        <div
          className="h-2.5 w-2.5 rounded-full"
          style={{ background: HEALTH_COLOR[tenant.health], boxShadow: `0 0 8px ${HEALTH_COLOR[tenant.health]}` }}
        />
        <span className="text-sm font-semibold text-ae-text">{tenant.name}</span>
      </div>

      <div className="flex flex-col gap-2.5">
        {[
          { icon: TrendingUp, label: "Requests / day", value: tenant.requestsToday.toLocaleString() },
          { icon: Users, label: "Active users", value: tenant.activeUsers.toString() },
          { icon: ShieldCheck, label: "Isolation", value: tenant.isolationStatus.toUpperCase() },
          { icon: Zap, label: "Risk score", value: tenant.riskScore.toString() },
        ].map(({ icon: Icon, label, value }) => (
          <div key={label} className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <Icon size={11} className="text-ae-muted" />
              <span className="text-[11px] text-ae-muted">{label}</span>
            </div>
            <span className="font-mono text-[11px] font-medium text-ae-text">{value}</span>
          </div>
        ))}
      </div>

      <div className="mt-4 pt-3 border-t border-white/[0.06]">
        <div className="flex justify-between text-[10px]">
          <span className="text-ae-muted">SQL blocks</span>
          <span className="font-mono text-ae-amber">{tenant.sqlQueriesBlocked}</span>
        </div>
        <div className="flex justify-between text-[10px] mt-1">
          <span className="text-ae-muted">RBAC denials</span>
          <span className="font-mono text-ae-red">{tenant.rbacDenials}</span>
        </div>
        <div className="flex justify-between text-[10px] mt-1">
          <span className="text-ae-muted">JWT failures</span>
          <span className="font-mono text-ae-red">{tenant.jwtFailures}</span>
        </div>
      </div>

      <div className="mt-3">
        <div className="flex justify-between text-[10px] mb-1">
          <span className="text-ae-muted">Health score</span>
          <span className="font-mono" style={{ color: HEALTH_COLOR[tenant.health] }}>
            {tenant.healthScore}%
          </span>
        </div>
        <div className="h-1 w-full rounded-full bg-ae-base overflow-hidden">
          <motion.div
            className="h-full rounded-full"
            style={{ background: HEALTH_COLOR[tenant.health] }}
            initial={{ width: 0 }}
            animate={{ width: `${tenant.healthScore}%` }}
            transition={{ duration: 0.6 }}
          />
        </div>
      </div>
    </motion.div>
  );
}

export function TenantConstellation() {
  const [selected, setSelected] = useState<string | null>(null);
  const selectedTenant = tenants.find((t) => t.id === selected);

  return (
    <div className="relative overflow-hidden rounded-2xl border border-white/[0.07] bg-ae-surface/40 p-5"
      style={{ boxShadow: "0 0 0 1px rgba(255,255,255,0.05), 0 16px 48px rgba(0,0,0,0.4)" }}
    >
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-ae-text">Tenant Constellation</h3>
          <p className="text-[11px] text-ae-muted">Click a node to inspect</p>
        </div>
        <div className="flex items-center gap-2">
          {tenants.map((t) => (
            <div key={t.id} className="flex items-center gap-1">
              <div
                className="h-1.5 w-1.5 rounded-full"
                style={{ background: HEALTH_COLOR[t.health] }}
              />
              <span className="text-[10px] text-ae-muted">{t.slug}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="relative">
        <svg
          width="100%"
          viewBox="0 0 520 420"
          className="overflow-visible"
          style={{ maxHeight: 280 }}
        >
          <defs>
            <radialGradient id="core-glow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="rgba(0,212,255,0.2)" />
              <stop offset="100%" stopColor="transparent" />
            </radialGradient>
            <filter id="node-glow">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Connection lines */}
          {tenants.map((tenant, i) => {
            const pos = NODE_POSITIONS[i];
            const isSelected = tenant.id === selected;
            return (
              <g key={`line-${tenant.id}`}>
                <line
                  x1={CORE.x} y1={CORE.y}
                  x2={pos.x} y2={pos.y}
                  stroke="rgba(255,255,255,0.06)"
                  strokeWidth={1}
                />
                {isSelected && (
                  <motion.line
                    x1={CORE.x} y1={CORE.y}
                    x2={pos.x} y2={pos.y}
                    stroke={HEALTH_COLOR[tenant.health]}
                    strokeWidth={1.5}
                    strokeOpacity={0.5}
                    strokeDasharray="6 4"
                    className="flow-animate"
                  />
                )}
                {/* Animated dot flowing from core to node */}
                <motion.circle
                  r="2"
                  fill={HEALTH_COLOR[tenant.health]}
                  opacity={0.6}
                  animate={{
                    cx: [CORE.x, pos.x],
                    cy: [CORE.y, pos.y],
                    opacity: [0, 0.8, 0],
                  }}
                  transition={{
                    duration: 2.5,
                    delay: i * 0.8,
                    repeat: Infinity,
                    ease: "linear",
                  }}
                />
              </g>
            );
          })}

          {/* Core node */}
          <g>
            <circle cx={CORE.x} cy={CORE.y} r={42} fill="url(#core-glow)" />
            <motion.circle
              cx={CORE.x} cy={CORE.y} r={26}
              fill="rgba(0,212,255,0.08)"
              stroke="#00d4ff"
              strokeWidth={1.5}
              animate={{ r: [24, 27, 24] }}
              transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
            />
            <circle cx={CORE.x} cy={CORE.y} r={18} fill="rgba(0,212,255,0.12)" />
            <text
              x={CORE.x} y={CORE.y - 2}
              textAnchor="middle"
              dominantBaseline="middle"
              fontSize="8"
              fontFamily="monospace"
              fill="#00d4ff"
              fontWeight="bold"
            >
              AEGIS
            </text>
            <text
              x={CORE.x} y={CORE.y + 8}
              textAnchor="middle"
              dominantBaseline="middle"
              fontSize="7"
              fontFamily="monospace"
              fill="rgba(0,212,255,0.6)"
            >
              CORE
            </text>
          </g>

          {/* Tenant nodes */}
          {tenants.map((tenant, i) => {
            const pos = NODE_POSITIONS[i];
            const color = HEALTH_COLOR[tenant.health];
            const bg = HEALTH_BG[tenant.health];
            const isSelected = tenant.id === selected;

            return (
              <g
                key={tenant.id}
                onClick={() => setSelected(tenant.id === selected ? null : tenant.id)}
                className="cursor-pointer"
              >
                {/* Selection ring */}
                {isSelected && (
                  <motion.circle
                    cx={pos.x} cy={pos.y}
                    r={32}
                    fill="none"
                    stroke={color}
                    strokeWidth={1}
                    strokeOpacity={0.4}
                    animate={{ r: [30, 34, 30], strokeOpacity: [0.4, 0.2, 0.4] }}
                    transition={{ duration: 2, repeat: Infinity }}
                  />
                )}

                {/* Ping ring */}
                <motion.circle
                  cx={pos.x} cy={pos.y}
                  r={22}
                  fill="none"
                  stroke={color}
                  strokeWidth={1}
                  animate={{ r: [20, 30], opacity: [0.4, 0] }}
                  transition={{ duration: 2.5, delay: i * 0.6, repeat: Infinity, ease: "easeOut" }}
                />

                {/* Main node */}
                <circle
                  cx={pos.x} cy={pos.y}
                  r={22}
                  fill={bg}
                  stroke={color}
                  strokeWidth={isSelected ? 1.5 : 1}
                  filter="url(#node-glow)"
                />

                {/* Inner node */}
                <circle cx={pos.x} cy={pos.y} r={14} fill={bg} />

                {/* Slug label */}
                <text
                  x={pos.x} y={pos.y}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fontSize="10"
                  fontFamily="system-ui, sans-serif"
                  fill={color}
                  fontWeight="600"
                >
                  {tenant.slug.toUpperCase().slice(0, 1)}
                </text>

                {/* Name below */}
                <text
                  x={pos.x} y={pos.y + 32}
                  textAnchor="middle"
                  fontSize="9"
                  fontFamily="system-ui, sans-serif"
                  fill="rgba(255,255,255,0.6)"
                  fontWeight="500"
                >
                  {tenant.name.split(" ")[0]}
                </text>

                {/* Health dot */}
                <circle cx={pos.x + 16} cy={pos.y - 14} r={4} fill={color}
                  style={{ filter: `drop-shadow(0 0 4px ${color})` }}
                />
              </g>
            );
          })}
        </svg>

        {/* Detail panel */}
        <AnimatePresence>
          {selectedTenant && (
            <TenantDetail tenant={selectedTenant} />
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

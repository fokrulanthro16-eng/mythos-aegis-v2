"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface TopologyNode {
  id: string;
  label: string;
  sub: string;
  x: number;
  y: number;
  type: "external" | "infra" | "service" | "security" | "data";
  health: "ok" | "warn" | "err";
  metric: string;
}

interface TopologyEdge {
  id: string;
  from: string;
  to: string;
  blocked?: boolean;
}

const NODES: TopologyNode[] = [
  { id: "inet", label: "INTERNET", sub: "external traffic", x: 350, y: 44, type: "external", health: "ok", metric: "∞" },
  { id: "lb", label: "LOAD BALANCER", sub: "nginx / 2 upstreams", x: 350, y: 120, type: "infra", health: "ok", metric: "2 nodes" },
  { id: "api1", label: "API·1", sub: "uvicorn:8000", x: 200, y: 215, type: "service", health: "ok", metric: "12ms" },
  { id: "api2", label: "API·2", sub: "uvicorn:8000", x: 500, y: 215, type: "service", health: "ok", metric: "14ms" },
  { id: "jwt", label: "JWT VALIDATOR", sub: "HS256 / 1ms", x: 265, y: 315, type: "security", health: "ok", metric: "0.8ms" },
  { id: "rl", label: "RATE LIMITER", sub: "FIXED_WINDOW", x: 435, y: 315, type: "security", health: "ok", metric: "Redis" },
  { id: "lock", label: "SQL AIRLOCK", sub: "7 stages active", x: 350, y: 400, type: "security", health: "ok", metric: "21ms" },
  { id: "pg", label: "POSTGRES", sub: "v16 primary", x: 235, y: 475, type: "data", health: "ok", metric: "23ms" },
  { id: "redis", label: "REDIS", sub: "v7-alpine", x: 465, y: 475, type: "data", health: "ok", metric: "0.4ms" },
];

const EDGES: TopologyEdge[] = [
  { id: "inet-lb", from: "inet", to: "lb" },
  { id: "lb-api1", from: "lb", to: "api1" },
  { id: "lb-api2", from: "lb", to: "api2" },
  { id: "api1-jwt", from: "api1", to: "jwt" },
  { id: "api2-jwt", from: "api2", to: "jwt" },
  { id: "api2-rl", from: "api2", to: "rl" },
  { id: "jwt-lock", from: "jwt", to: "lock" },
  { id: "rl-lock", from: "rl", to: "lock" },
  { id: "lock-pg", from: "lock", to: "pg" },
  { id: "rl-redis", from: "rl", to: "redis" },
];

const TYPE_CFG = {
  external: { stroke: "#64748b", fill: "rgba(100,116,139,0.1)", glow: "rgba(100,116,139,0.3)" },
  infra: { stroke: "#8b5cf6", fill: "rgba(139,92,246,0.1)", glow: "rgba(139,92,246,0.3)" },
  service: { stroke: "#00d4ff", fill: "rgba(0,212,255,0.1)", glow: "rgba(0,212,255,0.3)" },
  security: { stroke: "#10b981", fill: "rgba(16,185,129,0.1)", glow: "rgba(16,185,129,0.3)" },
  data: { stroke: "#f59e0b", fill: "rgba(245,158,11,0.1)", glow: "rgba(245,158,11,0.3)" },
};

const HEALTH_CFG = {
  ok: "#10b981",
  warn: "#f59e0b",
  err: "#ef4444",
};

const nodeMap = Object.fromEntries(NODES.map((n) => [n.id, n]));

/** Deterministic delay 0–max derived from a string, avoids Math.random() in render. */
function stableDelay(seed: string, max: number): number {
  const hash = seed.split("").reduce((a, c) => a + c.charCodeAt(0), 0);
  return (hash % (max * 100)) / 100;
}

function dist(a: TopologyNode, b: TopologyNode) {
  return Math.sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2);
}

interface ParticleProps {
  edge: TopologyEdge;
  phase: number;
  blocked?: boolean;
}

function EdgeParticle({ edge, phase, blocked }: ParticleProps) {
  const from = nodeMap[edge.from];
  const to = nodeMap[edge.to];
  if (!from || !to) return null;
  const d = dist(from, to);
  const speed = d / 120;
  const color = blocked ? "#ef4444" : "#00d4ff";

  return (
    <motion.circle
      r={blocked ? 2.5 : 1.8}
      fill={color}
      style={{ filter: `drop-shadow(0 0 3px ${color})` }}
      animate={{
        cx: [from.x, to.x],
        cy: [from.y, to.y],
        opacity: [0, 0, 1, 1, 0],
      }}
      transition={{
        duration: speed,
        delay: phase * speed,
        repeat: Infinity,
        ease: "linear",
        times: [0, 0.08, 0.2, 0.8, 1],
      }}
    />
  );
}

function AttackParticle({ path, blockAt }: { path: string[]; blockAt: string }) {
  const nodes = path.map((id) => nodeMap[id]);
  const blockIdx = path.indexOf(blockAt);
  if (blockIdx < 1) return null;
  const from = nodes[0];
  const to = nodes[blockIdx];
  if (!from || !to) return null;
  const d = dist(from, to);
  const seed = path[0] + blockAt;

  return (
    <>
      <motion.circle
        r={2.5}
        fill="#ef4444"
        style={{ filter: "drop-shadow(0 0 4px #ef4444)" }}
        animate={{
          cx: [from.x, to.x],
          cy: [from.y, to.y],
          opacity: [0, 0, 1, 1, 0],
        }}
        transition={{
          duration: d / 100,
          delay: stableDelay(seed, 3),
          repeat: Infinity,
          ease: "linear",
          times: [0, 0.05, 0.2, 0.85, 1],
        }}
      />
      {/* Burst at block node */}
      <motion.circle
        cx={to.x}
        cy={to.y}
        fill="none"
        stroke="#ef4444"
        strokeWidth={1}
        animate={{
          r: [0, 14, 20],
          opacity: [0, 0.8, 0],
        }}
        transition={{
          duration: d / 100,
          delay: stableDelay(seed + "burst", 3),
          repeat: Infinity,
          ease: "easeOut",
        }}
      />
    </>
  );
}

function RadarSweep({ cx, cy }: { cx: number; cy: number }) {
  return (
    <motion.g
      style={{ transformOrigin: `${cx}px ${cy}px` }}
      animate={{ rotate: [0, 360] }}
      transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
    >
      <defs>
        <linearGradient id="sweep-grad" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="rgba(0,212,255,0)" />
          <stop offset="100%" stopColor="rgba(0,212,255,0.12)" />
        </linearGradient>
      </defs>
      <line
        x1={cx}
        y1={cy}
        x2={cx}
        y2={cy - 300}
        stroke="rgba(0,212,255,0.25)"
        strokeWidth={1}
      />
      <path
        d={`M ${cx} ${cy} L ${cx - 25} ${cy - 300} L ${cx + 25} ${cy - 300} Z`}
        fill="rgba(0,212,255,0.04)"
      />
    </motion.g>
  );
}

function NodeShape({ node, selected, onClick }: {
  node: TopologyNode;
  selected: boolean;
  onClick: () => void;
}) {
  const cfg = TYPE_CFG[node.type];
  const r = node.type === "external" ? 20 : node.type === "security" ? 24 : 20;

  return (
    <g onClick={onClick} className="cursor-pointer" style={{ userSelect: "none" }}>
      {/* Outer glow ring */}
      {selected && (
        <motion.circle
          cx={node.x} cy={node.y}
          r={r + 12}
          fill="none"
          stroke={cfg.stroke}
          strokeWidth={1}
          strokeOpacity={0.4}
          animate={{ r: [r + 10, r + 16, r + 10] }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
        />
      )}

      {/* Pulse ring */}
      <motion.circle
        cx={node.x} cy={node.y}
        r={r}
        fill="none"
        stroke={cfg.stroke}
        strokeWidth={0.8}
        animate={{ r: [r, r + 8], opacity: [0.4, 0] }}
        transition={{ duration: 2.5, repeat: Infinity, ease: "easeOut", delay: stableDelay(node.id, 2) }}
      />

      {/* Filter glow */}
      <defs>
        <filter id={`glow-${node.id}`}>
          <feGaussianBlur stdDeviation={selected ? 4 : 2} result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Main node */}
      <circle
        cx={node.x} cy={node.y}
        r={r}
        fill={cfg.fill}
        stroke={cfg.stroke}
        strokeWidth={selected ? 1.5 : 1}
        filter={`url(#glow-${node.id})`}
      />

      {/* Inner node */}
      <circle cx={node.x} cy={node.y} r={r * 0.55} fill={cfg.fill} opacity={0.6} />

      {/* Health dot */}
      <circle
        cx={node.x + r - 4}
        cy={node.y - r + 4}
        r={3.5}
        fill={HEALTH_CFG[node.health]}
        style={{ filter: `drop-shadow(0 0 3px ${HEALTH_CFG[node.health]})` }}
      />

      {/* Label */}
      <text
        x={node.x}
        y={node.y + r + 12}
        textAnchor="middle"
        fontSize={8}
        fontFamily="'JetBrains Mono', 'Fira Code', monospace"
        fontWeight="700"
        fill={cfg.stroke}
        letterSpacing="0.06em"
      >
        {node.label}
      </text>
      <text
        x={node.x}
        y={node.y + r + 21}
        textAnchor="middle"
        fontSize={7}
        fontFamily="monospace"
        fill="rgba(255,255,255,0.3)"
      >
        {node.metric}
      </text>
    </g>
  );
}

export function SystemTopology() {
  const [selected, setSelected] = useState<string | null>(null);
  const [, setTick] = useState(0);
  const [clockTime, setClockTime] = useState("");

  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 4000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const tick = () =>
      setClockTime(new Date().toLocaleTimeString("en-US", { hour12: false }));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  const selectedNode = selected ? nodeMap[selected] : null;

  return (
    <div
      className="relative flex h-full w-full flex-col overflow-hidden rounded-2xl"
      style={{
        background: "radial-gradient(ellipse at 50% 30%, rgba(0,212,255,0.04) 0%, transparent 55%), #070b12",
        border: "1px solid rgba(255,255,255,0.06)",
        boxShadow: "0 0 0 1px rgba(255,255,255,0.03), 0 24px 64px rgba(0,0,0,0.6)",
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.05] shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="flex gap-1">
            {["#10b981", "#00d4ff", "#8b5cf6"].map((c) => (
              <span key={c} className="h-1.5 w-1.5 rounded-full" style={{ background: c, boxShadow: `0 0 4px ${c}` }} />
            ))}
          </div>
          <span className="font-mono text-[10px] font-bold uppercase tracking-[0.15em] text-ae-muted">
            SYSTEM TOPOLOGY
          </span>
        </div>
        <div className="flex items-center gap-3 text-[10px] font-mono text-ae-muted">
          <span className="text-ae-green">9 NODES HEALTHY</span>
          <span>·</span>
          <span>{clockTime}</span>
        </div>
      </div>

      {/* SVG canvas */}
      <div className="relative flex-1 overflow-hidden">
        {/* Grid overlay */}
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            backgroundImage: "linear-gradient(rgba(255,255,255,0.015) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.015) 1px, transparent 1px)",
            backgroundSize: "40px 40px",
          }}
        />

        <svg
          width="100%"
          height="100%"
          viewBox="0 0 700 520"
          preserveAspectRatio="xMidYMid meet"
          style={{ overflow: "visible" }}
        >
          <defs>
            <radialGradient id="topo-bg" cx="50%" cy="40%" r="50%">
              <stop offset="0%" stopColor="rgba(0,212,255,0.04)" />
              <stop offset="100%" stopColor="transparent" />
            </radialGradient>
          </defs>

          <rect width="700" height="520" fill="url(#topo-bg)" />

          {/* Radar sweep */}
          <RadarSweep cx={350} cy={260} />

          {/* Edges — base lines */}
          {EDGES.map((edge) => {
            const from = nodeMap[edge.from];
            const to = nodeMap[edge.to];
            if (!from || !to) return null;
            const isHighlighted =
              selected === edge.from || selected === edge.to;
            return (
              <line
                key={edge.id}
                x1={from.x} y1={from.y}
                x2={to.x} y2={to.y}
                stroke={isHighlighted ? "rgba(0,212,255,0.25)" : "rgba(255,255,255,0.06)"}
                strokeWidth={isHighlighted ? 1.5 : 1}
              />
            );
          })}

          {/* Data flow particles */}
          {EDGES.map((edge) =>
            [0, 0.38, 0.72].map((phase) => (
              <EdgeParticle
                key={`${edge.id}-${phase}`}
                edge={edge}
                phase={phase}
              />
            ))
          )}

          {/* Attack particles */}
          <AttackParticle path={["inet", "lb", "api2", "jwt"]} blockAt="jwt" />
          <AttackParticle path={["inet", "lb", "api1", "jwt", "lock"]} blockAt="lock" />
          <AttackParticle path={["inet", "lb", "api2", "rl"]} blockAt="rl" />

          {/* Nodes */}
          {NODES.map((node) => (
            <NodeShape
              key={node.id}
              node={node}
              selected={selected === node.id}
              onClick={() => setSelected(selected === node.id ? null : node.id)}
            />
          ))}
        </svg>

        {/* Selected node detail */}
        <AnimatePresence>
          {selectedNode && (
            <motion.div
              initial={{ opacity: 0, scale: 0.9, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 8 }}
              className="absolute bottom-4 left-4 w-52 rounded-xl border border-white/[0.08] bg-ae-elevated/95 p-3 backdrop-blur-sm"
              style={{ boxShadow: "0 0 0 1px rgba(0,212,255,0.15), 0 12px 40px rgba(0,0,0,0.5)" }}
            >
              <div className="flex items-center gap-2 mb-2">
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ background: TYPE_CFG[selectedNode.type].stroke, boxShadow: `0 0 6px ${TYPE_CFG[selectedNode.type].stroke}` }}
                />
                <span className="font-mono text-[10px] font-bold tracking-wider text-ae-text">
                  {selectedNode.label}
                </span>
              </div>
              <div className="space-y-1">
                <div className="flex justify-between text-[10px]">
                  <span className="text-ae-muted">TYPE</span>
                  <span className="font-mono text-ae-text">{selectedNode.type.toUpperCase()}</span>
                </div>
                <div className="flex justify-between text-[10px]">
                  <span className="text-ae-muted">STATUS</span>
                  <span className="font-mono text-ae-green">HEALTHY</span>
                </div>
                <div className="flex justify-between text-[10px]">
                  <span className="text-ae-muted">LATENCY</span>
                  <span className="font-mono text-ae-cyan">{selectedNode.metric}</span>
                </div>
                <div className="flex justify-between text-[10px]">
                  <span className="text-ae-muted">ID</span>
                  <span className="font-mono text-ae-muted">{selectedNode.id}</span>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Legend */}
        <div className="absolute bottom-4 right-4 flex flex-col gap-1">
          {Object.entries(TYPE_CFG).map(([type, cfg]) => (
            <div key={type} className="flex items-center gap-1.5 text-[9px]">
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: cfg.stroke }} />
              <span className="font-mono uppercase tracking-wider" style={{ color: cfg.stroke, opacity: 0.6 }}>
                {type}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

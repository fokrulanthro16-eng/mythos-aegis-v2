"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Shield, Hexagon, Cpu, Waves } from "lucide-react";
import { systemStatus } from "@/lib/mock-data";

function Counter({ end, duration = 1000 }: { end: number; duration?: number }) {
  const [val, setVal] = useState(0);

  useEffect(() => {
    const start = Date.now();
    const frame = () => {
      const elapsed = Date.now() - start;
      const p = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      setVal(Math.round(end * eased));
      if (p < 1) requestAnimationFrame(frame);
    };
    requestAnimationFrame(frame);
  }, [end, duration]);

  return <>{val.toLocaleString()}</>;
}

function PulseRing({ delay = 0, size = 60, color = "#00d4ff", opacity = 0.15 }: {
  delay?: number; size?: number; color?: string; opacity?: number;
}) {
  return (
    <motion.div
      className="absolute rounded-full border"
      style={{
        width: size,
        height: size,
        borderColor: color,
        left: "50%",
        top: "50%",
        marginLeft: -size / 2,
        marginTop: -size / 2,
      }}
      animate={{ scale: [1, 1.6], opacity: [opacity, 0] }}
      transition={{
        duration: 2.5,
        delay,
        repeat: Infinity,
        ease: "easeOut",
      }}
    />
  );
}

function FlowPulse() {
  return (
    <div className="relative mx-auto h-24 w-full max-w-xs">
      <svg width="100%" height="96" viewBox="0 0 320 96" preserveAspectRatio="xMidYMid meet">
        <defs>
          <linearGradient id="flow-grad" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="rgba(0,212,255,0)" />
            <stop offset="50%" stopColor="rgba(0,212,255,0.5)" />
            <stop offset="100%" stopColor="rgba(139,92,246,0.5)" />
          </linearGradient>
        </defs>
        {/* Base line */}
        <path d="M 20 48 Q 80 20 160 48 Q 240 76 300 48" stroke="rgba(255,255,255,0.06)" strokeWidth="1.5" fill="none" />
        {/* Animated glow line */}
        <motion.path
          d="M 20 48 Q 80 20 160 48 Q 240 76 300 48"
          stroke="url(#flow-grad)"
          strokeWidth="1.5"
          fill="none"
          strokeDasharray="40 20"
          animate={{ strokeDashoffset: [60, 0] }}
          transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
        />
        {/* Dots */}
        {[0.2, 0.5, 0.8].map((_t, i) => {
          return (
            <motion.circle
              key={i}
              r="2.5"
              fill="#00d4ff"
              animate={{
                cx: [20, 160, 300],
                cy: [48, 30, 48],
                opacity: [0, 1, 0],
              }}
              transition={{
                duration: 2,
                delay: i * 0.65,
                repeat: Infinity,
                ease: "easeInOut",
              }}
            />
          );
        })}
      </svg>
    </div>
  );
}

export function HeroStatusPanel() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="relative overflow-hidden rounded-2xl border border-white/[0.08] bg-ae-surface/40 p-8"
      style={{
        background: "linear-gradient(135deg, rgba(7,11,18,0.8) 0%, rgba(12,18,28,0.6) 100%)",
        boxShadow: "0 0 0 1px rgba(255,255,255,0.06), 0 24px 64px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.04)",
      }}
    >
      {/* Background effects */}
      <div className="pointer-events-none absolute inset-0">
        <div
          className="absolute inset-0"
          style={{
            background: "radial-gradient(ellipse at 20% 50%, rgba(0,212,255,0.06) 0%, transparent 55%), radial-gradient(ellipse at 80% 50%, rgba(139,92,246,0.04) 0%, transparent 45%)",
          }}
        />
      </div>

      <div className="relative flex flex-col gap-6">
        {/* Top row: title + status */}
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2.5 mb-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-ae-cyan/10 text-ae-cyan ring-1 ring-ae-cyan/20">
                <Hexagon size={16} strokeWidth={1.5} />
              </div>
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-ae-muted">
                  Mythos Aegis
                </div>
                <div className="text-[10px] text-ae-faint">v2.4.1 · prod</div>
              </div>
            </div>
            <h1
              className="text-3xl font-semibold leading-none tracking-tight text-ae-text"
              style={{ letterSpacing: "-0.02em" }}
            >
              Protecting{" "}
              <span className="text-glow-cyan gradient-text-cyan">
                {systemStatus.tenantsProtected} tenants
              </span>
            </h1>
            <p className="mt-1.5 text-sm text-ae-muted">
              All isolation guarantees active · 47 policies enforcing
            </p>
          </div>

          {/* Risk Score */}
          <div className="text-right">
            <div className="text-[10px] font-semibold uppercase tracking-widest text-ae-muted mb-1">
              Risk Score
            </div>
            <div className="relative inline-flex items-center justify-center">
              <div className="h-16 w-16 relative">
                <PulseRing size={64} color="#10b981" opacity={0.3} />
                <PulseRing size={64} color="#10b981" opacity={0.2} delay={0.8} />
                <div className="absolute inset-0 flex items-center justify-center rounded-full border border-ae-green/30 bg-ae-green/10">
                  <span className="font-mono text-lg font-bold text-ae-green">
                    <Counter end={systemStatus.riskScore} />
                  </span>
                </div>
              </div>
            </div>
            <div className="mt-1 text-[10px] text-ae-green">LOW RISK</div>
          </div>
        </div>

        {/* Metrics row */}
        <div className="grid grid-cols-4 gap-3">
          {[
            { label: "Requests / 24h", value: systemStatus.requestsLast24h, accent: "text-ae-cyan", icon: Waves },
            { label: "Avg Latency", value: `${systemStatus.avgLatencyMs}ms`, accent: "text-ae-violet", icon: Cpu },
            { label: "SQL Blocks Today", value: systemStatus.sqlBlocksToday, accent: "text-ae-amber", icon: Shield },
            { label: "Uptime", value: `${systemStatus.uptimePercent}%`, accent: "text-ae-green", icon: Shield },
          ].map((metric) => (
            <div
              key={metric.label}
              className="rounded-xl border border-white/[0.06] bg-ae-base/60 p-3"
            >
              <p className="text-[10px] font-medium uppercase tracking-widest text-ae-muted">
                {metric.label}
              </p>
              <p className={`mt-1 font-mono text-xl font-semibold ${metric.accent}`}>
                {typeof metric.value === "number" ? (
                  <Counter end={metric.value} duration={1200} />
                ) : (
                  metric.value
                )}
              </p>
            </div>
          ))}
        </div>

        {/* Request flow */}
        <div className="rounded-xl border border-white/[0.05] bg-ae-base/40 px-4 py-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-semibold uppercase tracking-widest text-ae-muted">
              Request Flow
            </span>
            <div className="flex items-center gap-1.5">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-ae-cyan opacity-50" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-ae-cyan" />
              </span>
              <span className="font-mono text-[10px] text-ae-cyan">LIVE</span>
            </div>
          </div>
          <FlowPulse />
        </div>
      </div>
    </motion.div>
  );
}

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowRight, Hexagon, Shield, Cpu, Lock } from "lucide-react";
import { systemStatus, tenants } from "@/lib/mock-data";

const BOOT_LINES = [
  "INITIALIZING SECURITY CORE …",
  "LOADING TENANT ISOLATION LAYER …",
  "ACTIVATING SQL AIRLOCK PIPELINE …",
  "JWT VALIDATOR ONLINE …",
  "RATE LIMITER ARMED …",
  "CONNECTING TO OBSERVABILITY MESH …",
  "ALL SYSTEMS NOMINAL — CLEARANCE GRANTED",
];

const HEALTH_COLOR: Record<string, string> = {
  healthy: "#10b981",
  degraded: "#f59e0b",
  critical: "#ef4444",
};

function BootSequence({ onComplete }: { onComplete: () => void }) {
  const [lines, setLines] = useState<string[]>([]);
  const [done, setDone] = useState(false);

  useEffect(() => {
    let i = 0;
    const id = setInterval(() => {
      if (i < BOOT_LINES.length) {
        setLines((prev) => [...prev, BOOT_LINES[i]]);
        i++;
      } else {
        clearInterval(id);
        setTimeout(() => {
          setDone(true);
          setTimeout(onComplete, 600);
        }, 400);
      }
    }, 240);
    return () => clearInterval(id);
  }, [onComplete]);

  return (
    <motion.div
      className="flex w-full max-w-lg flex-col gap-1 font-mono text-[11px]"
      exit={{ opacity: 0, y: -12 }}
      transition={{ duration: 0.4 }}
    >
      {lines.map((line, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.2 }}
          className="flex items-center gap-2"
        >
          <span className={i === lines.length - 1 && done ? "text-ae-green" : "text-ae-cyan/50"}>›</span>
          <span
            className={
              i === lines.length - 1 && done
                ? "text-ae-green"
                : "text-ae-muted"
            }
          >
            {line}
          </span>
        </motion.div>
      ))}
      {!done && (
        <motion.span
          className="inline-block h-3 w-2 bg-ae-cyan"
          animate={{ opacity: [1, 0, 1] }}
          transition={{ duration: 0.6, repeat: Infinity }}
        />
      )}
    </motion.div>
  );
}

export default function LandingPage() {
  const [booted, setBooted] = useState(false);

  return (
    <div
      className="relative flex min-h-screen items-center justify-center overflow-hidden"
      style={{
        background: "radial-gradient(ellipse at 50% -5%, rgba(0,212,255,0.14) 0%, transparent 52%), radial-gradient(ellipse at 85% 80%, rgba(139,92,246,0.07) 0%, transparent 45%), #010409",
      }}
    >
      {/* Hex grid */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage: "linear-gradient(rgba(255,255,255,0.018) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.018) 1px, transparent 1px)",
          backgroundSize: "56px 56px",
          maskImage: "radial-gradient(ellipse at center, black 30%, transparent 80%)",
          WebkitMaskImage: "radial-gradient(ellipse at center, black 30%, transparent 80%)",
        }}
      />

      {/* Scan line */}
      <motion.div
        className="pointer-events-none absolute left-0 right-0 h-px"
        style={{
          background: "linear-gradient(90deg, transparent, rgba(0,212,255,0.3), transparent)",
          zIndex: 1,
        }}
        animate={{ top: ["0%", "100%"] }}
        transition={{ duration: 6, repeat: Infinity, ease: "linear" }}
      />

      {/* Corner brackets */}
      {[
        ["top-8 left-8 border-t border-l", ""],
        ["top-8 right-8 border-t border-r", ""],
        ["bottom-8 left-8 border-b border-l", ""],
        ["bottom-8 right-8 border-b border-r", ""],
      ].map(([cls], i) => (
        <div
          key={i}
          className={`pointer-events-none absolute h-10 w-10 ${cls} border-ae-cyan/25`}
        />
      ))}

      <div className="relative z-10 flex w-full max-w-2xl flex-col items-center px-6 text-center">
        <AnimatePresence mode="wait">
          {!booted ? (
            <motion.div
              key="boot"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex flex-col items-center gap-6 w-full"
            >
              {/* Logo */}
              <motion.div
                className="flex h-16 w-16 items-center justify-center rounded-2xl"
                style={{
                  background: "rgba(0,212,255,0.06)",
                  border: "1px solid rgba(0,212,255,0.2)",
                  boxShadow: "0 0 40px rgba(0,212,255,0.12), inset 0 1px 0 rgba(255,255,255,0.06)",
                }}
                animate={{ boxShadow: ["0 0 40px rgba(0,212,255,0.12)", "0 0 60px rgba(0,212,255,0.24)", "0 0 40px rgba(0,212,255,0.12)"] }}
                transition={{ duration: 2, repeat: Infinity }}
              >
                <Hexagon size={26} strokeWidth={1.5} className="text-ae-cyan" />
              </motion.div>

              <div className="text-center mb-2">
                <p className="font-mono text-[9px] font-bold uppercase tracking-[0.3em] text-ae-muted mb-3">
                  SECURITY SYSTEM v2.4.1
                </p>
                <h1 className="text-4xl font-semibold tracking-tight text-ae-text" style={{ letterSpacing: "-0.02em" }}>
                  MYTHOS <span style={{
                    background: "linear-gradient(135deg, #00d4ff 0%, #8b5cf6 100%)",
                    WebkitBackgroundClip: "text",
                    WebkitTextFillColor: "transparent",
                    backgroundClip: "text",
                  }}>AEGIS</span>
                </h1>
              </div>

              {/* Boot sequence */}
              <BootSequence onComplete={() => setBooted(true)} />
            </motion.div>
          ) : (
            <motion.div
              key="ready"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="flex flex-col items-center gap-6"
            >
              {/* Logo */}
              <div
                className="flex h-16 w-16 items-center justify-center rounded-2xl"
                style={{
                  background: "rgba(0,212,255,0.08)",
                  border: "1px solid rgba(0,212,255,0.25)",
                  boxShadow: "0 0 40px rgba(0,212,255,0.15)",
                }}
              >
                <Hexagon size={26} strokeWidth={1.5} className="text-ae-cyan" />
              </div>

              {/* Status */}
              <div className="flex items-center gap-2">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-ae-green opacity-70" />
                  <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-ae-green" />
                </span>
                <span className="font-mono text-[10px] font-bold uppercase tracking-[0.2em] text-ae-green">
                  ALL SYSTEMS NOMINAL
                </span>
              </div>

              {/* Title */}
              <div>
                <p className="font-mono text-[9px] tracking-[0.3em] text-ae-muted mb-2">
                  ELITE SECURITY INFRASTRUCTURE CONSOLE
                </p>
                <h1 className="text-5xl font-semibold tracking-tight" style={{ letterSpacing: "-0.025em" }}>
                  <span className="text-ae-text">MYTHOS </span>
                  <span style={{
                    background: "linear-gradient(135deg, #00d4ff 0%, #8b5cf6 100%)",
                    WebkitBackgroundClip: "text",
                    WebkitTextFillColor: "transparent",
                    backgroundClip: "text",
                  }}>AEGIS</span>
                </h1>
              </div>

              {/* Stats grid */}
              <div className="flex w-full max-w-md divide-x divide-white/[0.06] rounded-xl border border-white/[0.07] bg-ae-surface/60">
                {[
                  { icon: Shield, v: `${systemStatus.tenantsProtected}`, label: "TENANTS" },
                  { icon: Lock, v: `${systemStatus.activePolicies}`, label: "POLICIES" },
                  { icon: Cpu, v: `${systemStatus.avgLatencyMs}ms`, label: "AVG LATENCY" },
                  { icon: Shield, v: `${systemStatus.uptimePercent}%`, label: "UPTIME" },
                ].map(({ v, label }) => (
                  <div key={label} className="flex flex-1 flex-col items-center py-3">
                    <span className="font-mono text-lg font-semibold text-ae-cyan">{v}</span>
                    <span className="font-mono text-[8px] tracking-widest text-ae-muted">{label}</span>
                  </div>
                ))}
              </div>

              {/* Tenant status */}
              <div className="flex items-center gap-2.5">
                {tenants.map((t) => (
                  <div key={t.id} className="flex items-center gap-1.5 rounded-full border border-white/[0.07] bg-ae-surface/40 px-2.5 py-1">
                    <div className="h-1.5 w-1.5 rounded-full" style={{ background: HEALTH_COLOR[t.health] }} />
                    <span className="font-mono text-[9px] text-ae-muted">{t.name}</span>
                  </div>
                ))}
              </div>

              {/* CTA */}
              <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
                <Link
                  href="/console"
                  className="group flex items-center gap-3 rounded-xl px-8 py-3 font-mono text-sm font-bold tracking-wider text-ae-base"
                  style={{
                    background: "linear-gradient(135deg, #00d4ff 0%, #0891b2 100%)",
                    boxShadow: "0 0 30px rgba(0,212,255,0.3), 0 4px 16px rgba(0,0,0,0.4)",
                  }}
                >
                  ENTER COMMAND CENTER
                  <ArrowRight size={15} className="transition-transform group-hover:translate-x-1" />
                </Link>
              </motion.div>

              <p className="font-mono text-[10px] text-ae-muted">
                PRESS <kbd className="rounded border border-white/10 bg-white/[0.04] px-1.5 py-0.5">⌘ K</kbd> FOR COMMAND PALETTE
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

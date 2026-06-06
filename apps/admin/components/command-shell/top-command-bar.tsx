"use client";

import { useState, useEffect } from "react";
import { usePathname } from "next/navigation";
import { Search, Zap } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { systemStatus } from "@/lib/mock-data";

interface TopCommandBarProps {
  onOpenPalette: () => void;
}

const BREADCRUMBS: Record<string, string[]> = {
  "/console": ["Mythos Aegis", "Command Center"],
  "/console/airlock": ["Mythos Aegis", "SQL Airlock"],
  "/console/security": ["Mythos Aegis", "Security Events"],
  "/console/tenants": ["Mythos Aegis", "Tenant Intelligence"],
  "/console/observability": ["Mythos Aegis", "Observability"],
  "/console/settings": ["Mythos Aegis", "Settings"],
};

function LiveClock() {
  const [time, setTime] = useState("");

  useEffect(() => {
    const tick = () => {
      setTime(
        new Date().toLocaleTimeString("en-US", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: false,
          timeZoneName: "short",
        })
      );
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <span className="font-mono text-xs tracking-wider text-ae-muted">{time}</span>
  );
}

export function TopCommandBar({ onOpenPalette }: TopCommandBarProps) {
  const pathname = usePathname();
  const breadcrumbs = BREADCRUMBS[pathname] ?? ["Mythos Aegis"];

  return (
    <header className="flex h-12 items-center justify-between border-b border-white/[0.06] bg-ae-surface/80 px-4 backdrop-blur-sm">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2">
        {breadcrumbs.map((crumb, i) => (
          <span key={crumb} className="flex items-center gap-2">
            {i > 0 && (
              <span className="text-ae-faint">/</span>
            )}
            <span
              className={
                i === breadcrumbs.length - 1
                  ? "text-sm font-medium text-ae-text"
                  : "text-sm text-ae-muted"
              }
            >
              {crumb}
            </span>
          </span>
        ))}
      </div>

      {/* Command search */}
      <button
        onClick={onOpenPalette}
        className="group flex items-center gap-2.5 rounded-lg border border-white/[0.07] bg-white/[0.02] px-3 py-1.5 text-xs text-ae-muted transition-all hover:border-white/[0.12] hover:bg-white/[0.04] hover:text-ae-text"
      >
        <Search size={13} />
        <span className="hidden sm:inline">Search or run command</span>
        <span className="hidden items-center gap-1 sm:flex">
          <kbd className="rounded border border-white/10 bg-white/[0.04] px-1.5 py-0.5 font-mono text-[10px] text-ae-faint">
            ⌘
          </kbd>
          <kbd className="rounded border border-white/10 bg-white/[0.04] px-1.5 py-0.5 font-mono text-[10px] text-ae-faint">
            K
          </kbd>
        </span>
      </button>

      {/* Right controls */}
      <div className="flex items-center gap-4">
        <LiveClock />

        {/* System status pill */}
        <AnimatePresence mode="wait">
          <motion.div
            key={systemStatus.overall}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex items-center gap-1.5 rounded-full border border-ae-green/25 bg-ae-green/10 px-2.5 py-1"
          >
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-ae-green opacity-60" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-ae-green" />
            </span>
            <span className="text-[10px] font-semibold uppercase tracking-wider text-ae-green">
              Operational
            </span>
          </motion.div>
        </AnimatePresence>

        {/* Risk score */}
        <div className="flex items-center gap-1.5">
          <Zap size={12} className="text-ae-amber" />
          <span className="text-xs text-ae-muted">
            Risk{" "}
            <span className="font-mono font-semibold text-ae-amber">
              {systemStatus.riskScore}
            </span>
          </span>
        </div>
      </div>
    </header>
  );
}

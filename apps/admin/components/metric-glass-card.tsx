"use client";

import { useEffect, useState, useRef } from "react";
import { motion } from "framer-motion";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import {
  AreaChart,
  Area,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { cn } from "@/lib/utils";

interface MetricGlassCardProps {
  label: string;
  value: number | string;
  unit?: string;
  change?: number;
  changeLabel?: string;
  sparkline?: number[];
  accent?: "cyan" | "violet" | "amber" | "green" | "red";
  className?: string;
  prefix?: string;
}

const ACCENT_CONFIG = {
  cyan: {
    text: "text-ae-cyan",
    gradient: "from-ae-cyan/20 to-transparent",
    stroke: "#00d4ff",
    fill: "rgba(0,212,255,0.12)",
    border: "hover:border-ae-cyan/30",
  },
  violet: {
    text: "text-ae-violet",
    gradient: "from-ae-violet/20 to-transparent",
    stroke: "#8b5cf6",
    fill: "rgba(139,92,246,0.12)",
    border: "hover:border-ae-violet/30",
  },
  amber: {
    text: "text-ae-amber",
    gradient: "from-ae-amber/20 to-transparent",
    stroke: "#f59e0b",
    fill: "rgba(245,158,11,0.12)",
    border: "hover:border-ae-amber/30",
  },
  green: {
    text: "text-ae-green",
    gradient: "from-ae-green/20 to-transparent",
    stroke: "#10b981",
    fill: "rgba(16,185,129,0.12)",
    border: "hover:border-ae-green/30",
  },
  red: {
    text: "text-ae-red",
    gradient: "from-ae-red/20 to-transparent",
    stroke: "#ef4444",
    fill: "rgba(239,68,68,0.12)",
    border: "hover:border-ae-red/30",
  },
};

function AnimatedNumber({ value }: { value: number }) {
  const [displayed, setDisplayed] = useState(0);
  const startRef = useRef(Date.now());

  useEffect(() => {
    const start = 0;
    const end = value;
    const duration = 900;
    startRef.current = Date.now();

    const frame = () => {
      const elapsed = Date.now() - startRef.current;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayed(Math.round(start + (end - start) * eased));
      if (progress < 1) requestAnimationFrame(frame);
    };
    requestAnimationFrame(frame);
  }, [value]);

  return <>{displayed.toLocaleString()}</>;
}

export function MetricGlassCard({
  label,
  value,
  unit,
  change,
  changeLabel,
  sparkline,
  accent = "cyan",
  className,
  prefix,
}: MetricGlassCardProps) {
  const cfg = ACCENT_CONFIG[accent];
  const sparkData = sparkline?.map((v, i) => ({ i, v }));

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={cn(
        "group relative overflow-hidden rounded-xl border border-white/[0.07] bg-ae-surface/60 p-4 transition-all duration-300",
        cfg.border,
        className
      )}
    >
      {/* Background gradient */}
      <div
        className={cn(
          "pointer-events-none absolute inset-0 bg-gradient-to-br opacity-0 transition-opacity group-hover:opacity-100",
          cfg.gradient
        )}
      />

      {/* Label */}
      <p className="mb-1.5 text-[11px] font-medium uppercase tracking-widest text-ae-muted">
        {label}
      </p>

      {/* Value */}
      <div className="flex items-baseline gap-1">
        {prefix && (
          <span className={cn("text-sm font-semibold", cfg.text)}>{prefix}</span>
        )}
        <span className="font-sans text-2xl font-semibold tracking-tight text-ae-text">
          {typeof value === "number" ? <AnimatedNumber value={value} /> : value}
        </span>
        {unit && (
          <span className="text-sm text-ae-muted">{unit}</span>
        )}
      </div>

      {/* Change indicator */}
      {change !== undefined && (
        <div className="mt-1 flex items-center gap-1">
          {change > 0 ? (
            <TrendingUp size={11} className="text-ae-green" />
          ) : change < 0 ? (
            <TrendingDown size={11} className="text-ae-red" />
          ) : (
            <Minus size={11} className="text-ae-muted" />
          )}
          <span
            className={cn(
              "text-[11px] font-medium",
              change > 0 ? "text-ae-green" : change < 0 ? "text-ae-red" : "text-ae-muted"
            )}
          >
            {change > 0 ? "+" : ""}{change}%
          </span>
          {changeLabel && (
            <span className="text-[11px] text-ae-muted">{changeLabel}</span>
          )}
        </div>
      )}

      {/* Sparkline */}
      {sparkData && sparkData.length > 0 && (
        <div className="mt-3 h-10">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={sparkData} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id={`spark-${accent}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={cfg.stroke} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={cfg.stroke} stopOpacity={0} />
                </linearGradient>
              </defs>
              <Tooltip content={() => null} />
              <Area
                type="monotone"
                dataKey="v"
                stroke={cfg.stroke}
                strokeWidth={1.5}
                fill={`url(#spark-${accent})`}
                dot={false}
                activeDot={{ r: 2, fill: cfg.stroke }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </motion.div>
  );
}

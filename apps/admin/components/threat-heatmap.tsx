"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";

const CATEGORIES = [
  { id: "jwt", label: "JWT FAIL" },
  { id: "rbac", label: "RBAC DENY" },
  { id: "sql", label: "SQL BLOCK" },
  { id: "rate", label: "RATE LIMIT" },
  { id: "iso", label: "ISOLATION" },
  { id: "secret", label: "KEY EVENT" },
];

const HOURS = 24;

// Intensity 0-1 → color
function intensityToColor(v: number): string {
  if (v < 0.01) return "rgba(255,255,255,0.03)";
  if (v < 0.25) return `rgba(0,212,255,${0.1 + v * 0.6})`;
  if (v < 0.6) return `rgba(245,158,11,${0.2 + v * 0.5})`;
  return `rgba(239,68,68,${0.3 + v * 0.6})`;
}

function generateHeatmapData() {
  return CATEGORIES.map((cat) =>
    Array.from({ length: HOURS }, (_, h) => {
      const age = HOURS - h; // 0 = current hour
      const base =
        cat.id === "sql" ? 0.55 : cat.id === "rbac" ? 0.45 : cat.id === "jwt" ? 0.38 : 0.2;
      const spike = age === 1 || age === 2 ? 0.3 : 0;
      const noise = Math.random() * 0.2;
      const decay = age * 0.012;
      return Math.max(0, Math.min(1, base + spike + noise - decay));
    })
  );
}

const EMPTY_DATA = CATEGORIES.map(() => Array<number>(HOURS).fill(0));

export function ThreatHeatmap() {
  const [data, setData] = useState<number[][]>(EMPTY_DATA);
  const [hovered, setHovered] = useState<{ row: number; col: number } | null>(null);

  useEffect(() => {
    // Populate with random data after mount to avoid SSR mismatch.
    setData(generateHeatmapData());

    const id = setInterval(() => {
      setData((prev) =>
        prev.map((row) => {
          const updated = [...row];
          updated[HOURS - 1] = Math.max(0, Math.min(1, updated[HOURS - 1] + (Math.random() - 0.5) * 0.15));
          return updated;
        })
      );
    }, 2500);
    return () => clearInterval(id);
  }, []);

  const cellW = 8;
  const cellH = 18;

  return (
    <div
      className="flex h-full flex-col overflow-hidden rounded-xl"
      style={{
        background: "rgba(7,11,18,0.8)",
        border: "1px solid rgba(255,255,255,0.06)",
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/[0.05] px-3 py-2.5 shrink-0">
        <span className="font-mono text-[9px] font-bold uppercase tracking-[0.18em] text-ae-muted">
          THREAT HEATMAP
        </span>
        <div className="flex items-center gap-1.5">
          <span className="h-1 w-1 rounded-full bg-ae-red" style={{ boxShadow: "0 0 4px #ef4444" }} />
          <span className="font-mono text-[9px] text-ae-red">HIGH</span>
          <span className="h-1 w-1 rounded-full bg-ae-amber" />
          <span className="font-mono text-[9px] text-ae-amber">MED</span>
          <span className="h-1 w-1 rounded-full bg-ae-cyan opacity-60" />
          <span className="font-mono text-[9px] text-ae-muted">LOW</span>
        </div>
      </div>

      {/* Grid */}
      <div className="flex-1 overflow-hidden p-3">
        <div className="flex flex-col gap-[3px]">
          {CATEGORIES.map((cat, rowIdx) => (
            <div key={cat.id} className="flex items-center gap-1.5">
              {/* Category label */}
              <span className="w-14 shrink-0 text-right font-mono text-[8px] font-semibold tracking-wider text-ae-muted">
                {cat.label}
              </span>

              {/* Cells */}
              <div className="flex gap-[2px]">
                {data[rowIdx].map((val, col) => {
                  const isCurrent = col === HOURS - 1;
                  return (
                    <motion.div
                      key={col}
                      className="cursor-default rounded-[1px]"
                      style={{
                        width: cellW,
                        height: cellH,
                        background: intensityToColor(val),
                        outline: isCurrent ? "1px solid rgba(0,212,255,0.3)" : "none",
                        outlineOffset: "1px",
                      }}
                      animate={{ background: intensityToColor(val) }}
                      transition={{ duration: 0.6 }}
                      onMouseEnter={() => setHovered({ row: rowIdx, col })}
                      onMouseLeave={() => setHovered(null)}
                    />
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {/* Hour axis */}
        <div className="flex items-center gap-[2px] mt-1.5 pl-[62px]">
          {Array.from({ length: HOURS }, (_, i) =>
            i % 6 === 0 ? (
              <span
                key={i}
                className="font-mono text-[7px] text-ae-muted"
                style={{ width: cellW * 6 + 5 * 2, textAlign: "center" }}
              >
                -{HOURS - 1 - i}h
              </span>
            ) : null
          )}
          <span className="font-mono text-[7px] text-ae-cyan" style={{ width: cellW, textAlign: "center" }}>
            NOW
          </span>
        </div>

        {/* Tooltip */}
        {hovered && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-2 rounded-lg border border-white/[0.08] bg-ae-elevated px-2 py-1.5"
          >
            <span className="font-mono text-[9px] text-ae-muted">
              {CATEGORIES[hovered.row].label} · -{HOURS - 1 - hovered.col}h ·{" "}
            </span>
            <span
              className="font-mono text-[9px] font-bold"
              style={{ color: intensityToColor(data[hovered.row][hovered.col]) }}
            >
              {(data[hovered.row][hovered.col] * 100).toFixed(0)}%
            </span>
          </motion.div>
        )}
      </div>
    </div>
  );
}

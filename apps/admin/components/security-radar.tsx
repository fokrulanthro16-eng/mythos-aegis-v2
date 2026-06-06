"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { threatData } from "@/lib/mock-data";

const CX = 180;
const CY = 180;
const MAX_R = 130;
const RINGS = [0.2, 0.4, 0.6, 0.8, 1.0];
const AXES = threatData.map((d, i) => ({
  ...d,
  angle: ((i * 360) / threatData.length - 90) * (Math.PI / 180),
}));

function polar(angle: number, r: number) {
  return {
    x: CX + r * Math.cos(angle),
    y: CY + r * Math.sin(angle),
  };
}

function polygonPoints(animated: boolean) {
  return AXES.map((ax) => {
    const r = animated ? (ax.value / 100) * MAX_R : 0;
    const p = polar(ax.angle, r);
    return `${p.x},${p.y}`;
  }).join(" ");
}

function hexagonPoints(fraction: number) {
  return AXES.map((ax) => {
    const p = polar(ax.angle, fraction * MAX_R);
    return `${p.x},${p.y}`;
  }).join(" ");
}

export function SecurityRadar() {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const id = setTimeout(() => setReady(true), 300);
    return () => clearTimeout(id);
  }, []);

  return (
    <div className="relative overflow-hidden rounded-2xl border border-white/[0.07] bg-ae-surface/40 p-5"
      style={{ boxShadow: "0 0 0 1px rgba(255,255,255,0.05), 0 16px 48px rgba(0,0,0,0.4)" }}
    >
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-ae-text">Threat Radar</h3>
          <p className="text-[11px] text-ae-muted">Last 24 hours · All tenants</p>
        </div>
        <div className="flex items-center gap-1.5 rounded-full border border-ae-red/20 bg-ae-red/10 px-2.5 py-1">
          <span className="h-1.5 w-1.5 rounded-full bg-ae-red" />
          <span className="text-[10px] font-semibold text-ae-red">3 ACTIVE</span>
        </div>
      </div>

      <div className="flex items-center gap-4">
        {/* SVG Radar */}
        <div className="flex-shrink-0">
          <svg width={360} height={360} viewBox="0 0 360 360">
            <defs>
              <radialGradient id="radar-center" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="rgba(0,212,255,0.08)" />
                <stop offset="100%" stopColor="transparent" />
              </radialGradient>
              <filter id="radar-glow">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            {/* Center glow */}
            <circle cx={CX} cy={CY} r={MAX_R} fill="url(#radar-center)" />

            {/* Concentric rings */}
            {RINGS.map((fraction, i) => (
              <polygon
                key={i}
                points={hexagonPoints(fraction)}
                fill="none"
                stroke="rgba(255,255,255,0.05)"
                strokeWidth={1}
              />
            ))}

            {/* Ring labels */}
            {[20, 40, 60, 80].map((val) => (
              <text
                key={val}
                x={CX + 4}
                y={CY - (val / 100) * MAX_R + 4}
                fill="rgba(255,255,255,0.2)"
                fontSize="9"
                fontFamily="monospace"
              >
                {val}
              </text>
            ))}

            {/* Axis lines */}
            {AXES.map((ax, i) => {
              const end = polar(ax.angle, MAX_R);
              return (
                <line
                  key={i}
                  x1={CX}
                  y1={CY}
                  x2={end.x}
                  y2={end.y}
                  stroke="rgba(255,255,255,0.06)"
                  strokeWidth={1}
                />
              );
            })}

            {/* Threat polygon */}
            <motion.polygon
              points={polygonPoints(ready)}
              fill="rgba(0,212,255,0.08)"
              stroke="#00d4ff"
              strokeWidth={1.5}
              strokeLinejoin="round"
              filter="url(#radar-glow)"
              initial={{ opacity: 0, scale: 0.3 }}
              animate={{ opacity: 1, scale: 1 }}
              style={{ transformOrigin: `${CX}px ${CY}px` }}
              transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1], delay: 0.3 }}
            />

            {/* Inner threat fill */}
            <motion.polygon
              points={polygonPoints(ready)}
              fill="rgba(139,92,246,0.05)"
              stroke="none"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.8, delay: 0.5 }}
            />

            {/* Data points */}
            {AXES.map((ax, i) => {
              const r = (ax.value / 100) * MAX_R;
              const pt = polar(ax.angle, r);
              return (
                <motion.circle
                  key={i}
                  cx={pt.x}
                  cy={pt.y}
                  r={3.5}
                  fill="#00d4ff"
                  stroke="rgba(0,212,255,0.4)"
                  strokeWidth={4}
                  initial={{ opacity: 0, scale: 0 }}
                  animate={{ opacity: 1, scale: 1 }}
                  style={{ transformOrigin: `${pt.x}px ${pt.y}px` }}
                  transition={{ duration: 0.3, delay: 0.6 + i * 0.08 }}
                />
              );
            })}

            {/* Axis labels */}
            {AXES.map((ax, i) => {
              const labelR = MAX_R + 20;
              const pt = polar(ax.angle, labelR);
              const anchor =
                Math.abs(Math.cos(ax.angle)) < 0.1
                  ? "middle"
                  : Math.cos(ax.angle) > 0
                  ? "start"
                  : "end";

              return (
                <text
                  key={i}
                  x={pt.x}
                  y={pt.y}
                  textAnchor={anchor}
                  dominantBaseline="middle"
                  fontSize="10"
                  fill="rgba(255,255,255,0.45)"
                  fontFamily="system-ui, sans-serif"
                  fontWeight="500"
                >
                  {ax.category}
                </text>
              );
            })}
          </svg>
        </div>

        {/* Legend */}
        <div className="flex flex-col gap-2.5 min-w-0 flex-1">
          {threatData.map((item, i) => (
            <motion.div
              key={item.category}
              initial={{ opacity: 0, x: 12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.4 + i * 0.07 }}
              className="flex items-center justify-between gap-3"
            >
              <div className="flex items-center gap-2 min-w-0">
                <div
                  className="h-1.5 w-1.5 shrink-0 rounded-full bg-ae-cyan"
                  style={{ opacity: 0.4 + (item.value / 100) * 0.6 }}
                />
                <span className="text-[11px] text-ae-muted truncate">{item.category}</span>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className="font-mono text-xs font-semibold text-ae-text">
                  {item.count}
                </span>
                <div className="h-1 w-16 overflow-hidden rounded-full bg-ae-base">
                  <motion.div
                    className="h-full rounded-full bg-ae-cyan"
                    initial={{ width: 0 }}
                    animate={{ width: `${item.value}%` }}
                    transition={{ duration: 0.7, delay: 0.5 + i * 0.07, ease: "easeOut" }}
                  />
                </div>
                <span className="font-mono text-[10px] text-ae-muted w-7 text-right">
                  {item.value}%
                </span>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}

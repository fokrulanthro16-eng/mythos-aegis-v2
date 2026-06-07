"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface RiskFactor {
  label: string;
  score: number;
  delta: number;
  source: string;
}

const FACTORS: RiskFactor[] = [
  { label: "JWT failure rate", score: 72, delta: +8, source: "beta tenant" },
  { label: "SQL injection attempts", score: 61, delta: -3, source: "airlock stage 2" },
  { label: "RBAC denial frequency", score: 54, delta: +14, source: "analytics.write" },
  { label: "Rate limit pressure", score: 38, delta: -6, source: "WRITE_MUTATION" },
  { label: "Cross-tenant probes", score: 29, delta: 0, source: "isolation layer" },
];

// Forecast: 6-hour predicted risk
const FORECAST = [24, 22, 25, 29, 34, 38, 41];

// Module-level constants — computed once, identical on server and client
const GAUGE_R = 42;
const GAUGE_CX = 52;
const GAUGE_CY = 52;
const GAUGE_START = -220 * (Math.PI / 180);
const GAUGE_SWEEP = 240 * (Math.PI / 180);

// Coordinates rounded to 4 dp so the serialized string is byte-for-byte
// identical between Node.js SSR and browser, preventing hydration mismatches.
function buildArcPath(sweepFraction: number): string {
  const sweep = sweepFraction * GAUGE_SWEEP;
  const end = GAUGE_START + sweep;
  const x1 = (GAUGE_CX + GAUGE_R * Math.cos(GAUGE_START)).toFixed(4);
  const y1 = (GAUGE_CY + GAUGE_R * Math.sin(GAUGE_START)).toFixed(4);
  const x2 = (GAUGE_CX + GAUGE_R * Math.cos(end)).toFixed(4);
  const y2 = (GAUGE_CY + GAUGE_R * Math.sin(end)).toFixed(4);
  const large = Math.abs(sweep) > Math.PI ? 1 : 0;
  return `M ${x1} ${y1} A ${GAUGE_R} ${GAUGE_R} 0 ${large} 1 ${x2} ${y2}`;
}

const TRACK_PATH = buildArcPath(1); // Full 240° track — precomputed at module load

function RiskGauge({ score }: { score: number }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);

  // Deterministic: integer score (10-90) only — no browser globals in render path
  const fillPath = buildArcPath(score / 100);

  const scoreColor = score < 30 ? "#10b981" : score < 60 ? "#f59e0b" : "#ef4444";
  const label = score < 30 ? "LOW RISK" : score < 60 ? "MODERATE" : "HIGH RISK";

  return (
    <div className="flex items-center gap-4">
      <svg width={104} height={104}>
        <defs>
          <filter id="gauge-glow">
            <feGaussianBlur stdDeviation={3} result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        {/* Track */}
        <path
          d={TRACK_PATH}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={5}
          strokeLinecap="round"
        />
        {/* Fill — client-only animation prevents SSR/hydration d-attribute mismatch */}
        {mounted ? (
          <motion.path
            d={fillPath}
            fill="none"
            stroke={scoreColor}
            strokeWidth={5}
            strokeLinecap="round"
            filter="url(#gauge-glow)"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 1.2, ease: "easeOut" }}
          />
        ) : (
          <path
            d={fillPath}
            fill="none"
            stroke={scoreColor}
            strokeWidth={5}
            strokeLinecap="round"
            filter="url(#gauge-glow)"
          />
        )}
        {/* Score text */}
        <text
          x={GAUGE_CX}
          y={GAUGE_CY}
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize={20}
          fontFamily="monospace"
          fontWeight="700"
          fill={scoreColor}
          style={{ filter: `drop-shadow(0 0 6px ${scoreColor})` }}
        >
          {score}
        </text>
        <text
          x={GAUGE_CX}
          y={GAUGE_CY + 14}
          textAnchor="middle"
          fontSize={7}
          fontFamily="monospace"
          fill="rgba(255,255,255,0.35)"
          letterSpacing="0.08em"
        >
          /100
        </text>
      </svg>

      <div>
        <p
          className="font-mono text-xs font-bold"
          style={{ color: scoreColor, textShadow: `0 0 8px ${scoreColor}` }}
        >
          {label}
        </p>
        <p className="mt-0.5 font-mono text-[9px] text-ae-muted">COMPOSITE SCORE</p>
        <p className="mt-2 font-mono text-[9px] text-ae-muted">
          MODEL CONFIDENCE{" "}
          <span className="text-ae-cyan">87%</span>
        </p>
        <p className="font-mono text-[9px] text-ae-muted">
          UPDATED{" "}
          <span className="text-ae-text">30s ago</span>
        </p>
      </div>
    </div>
  );
}

function ForecastMini() {
  const max = Math.max(...FORECAST);
  const w = 100;
  const h = 32;

  const pts = FORECAST.map((v, i) => {
    const x = (i / (FORECAST.length - 1)) * w;
    const y = h - (v / max) * (h - 4);
    return `${x},${y}`;
  }).join(" ");

  return (
    <div>
      <p className="mb-1.5 font-mono text-[9px] text-ae-muted">6-HOUR FORECAST</p>
      <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} overflow="visible">
        <defs>
          <linearGradient id="forecast-grad" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#10b981" />
            <stop offset="60%" stopColor="#f59e0b" />
            <stop offset="100%" stopColor="#ef4444" />
          </linearGradient>
        </defs>
        <polyline
          points={pts}
          fill="none"
          stroke="url(#forecast-grad)"
          strokeWidth={1.5}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {/* NOW marker */}
        <circle cx={0} cy={h - (FORECAST[0] / max) * (h - 4)} r={2.5} fill="#10b981" />
        {/* +6h marker */}
        <circle
          cx={w}
          cy={h - (FORECAST[FORECAST.length - 1] / max) * (h - 4)}
          r={2.5}
          fill="#ef4444"
          style={{ filter: "drop-shadow(0 0 3px #ef4444)" }}
        />
        <text x={w - 2} y={h + 10} textAnchor="end" fontSize={7} fontFamily="monospace" fill="#ef4444">
          +{FORECAST[FORECAST.length - 1]}
        </text>
      </svg>
    </div>
  );
}

export function RiskPrediction() {
  const [score, setScore] = useState(24);

  useEffect(() => {
    const id = setInterval(() => {
      setScore((s) => Math.max(10, Math.min(90, s + (Math.random() - 0.45) * 4)));
    }, 5000);
    return () => clearInterval(id);
  }, []);

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
          AI RISK ENGINE
        </span>
        <div className="flex items-center gap-1">
          <motion.div
            className="h-1 w-1 rounded-full bg-ae-violet"
            animate={{ opacity: [1, 0.3, 1] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          />
          <span className="font-mono text-[9px] text-ae-violet">LIVE</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-3">
        {/* Gauge */}
        <RiskGauge score={Math.round(score)} />

        {/* Forecast */}
        <ForecastMini />

        {/* Risk factors */}
        <div>
          <p className="mb-1.5 font-mono text-[9px] text-ae-muted">TOP RISK FACTORS</p>
          <div className="flex flex-col gap-1.5">
            {FACTORS.map((factor, i) => (
              <motion.div
                key={factor.label}
                initial={{ opacity: 0, x: 8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.06 }}
                className="group"
              >
                <div className="flex items-center justify-between mb-0.5">
                  <span className="font-mono text-[9px] text-ae-muted group-hover:text-ae-text transition-colors truncate pr-2">
                    {factor.label}
                  </span>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <span
                      className={`font-mono text-[9px] font-bold ${
                        factor.delta > 0 ? "text-ae-red" : factor.delta < 0 ? "text-ae-green" : "text-ae-muted"
                      }`}
                    >
                      {factor.delta > 0 ? "▲" : factor.delta < 0 ? "▼" : "–"}
                      {Math.abs(factor.delta)}
                    </span>
                    <span className="font-mono text-[9px] text-ae-text">{factor.score}</span>
                  </div>
                </div>
                <div className="h-[3px] w-full rounded-full bg-white/[0.05] overflow-hidden">
                  <motion.div
                    className="h-full rounded-full"
                    style={{
                      background:
                        factor.score > 60
                          ? "#ef4444"
                          : factor.score > 40
                          ? "#f59e0b"
                          : "#00d4ff",
                    }}
                    initial={{ width: 0 }}
                    animate={{ width: `${factor.score}%` }}
                    transition={{ duration: 0.8, delay: 0.3 + i * 0.06 }}
                  />
                </div>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Anomaly alert */}
        <AnimatePresence>
          {score > 35 && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="rounded-lg border border-ae-amber/30 bg-ae-amber/10 px-2.5 py-2"
            >
              <div className="flex items-center gap-1.5">
                <motion.span
                  className="h-1.5 w-1.5 rounded-full bg-ae-amber"
                  animate={{ opacity: [1, 0.3, 1] }}
                  transition={{ duration: 0.8, repeat: Infinity }}
                />
                <span className="font-mono text-[9px] font-bold text-ae-amber">ANOMALY DETECTED</span>
              </div>
              <p className="mt-0.5 font-mono text-[9px] text-ae-amber/70">
                RBAC denial rate 2.4× above baseline. Model predicts escalation within 2h.
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

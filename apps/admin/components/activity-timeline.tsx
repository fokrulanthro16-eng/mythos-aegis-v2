"use client";

import { useEffect, useState } from "react";
import { securityEvents, type SecurityEvent } from "@/lib/mock-data";

const TYPE_CFG = {
  jwt_failure:    { color: "#ef4444", symbol: "⊗", lane: 0 },
  rbac_denial:    { color: "#f59e0b", symbol: "⊘", lane: 1 },
  sql_block:      { color: "#8b5cf6", symbol: "⊟", lane: 2 },
  rate_limit:     { color: "#00d4ff", symbol: "⊕", lane: 3 },
  health_change:  { color: "#10b981", symbol: "⊙", lane: 4 },
  secret_rotation:{ color: "#8b5cf6", symbol: "⊛", lane: 4 },
  tenant_isolation:{ color: "#ef4444", symbol: "⊠", lane: 0 },
  auth_success:   { color: "#10b981", symbol: "⊜", lane: 4 },
} as const;

const WINDOW_MS = 2 * 60 * 60 * 1000;
const LANES = 5;
const LANE_H = 16;
const PAD_TOP = 6;
const W = 960;
const SVG_H = PAD_TOP + LANES * LANE_H + 20;

export function ActivityTimeline() {
  const [events, setEvents] = useState<SecurityEvent[]>(securityEvents);
  const [hovered, setHovered] = useState<string | null>(null);
  const [now, setNow] = useState(0);

  useEffect(() => {
    setNow(Date.now());
    const tick = setInterval(() => setNow(Date.now()), 8000);
    return () => clearInterval(tick);
  }, []);

  useEffect(() => {
    const types = Object.keys(TYPE_CFG) as SecurityEvent["type"][];
    const tenantPool = ["alpha", "beta", "gamma"];
    const msgs: Record<string, string> = {
      jwt_failure: "JWT signature invalid", rbac_denial: "Permission denied",
      sql_block: "Airlock blocked query", rate_limit: "Rate limit exceeded",
      health_change: "Health changed", secret_rotation: "Key rotated",
      tenant_isolation: "Cross-tenant attempt", auth_success: "Session authenticated",
    };
    const sevs: Record<string, SecurityEvent["severity"]> = {
      jwt_failure: "high", rbac_denial: "high", sql_block: "medium",
      rate_limit: "medium", health_change: "info", secret_rotation: "info",
      tenant_isolation: "critical", auth_success: "info",
    };
    const id = setInterval(() => {
      const type = types[Math.floor(Math.random() * types.length)];
      const ev: SecurityEvent = {
        id: `tl-${Date.now()}`,
        type,
        severity: sevs[type] ?? "info",
        message: msgs[type] ?? type,
        detail: "",
        tenant: tenantPool[Math.floor(Math.random() * tenantPool.length)],
        timestamp: new Date(),
        resolved: true,
      };
      setEvents((prev) => [...prev, ev].slice(-80));
      setNow(Date.now());
    }, 4500 + Math.random() * 5500);
    return () => clearInterval(id);
  }, []);

  const toX = (ts: Date) => {
    const age = now - ts.getTime();
    return W - (age / WINDOW_MS) * W;
  };

  const visibleEvents = events.filter((e) => {
    const x = toX(e.timestamp);
    return x >= 0 && x <= W && now - e.timestamp.getTime() < WINDOW_MS;
  });

  return (
    <div
      className="relative flex h-full flex-col overflow-hidden rounded-xl"
      style={{ background: "rgba(7,11,18,0.8)", border: "1px solid rgba(255,255,255,0.06)" }}
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/[0.05] px-3 py-2 shrink-0">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[9px] font-bold uppercase tracking-[0.18em] text-ae-muted">
            GLOBAL ACTIVITY TIMELINE
          </span>
          <span className="font-mono text-[9px] text-ae-muted">— LAST 2H —</span>
        </div>
        <div className="flex items-center gap-3">
          {(["jwt_failure", "rbac_denial", "sql_block", "rate_limit"] as const).map((t) => {
            const cfg = TYPE_CFG[t];
            return (
              <div key={t} className="flex items-center gap-1">
                <span className="font-mono text-[9px]" style={{ color: cfg.color }}>{cfg.symbol}</span>
                <span className="font-mono text-[8px] text-ae-muted">{t.replace("_", " ").toUpperCase()}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Timeline SVG */}
      <div className="flex-1 overflow-hidden px-3 py-1">
        <svg
          width="100%"
          height="100%"
          viewBox={`0 0 ${W} ${SVG_H}`}
          preserveAspectRatio="none"
        >
          {/* Time axis ticks */}
          {Array.from({ length: 13 }, (_, i) => {
            const x = (i / 12) * W;
            const ageMin = Math.round(((12 - i) / 12) * 120);
            return (
              <g key={i}>
                <line x1={x} y1={0} x2={x} y2={SVG_H - 18}
                  stroke="rgba(255,255,255,0.04)" strokeWidth={0.5} strokeDasharray="2 4" />
                <text x={x} y={SVG_H - 4} textAnchor="middle" fontSize={7}
                  fontFamily="monospace" fill="rgba(255,255,255,0.18)">
                  {ageMin === 0 ? "NOW" : `-${ageMin}m`}
                </text>
              </g>
            );
          })}

          {/* Lane backgrounds */}
          {Array.from({ length: LANES }, (_, i) => (
            <rect key={i}
              x={0} y={PAD_TOP + i * LANE_H}
              width={W} height={LANE_H - 1}
              fill={i % 2 === 0 ? "rgba(255,255,255,0.008)" : "transparent"}
            />
          ))}

          {/* Events */}
          {visibleEvents.map((e) => {
            const cfg = TYPE_CFG[e.type];
            const x = toX(e.timestamp);
            const y = PAD_TOP + cfg.lane * LANE_H + LANE_H / 2;
            const isHigh = e.severity === "critical" || e.severity === "high";

            return (
              <g key={e.id}
                onMouseEnter={() => setHovered(e.id)}
                onMouseLeave={() => setHovered(null)}
                style={{ cursor: "default" }}
              >
                <circle cx={x} cy={y} r={isHigh ? 4.5 : 3}
                  fill={cfg.color}
                  opacity={isHigh ? 1 : 0.55}
                  style={{ filter: isHigh ? `drop-shadow(0 0 5px ${cfg.color})` : undefined }}
                />
                {hovered === e.id && (
                  <g>
                    <rect x={Math.min(x + 8, W - 145)} y={y - 22}
                      width={140} height={30} rx={3} ry={3}
                      fill="rgba(12,18,28,0.97)"
                      stroke="rgba(255,255,255,0.08)" strokeWidth={0.5}
                    />
                    <text x={Math.min(x + 14, W - 139)} y={y - 11}
                      fontSize={7} fontFamily="monospace"
                      fill={cfg.color} fontWeight="bold" letterSpacing="0.06em">
                      {e.type.replace(/_/g, " ").toUpperCase()}
                    </text>
                    <text x={Math.min(x + 14, W - 139)} y={y + 1}
                      fontSize={7} fontFamily="monospace" fill="rgba(255,255,255,0.4)">
                      {e.tenant.toUpperCase()} · {e.message.slice(0, 22)}
                    </text>
                  </g>
                )}
              </g>
            );
          })}

          {/* NOW indicator */}
          <line x1={W - 1} y1={0} x2={W - 1} y2={SVG_H - 18}
            stroke="rgba(0,212,255,0.45)" strokeWidth={1}
          />
        </svg>
      </div>
    </div>
  );
}

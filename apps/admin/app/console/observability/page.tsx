"use client";

import { MetricGlassCard } from "@/components/metric-glass-card";
import { systemStatus, requestVolumeData, latencyData, sparkline7d, tenants } from "@/lib/mock-data";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line,
} from "recharts";
import { Activity, CheckCircle2, Clock } from "lucide-react";

function ChartTooltip({ active, payload, label }: {
  active?: boolean; payload?: Array<{ color: string; name: string; value: number }>; label?: string
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="glass rounded-xl p-3 text-[11px]">
      <p className="mb-1.5 font-mono text-ae-muted">{label}</p>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full" style={{ background: p.color }} />
          <span className="text-ae-muted">{p.name}:</span>
          <span className="font-mono font-semibold" style={{ color: p.color }}>{p.value}</span>
        </div>
      ))}
    </div>
  );
}

export default function ObservabilityPage() {
  const recent = requestVolumeData.slice(-12);
  const recentLatency = latencyData.slice(-12);

  return (
    <div className="h-full overflow-y-auto">
    <div className="flex flex-col gap-5 p-5">
      {/* Header */}
      <div>
        <h2 className="text-xl font-semibold tracking-tight text-ae-text">Observability</h2>
        <p className="mt-0.5 text-sm text-ae-muted">
          System telemetry · {systemStatus.avgLatencyMs}ms avg · {systemStatus.uptimePercent}% uptime
        </p>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-4 gap-4">
        <MetricGlassCard
          label="P50 Latency"
          value={systemStatus.avgLatencyMs}
          unit="ms"
          change={-8}
          changeLabel="vs avg"
          accent="green"
          sparkline={latencyData.slice(-14).map((d) => d.p50)}
        />
        <MetricGlassCard
          label="P95 Latency"
          value={58}
          unit="ms"
          change={-4}
          changeLabel="vs avg"
          accent="cyan"
          sparkline={latencyData.slice(-14).map((d) => d.p95)}
        />
        <MetricGlassCard
          label="P99 Latency"
          value={187}
          unit="ms"
          change={12}
          changeLabel="vs avg"
          accent="amber"
          sparkline={latencyData.slice(-14).map((d) => d.p99)}
        />
        <MetricGlassCard
          label="Uptime"
          value={systemStatus.uptimePercent.toString()}
          unit="%"
          accent="violet"
          sparkline={sparkline7d.map((_, i) => 99.9 + (i % 5) * 0.02)}
        />
      </div>

      {/* Request volume chart */}
      <div className="rounded-2xl border border-white/[0.07] bg-ae-surface/40 p-5">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-ae-text">Request Volume</h3>
            <p className="text-[11px] text-ae-muted">Requests per hour by tenant</p>
          </div>
          <div className="flex items-center gap-3 text-[10px] text-ae-muted">
            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm bg-ae-cyan" />Alpha</span>
            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm bg-ae-violet" />Beta</span>
            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm bg-ae-green" />Gamma</span>
          </div>
        </div>
        <div className="h-52">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={recent} margin={{ top: 4, right: 4, bottom: 0, left: -16 }}>
              <defs>
                <linearGradient id="grad-alpha" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#00d4ff" stopOpacity={0.2} />
                  <stop offset="100%" stopColor="#00d4ff" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="grad-beta" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.2} />
                  <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="grad-gamma" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10b981" stopOpacity={0.2} />
                  <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(255,255,255,0.04)" strokeDasharray="4 4" />
              <XAxis dataKey="time" tick={{ fill: "#475569", fontSize: 10 }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fill: "#475569", fontSize: 10 }} tickLine={false} axisLine={false} />
              <Tooltip content={<ChartTooltip />} />
              <Area type="monotone" dataKey="alpha" name="Alpha" stroke="#00d4ff" strokeWidth={1.5} fill="url(#grad-alpha)" dot={false} />
              <Area type="monotone" dataKey="beta" name="Beta" stroke="#8b5cf6" strokeWidth={1.5} fill="url(#grad-beta)" dot={false} />
              <Area type="monotone" dataKey="gamma" name="Gamma" stroke="#10b981" strokeWidth={1.5} fill="url(#grad-gamma)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Latency chart */}
      <div className="rounded-2xl border border-white/[0.07] bg-ae-surface/40 p-5">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-ae-text">Latency Percentiles</h3>
            <p className="text-[11px] text-ae-muted">P50 / P95 / P99 response times (ms)</p>
          </div>
        </div>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={recentLatency} margin={{ top: 4, right: 4, bottom: 0, left: -16 }}>
              <CartesianGrid stroke="rgba(255,255,255,0.04)" strokeDasharray="4 4" />
              <XAxis dataKey="time" tick={{ fill: "#475569", fontSize: 10 }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fill: "#475569", fontSize: 10 }} tickLine={false} axisLine={false} />
              <Tooltip content={<ChartTooltip />} />
              <Line type="monotone" dataKey="p50" name="P50" stroke="#10b981" strokeWidth={1.5} dot={false} />
              <Line type="monotone" dataKey="p95" name="P95" stroke="#00d4ff" strokeWidth={1.5} dot={false} />
              <Line type="monotone" dataKey="p99" name="P99" stroke="#f59e0b" strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Health probes */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Liveness Probe", path: "/health/live", status: "passing", latency: 1 },
          { label: "Readiness Probe", path: "/health/ready", status: "passing", latency: 4 },
          { label: "Startup Probe", path: "/health/startup", status: "passing", latency: 2 },
        ].map((probe) => (
          <div key={probe.label} className="rounded-xl border border-ae-green/20 bg-ae-surface/40 p-4">
            <div className="flex items-center gap-2 mb-2">
              <CheckCircle2 size={13} className="text-ae-green" />
              <span className="text-xs font-semibold text-ae-text">{probe.label}</span>
            </div>
            <p className="font-mono text-[11px] text-ae-muted mb-1">{probe.path}</p>
            <div className="flex items-center justify-between">
              <span className="rounded-full bg-ae-green/10 px-2 py-0.5 text-[10px] font-semibold text-ae-green">
                {probe.status.toUpperCase()}
              </span>
              <div className="flex items-center gap-1 text-[10px] text-ae-muted">
                <Clock size={10} />
                <span>{probe.latency}ms</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Per-tenant stats */}
      <div className="rounded-2xl border border-white/[0.07] bg-ae-surface/40 p-5">
        <h3 className="mb-4 text-sm font-semibold text-ae-text">Tenant Performance</h3>
        <div className="grid grid-cols-3 gap-4">
          {tenants.map((t) => (
            <div key={t.id} className="rounded-xl border border-white/[0.06] bg-ae-base/60 p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-ae-text">{t.name}</span>
                <Activity size={12} className="text-ae-muted" />
              </div>
              <div className="space-y-1.5">
                {[
                  { label: "Req/hr", value: t.requestsLastHour.toLocaleString(), color: "text-ae-cyan" },
                  { label: "Users", value: t.activeUsers.toString(), color: "text-ae-violet" },
                  { label: "Risk", value: t.riskScore.toString(), color: t.riskScore > 30 ? "text-ae-amber" : "text-ae-green" },
                ].map(({ label, value, color }) => (
                  <div key={label} className="flex items-center justify-between text-[10px]">
                    <span className="text-ae-muted">{label}</span>
                    <span className={`font-mono font-semibold ${color}`}>{value}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
    </div>
  );
}

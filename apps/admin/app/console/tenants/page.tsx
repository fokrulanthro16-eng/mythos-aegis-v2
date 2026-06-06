"use client";

import { TenantConstellation } from "@/components/tenant-constellation";
import { MetricGlassCard } from "@/components/metric-glass-card";
import { tenants, sparkline7d } from "@/lib/mock-data";
import { ShieldCheck, Globe, Users, Activity } from "lucide-react";
import { cn } from "@/lib/utils";
import { RelativeTime } from "@/components/relative-time";

const HEALTH_STYLE = {
  healthy: "border-ae-green/25 text-ae-green",
  degraded: "border-ae-amber/30 text-ae-amber",
  critical: "border-ae-red/30 text-ae-red",
};
const HEALTH_DOT = {
  healthy: "bg-ae-green",
  degraded: "bg-ae-amber",
  critical: "bg-ae-red",
};
const PLAN_STYLE = {
  enterprise: "bg-ae-violet/10 text-ae-violet",
  business: "bg-ae-cyan/10 text-ae-cyan",
  growth: "bg-ae-green/10 text-ae-green",
};

export default function TenantsPage() {
  const totalRequests = tenants.reduce((s, t) => s + t.requestsToday, 0);
  const totalUsers = tenants.reduce((s, t) => s + t.activeUsers, 0);
  const avgRisk = Math.round(tenants.reduce((s, t) => s + t.riskScore, 0) / tenants.length);

  return (
    <div className="h-full overflow-y-auto">
    <div className="flex flex-col gap-5 p-5">
      {/* Header */}
      <div>
        <h2 className="text-xl font-semibold tracking-tight text-ae-text">Tenant Intelligence</h2>
        <p className="mt-0.5 text-sm text-ae-muted">
          {tenants.length} tenants · strict isolation enforced
        </p>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-4 gap-4">
        <MetricGlassCard
          label="Total Tenants"
          value={tenants.length}
          accent="cyan"
        />
        <MetricGlassCard
          label="Total Requests / day"
          value={totalRequests}
          change={9}
          changeLabel="vs yesterday"
          accent="violet"
          sparkline={sparkline7d.slice(0, 14)}
        />
        <MetricGlassCard
          label="Active Users"
          value={totalUsers}
          change={4}
          changeLabel="vs yesterday"
          accent="green"
        />
        <MetricGlassCard
          label="Avg Risk Score"
          value={avgRisk}
          change={-15}
          changeLabel="vs last week"
          accent="amber"
        />
      </div>

      {/* Constellation + tenant table */}
      <div className="grid grid-cols-2 gap-5">
        <TenantConstellation />

        {/* Tenant cards */}
        <div className="flex flex-col gap-3">
          {tenants.map((tenant) => (
            <div
              key={tenant.id}
              className="overflow-hidden rounded-2xl border border-white/[0.07] bg-ae-surface/40 p-4"
              style={{ boxShadow: "0 0 0 1px rgba(255,255,255,0.04)" }}
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2.5">
                  <div
                    className={cn("h-2 w-2 rounded-full", HEALTH_DOT[tenant.health])}
                    style={{ boxShadow: `0 0 6px ${tenant.health === "healthy" ? "#10b981" : tenant.health === "degraded" ? "#f59e0b" : "#ef4444"}` }}
                  />
                  <div>
                    <p className="text-sm font-semibold text-ae-text">{tenant.name}</p>
                    <p className="text-[10px] text-ae-muted font-mono">{tenant.id}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={cn("rounded-full px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider", PLAN_STYLE[tenant.plan])}>
                    {tenant.plan}
                  </span>
                  <span className={cn("rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider", HEALTH_STYLE[tenant.health])}>
                    {tenant.health}
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2 mb-3">
                {[
                  { icon: Activity, label: "Req / day", value: tenant.requestsToday.toLocaleString() },
                  { icon: Users, label: "Users", value: tenant.activeUsers.toString() },
                  { icon: Globe, label: "Region", value: tenant.region },
                ].map(({ icon: Icon, label, value }) => (
                  <div key={label} className="rounded-lg bg-ae-base/60 px-2.5 py-2">
                    <div className="flex items-center gap-1 mb-0.5">
                      <Icon size={10} className="text-ae-muted" />
                      <span className="text-[9px] uppercase tracking-wider text-ae-muted">{label}</span>
                    </div>
                    <span className="font-mono text-xs font-semibold text-ae-text">{value}</span>
                  </div>
                ))}
              </div>

              <div className="flex items-center justify-between text-[10px]">
                <div className="flex items-center gap-3">
                  <span className="text-ae-muted">
                    SQL blocks: <span className="font-mono text-ae-amber">{tenant.sqlQueriesBlocked}</span>
                  </span>
                  <span className="text-ae-muted">
                    RBAC: <span className="font-mono text-ae-red">{tenant.rbacDenials}</span>
                  </span>
                  <span className="text-ae-muted">
                    JWT: <span className="font-mono text-ae-red">{tenant.jwtFailures}</span>
                  </span>
                </div>
                <RelativeTime date={tenant.lastActivity} className="text-ae-faint" />
              </div>

              {/* Health bar */}
              <div className="mt-2.5">
                <div className="flex justify-between text-[10px] mb-1">
                  <span className="text-ae-muted">Health score</span>
                  <span className={cn("font-mono font-semibold", HEALTH_STYLE[tenant.health].split(" ")[1])}>
                    {tenant.healthScore}%
                  </span>
                </div>
                <div className="h-0.5 rounded-full bg-ae-base overflow-hidden">
                  <div
                    className={cn("h-full rounded-full transition-all", HEALTH_DOT[tenant.health])}
                    style={{ width: `${tenant.healthScore}%` }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Isolation guarantee panel */}
      <div className="rounded-2xl border border-white/[0.07] bg-ae-surface/40 p-5">
        <div className="flex items-center gap-2 mb-4">
          <ShieldCheck size={14} className="text-ae-green" />
          <h3 className="text-sm font-semibold text-ae-text">Isolation Guarantees</h3>
        </div>
        <div className="grid grid-cols-3 gap-3">
          {[
            { title: "Database Row Isolation", detail: "Every query filtered by tenant_id. Cross-tenant access is structurally impossible at the SQL Airlock layer.", status: "guaranteed" },
            { title: "JWT Tenant Binding", detail: "All JWT tokens carry tenant_id claim. Middleware rejects any token/tenant mismatch before routing.", status: "guaranteed" },
            { title: "RBAC Scope Isolation", detail: "Permissions are scoped per-tenant. A user in alpha cannot exercise permissions in beta.", status: "guaranteed" },
          ].map((g) => (
            <div key={g.title} className="rounded-xl border border-ae-green/20 bg-ae-green/5 p-3">
              <div className="flex items-center gap-2 mb-1.5">
                <div className="h-1.5 w-1.5 rounded-full bg-ae-green shadow-glow-green" />
                <span className="text-xs font-semibold text-ae-green">{g.title}</span>
              </div>
              <p className="text-[11px] leading-relaxed text-ae-muted">{g.detail}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
    </div>
  );
}

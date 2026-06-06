"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  KeyRound, Shield, Database, Activity, RefreshCw,
  ToggleLeft, ToggleRight, Copy, Eye, EyeOff
} from "lucide-react";
import { tenants } from "@/lib/mock-data";

function SettingRow({ label, description, children }: {
  label: string; description: string; children: React.ReactNode
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-3 border-b border-white/[0.05] last:border-0">
      <div>
        <p className="text-sm font-medium text-ae-text">{label}</p>
        <p className="text-[11px] text-ae-muted mt-0.5">{description}</p>
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

function Toggle({ enabled, onChange }: { enabled: boolean; onChange: (v: boolean) => void }) {
  return (
    <button onClick={() => onChange(!enabled)} className="transition-colors">
      {enabled
        ? <ToggleRight size={20} className="text-ae-cyan" />
        : <ToggleLeft size={20} className="text-ae-muted" />
      }
    </button>
  );
}

function Section({ title, icon: Icon, children }: {
  title: string; icon: React.ElementType; children: React.ReactNode
}) {
  return (
    <div className="rounded-2xl border border-white/[0.07] bg-ae-surface/40 overflow-hidden">
      <div className="flex items-center gap-2.5 px-5 py-4 border-b border-white/[0.06]">
        <Icon size={14} className="text-ae-muted" />
        <h3 className="text-sm font-semibold text-ae-text">{title}</h3>
      </div>
      <div className="px-5 pb-2">{children}</div>
    </div>
  );
}

export default function SettingsPage() {
  const [otelEnabled, setOtelEnabled] = useState(false);
  const [rateLimitStrict, setRateLimitStrict] = useState(true);
  const [auditLog, setAuditLog] = useState(true);
  const [autoRotate, setAutoRotate] = useState(false);
  const [showSecret, setShowSecret] = useState(false);
  const [rotateMsg, setRotateMsg] = useState<string | null>(null);

  const handleRotate = (tenantId: string) => {
    setRotateMsg(`JWT key rotation initiated for ${tenantId}`);
    setTimeout(() => setRotateMsg(null), 3500);
  };

  return (
    <div className="h-full overflow-y-auto">
    <div className="flex flex-col gap-5 p-5">
      <div>
        <h2 className="text-xl font-semibold tracking-tight text-ae-text">Control Settings</h2>
        <p className="mt-0.5 text-sm text-ae-muted">
          System configuration · changes apply immediately
        </p>
      </div>

      {/* Toast */}
      {rotateMsg && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          className="flex items-center gap-2 rounded-xl border border-ae-green/30 bg-ae-green/10 px-4 py-2.5 text-sm text-ae-green"
        >
          <RefreshCw size={13} className="animate-spin" />
          {rotateMsg}
        </motion.div>
      )}

      {/* JWT Settings */}
      <Section title="JWT Configuration" icon={KeyRound}>
        <SettingRow
          label="Current Signing Key"
          description="HS256 · Generated 2026-06-06T01:15:00Z · 64 chars"
        >
          <div className="flex items-center gap-2">
            <code className="font-mono text-[11px] text-ae-muted">
              {showSecret ? "mythos-aegis-prod-jwt-secret-" : "••••••••••••••••••••••••••••••"}
            </code>
            <button onClick={() => setShowSecret((v) => !v)} className="text-ae-muted hover:text-ae-text">
              {showSecret ? <EyeOff size={13} /> : <Eye size={13} />}
            </button>
            <button className="text-ae-muted hover:text-ae-text"><Copy size={13} /></button>
          </div>
        </SettingRow>
        <SettingRow
          label="Expiry"
          description="Tokens expire after this duration. Outstanding tokens are respected."
        >
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm text-ae-cyan">3600s</span>
            <span className="text-[11px] text-ae-muted">(1 hour)</span>
          </div>
        </SettingRow>
        <SettingRow
          label="Auto-rotation"
          description="Automatically rotate signing key every 30 days with 1-hour grace period"
        >
          <Toggle enabled={autoRotate} onChange={setAutoRotate} />
        </SettingRow>
        <SettingRow label="Algorithm" description="Signing algorithm — changes require key rotation">
          <span className="rounded-full border border-ae-violet/30 bg-ae-violet/10 px-2.5 py-0.5 font-mono text-[11px] text-ae-violet">
            HS256
          </span>
        </SettingRow>
      </Section>

      {/* Per-tenant JWT Rotation */}
      <Section title="JWT Key Rotation" icon={RefreshCw}>
        <div className="pt-1 pb-2">
          <p className="text-[11px] text-ae-muted mb-3">
            Rotate the signing key for a specific tenant. The previous key is retained for
            3600s so outstanding tokens remain valid. Generate a strong key with{" "}
            <code className="font-mono text-ae-cyan">python -c &quot;import secrets; print(secrets.token_hex(32))&quot;</code>
          </p>
          <div className="flex flex-col gap-2">
            {tenants.map((t) => (
              <div key={t.id} className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-ae-base/60 px-4 py-2.5">
                <div className="flex items-center gap-2">
                  <div className="h-1.5 w-1.5 rounded-full bg-ae-green" />
                  <span className="text-sm font-medium text-ae-text">{t.name}</span>
                  <span className="font-mono text-[10px] text-ae-muted">{t.slug}</span>
                </div>
                <button
                  onClick={() => handleRotate(t.name)}
                  className="flex items-center gap-1.5 rounded-lg border border-ae-cyan/20 bg-ae-cyan/5 px-3 py-1.5 text-[11px] font-semibold text-ae-cyan transition-all hover:border-ae-cyan/40 hover:bg-ae-cyan/10"
                >
                  <RefreshCw size={11} />
                  Rotate Key
                </button>
              </div>
            ))}
          </div>
        </div>
      </Section>

      {/* Security */}
      <Section title="Security Configuration" icon={Shield}>
        <SettingRow
          label="Strict Rate Limiting"
          description="Block requests at limit threshold. When disabled, rate limit warnings are logged but not enforced."
        >
          <Toggle enabled={rateLimitStrict} onChange={setRateLimitStrict} />
        </SettingRow>
        <SettingRow
          label="SQL Audit Log"
          description="Log all Airlock decisions (blocked + allowed). Stored 90 days."
        >
          <Toggle enabled={auditLog} onChange={setAuditLog} />
        </SettingRow>
        <SettingRow
          label="Cross-tenant Check"
          description="Reject queries containing explicit tenant_id references. Always-on."
        >
          <span className="rounded-full bg-ae-green/10 px-2.5 py-1 text-[10px] font-semibold text-ae-green">
            ALWAYS ON
          </span>
        </SettingRow>
        <SettingRow
          label="Production Secret Guard"
          description="Refuse to start with weak JWT_SECRET in production environment."
        >
          <span className="rounded-full bg-ae-green/10 px-2.5 py-1 text-[10px] font-semibold text-ae-green">
            ALWAYS ON
          </span>
        </SettingRow>
      </Section>

      {/* Observability */}
      <Section title="Observability" icon={Activity}>
        <SettingRow
          label="OpenTelemetry"
          description="Export traces to OTLP endpoint. Requires OTEL_EXPORTER_OTLP_ENDPOINT env var."
        >
          <Toggle enabled={otelEnabled} onChange={setOtelEnabled} />
        </SettingRow>
        {otelEnabled && (
          <SettingRow label="OTLP Endpoint" description="Active trace exporter">
            <span className="font-mono text-[11px] text-ae-cyan">localhost:4318</span>
          </SettingRow>
        )}
        <SettingRow
          label="Prometheus Metrics"
          description="Metrics scrape endpoint at /metrics (always enabled)"
        >
          <span className="rounded-full bg-ae-green/10 px-2.5 py-1 text-[10px] font-semibold text-ae-green">
            ACTIVE
          </span>
        </SettingRow>
        <SettingRow
          label="Metrics Prefix"
          description="All metric names are prefixed to avoid collisions"
        >
          <code className="rounded border border-white/10 bg-ae-base px-2 py-0.5 font-mono text-[11px] text-ae-violet">
            mythos_
          </code>
        </SettingRow>
      </Section>

      {/* SQL Airlock */}
      <Section title="SQL Airlock Limits" icon={Database}>
        <SettingRow label="Max Rows (LIMIT clamp)" description="Maximum rows returned by any SQL query">
          <span className="font-mono text-sm font-semibold text-ae-cyan">100</span>
        </SettingRow>
        <SettingRow label="Query Timeout" description="Maximum execution time before cancellation">
          <span className="font-mono text-sm font-semibold text-ae-cyan">3s</span>
        </SettingRow>
        <SettingRow label="Date Bound" description="Maximum historical lookback in queries">
          <span className="font-mono text-sm font-semibold text-ae-cyan">90 days</span>
        </SettingRow>
        <SettingRow label="Subquery Depth" description="Maximum nested subquery depth in AST">
          <span className="font-mono text-sm font-semibold text-ae-cyan">2</span>
        </SettingRow>
      </Section>
    </div>
    </div>
  );
}

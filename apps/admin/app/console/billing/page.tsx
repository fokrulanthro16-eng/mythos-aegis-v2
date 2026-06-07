"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  CreditCard, BarChart3, Receipt, Loader2, X,
  ShoppingCart, CheckCircle, XCircle, RefreshCw,
} from "lucide-react";
import { apiRequest } from "@/lib/api";
import { DemoAuthBar } from "@/components/demo-auth-bar";
import { cn } from "@/lib/utils";

// Matches app/billing/schemas.py SubscriptionResponse
interface Subscription {
  subscription_id: string;
  tenant_id: string;
  plan: string;          // "free" | "pro" | "enterprise"
  status: string;
  provider_subscription_id: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  created_at: string;
}

// Matches app/billing/schemas.py QuotaStatusResponse
interface QuotaStatus {
  plan: string;
  monthly_api_requests: {
    used: number;
    limit: number;      // -1 = unlimited
    unlimited: boolean;
  };
  features: {
    rag_search: boolean;
    vision: boolean;
    workflow: boolean;
  };
  limits: {
    max_projects: number;
    max_documents: number;
    max_workflow_executions: number;
  };
}

// Matches app/billing/schemas.py InvoiceResponse
interface Invoice {
  invoice_id: string;
  subscription_id: string;
  amount_cents: number;
  currency: string;
  status: string;
  invoice_date: string;
  due_date: string | null;
  invoice_url: string | null;
  created_at: string;
}

// Matches app/billing/schemas.py CheckoutResponse
interface CheckoutResponse {
  session_id: string;
  checkout_url: string;
  plan: string;
  expires_at: string;
}

function ErrorBanner({ msg, onDismiss }: { msg: string; onDismiss?: () => void }) {
  return (
    <div className="flex items-center justify-between gap-2 rounded-xl border border-ae-red/30 bg-ae-red/10 px-4 py-2.5 text-sm text-ae-red">
      <div className="flex items-center gap-2"><X size={13} />{msg}</div>
      {onDismiss && <button onClick={onDismiss} className="shrink-0 opacity-60 hover:opacity-100"><X size={12} /></button>}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    active: "border-ae-green/30 bg-ae-green/10 text-ae-green",
    trialing: "border-ae-cyan/30 bg-ae-cyan/10 text-ae-cyan",
    cancelled: "border-ae-red/30 bg-ae-red/10 text-ae-red",
    past_due: "border-ae-amber/30 bg-ae-amber/10 text-ae-amber",
    paid: "border-ae-green/30 bg-ae-green/10 text-ae-green",
    open: "border-ae-amber/30 bg-ae-amber/10 text-ae-amber",
    void: "border-white/10 bg-ae-base text-ae-faint",
  };
  return (
    <span className={cn("rounded-full border px-2 py-0.5 font-mono text-[9px] font-bold uppercase", map[status] ?? "border-white/10 bg-ae-base text-ae-muted")}>
      {status}
    </span>
  );
}

const PLAN_TIERS = ["free", "pro", "enterprise"] as const;

export default function BillingPage() {
  const [sub, setSub] = useState<Subscription | null>(null);
  const [quota, setQuota] = useState<QuotaStatus | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<string>("pro");
  // Holds the last checkout session_id for mock activate flow
  const [lastCheckoutSession, setLastCheckoutSession] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    const [subRes, quotaRes, invRes] = await Promise.all([
      apiRequest<Subscription>("/v1/billing/subscription"),
      apiRequest<QuotaStatus>("/v1/billing/quota"),
      apiRequest<Invoice[]>("/v1/billing/invoices"),
    ]);
    // Surface first meaningful error
    const firstErr = subRes.error ?? quotaRes.error ?? invRes.error;
    if (firstErr && !subRes.data && !quotaRes.data) setError(firstErr);
    setSub(subRes.data);
    setQuota(quotaRes.data);
    setInvoices(invRes.data ?? []);
    setLoading(false);
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  async function handleCheckout() {
    setActionLoading("checkout");
    setActionMsg(null);
    // POST /v1/billing/checkout — CreateCheckoutRequest { plan: PlanTier, success_url?, cancel_url? }
    const { data, error: err } = await apiRequest<CheckoutResponse>("/v1/billing/checkout", {
      method: "POST",
      body: JSON.stringify({ plan: selectedPlan }),
    });
    setActionLoading(null);
    if (err) { setError(err); return; }
    if (data) {
      setLastCheckoutSession(data.session_id);
      setActionMsg(`Checkout created for ${data.plan} — session: ${data.session_id.slice(0, 8)}… URL: ${data.checkout_url}`);
    }
    await loadAll();
  }

  async function handleMockActivate() {
    setActionLoading("activate");
    setActionMsg(null);
    // Two-step mock flow: checkout → checkout/activate
    // Step 1: create checkout session if we don't have one
    let sessionId = lastCheckoutSession;
    if (!sessionId) {
      const { data: ckData, error: ckErr } = await apiRequest<CheckoutResponse>("/v1/billing/checkout", {
        method: "POST",
        body: JSON.stringify({ plan: selectedPlan }),
      });
      if (ckErr) { setActionLoading(null); setError(ckErr); return; }
      sessionId = ckData?.session_id ?? null;
      if (sessionId) setLastCheckoutSession(sessionId);
    }
    if (!sessionId) { setActionLoading(null); setError("Could not create checkout session"); return; }
    // Step 2: activate — POST /v1/billing/checkout/activate { plan, session_id }
    const { error: actErr } = await apiRequest<Subscription>("/v1/billing/checkout/activate", {
      method: "POST",
      body: JSON.stringify({ plan: selectedPlan, session_id: sessionId }),
    });
    setActionLoading(null);
    if (actErr) { setError(actErr); return; }
    setActionMsg(`${selectedPlan} subscription activated`);
    setLastCheckoutSession(null);
    await loadAll();
  }

  async function handleCancel() {
    setActionLoading("cancel");
    setActionMsg(null);
    // DELETE /v1/billing/subscription
    const { error: err } = await apiRequest<Subscription>("/v1/billing/subscription", {
      method: "DELETE",
    });
    setActionLoading(null);
    if (err) { setError(err); return; }
    setActionMsg("Subscription cancelled");
    await loadAll();
  }

  function fmtDate(s?: string | null) {
    if (!s) return "—";
    try { return new Date(s).toLocaleDateString(); } catch { return s; }
  }

  function fmtAmount(cents: number, currency: string) {
    const sym = currency.toUpperCase() === "USD" ? "$" : currency.toUpperCase() + " ";
    return `${sym}${(cents / 100).toFixed(2)}`;
  }

  return (
    <div className="h-full overflow-y-auto">
      <DemoAuthBar />
      <div className="flex flex-col gap-5 p-5">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <p className="font-mono text-[9px] font-bold uppercase tracking-[0.2em] text-ae-muted">BILLING & PLANS</p>
            <h2 className="text-xl font-semibold tracking-tight text-ae-text">Subscription Management</h2>
            <p className="mt-0.5 text-sm text-ae-muted">Plan · quota · invoices · upgrade</p>
          </div>
          <button
            onClick={loadAll}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-ae-base/60 px-3 py-1.5 font-mono text-[10px] text-ae-muted transition-colors hover:text-ae-text disabled:opacity-50"
          >
            <RefreshCw size={11} className={loading ? "animate-spin" : ""} />
            Refresh
          </button>
        </div>

        {error && <ErrorBanner msg={error} onDismiss={() => setError(null)} />}

        <AnimatePresence>
          {actionMsg && (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="flex items-start gap-2 rounded-xl border border-ae-green/30 bg-ae-green/10 px-4 py-2.5 text-sm text-ae-green"
            >
              <CheckCircle size={13} className="shrink-0 mt-0.5" />
              <span className="break-all">{actionMsg}</span>
            </motion.div>
          )}
        </AnimatePresence>

        {loading ? (
          <div className="flex items-center justify-center gap-3 py-16">
            <Loader2 size={18} className="animate-spin text-ae-muted" />
            <span className="font-mono text-[11px] text-ae-muted">Loading billing data…</span>
          </div>
        ) : (
          <div className="flex flex-col gap-5">
            <div className="grid grid-cols-2 gap-5">
              {/* Subscription card */}
              <div className="rounded-2xl border border-white/[0.07] bg-ae-surface/40 p-5">
                <div className="mb-4 flex items-center gap-2">
                  <CreditCard size={14} className="text-ae-muted" />
                  <h3 className="text-sm font-semibold text-ae-text">Current Subscription</h3>
                </div>
                {sub ? (
                  <div className="flex flex-col gap-2.5">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] text-ae-muted">Plan</span>
                      <span className="font-mono text-sm font-semibold text-ae-cyan uppercase">{sub.plan}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] text-ae-muted">Status</span>
                      <StatusBadge status={sub.status} />
                    </div>
                    {sub.current_period_start && (
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] text-ae-muted">Period</span>
                        <span className="font-mono text-[11px] text-ae-text">
                          {fmtDate(sub.current_period_start)} → {fmtDate(sub.current_period_end)}
                        </span>
                      </div>
                    )}
                    {sub.cancel_at_period_end && (
                      <div className="flex items-center gap-1.5 rounded-lg border border-ae-amber/20 bg-ae-amber/5 px-3 py-2 text-[11px] text-ae-amber">
                        <XCircle size={11} />Cancels at end of period
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-[11px] text-ae-faint">No active subscription (404 from backend is expected if none exists).</p>
                )}
              </div>

              {/* Actions card */}
              <div className="rounded-2xl border border-white/[0.07] bg-ae-surface/40 p-5">
                <div className="mb-4 flex items-center gap-2">
                  <ShoppingCart size={14} className="text-ae-muted" />
                  <h3 className="text-sm font-semibold text-ae-text">Actions</h3>
                </div>
                <div className="flex flex-col gap-3">
                  <div className="flex flex-col gap-2">
                    <p className="font-mono text-[9px] uppercase tracking-widest text-ae-muted">Select Plan</p>
                    <div className="flex gap-2">
                      {PLAN_TIERS.map((p) => (
                        <button
                          key={p}
                          onClick={() => setSelectedPlan(p)}
                          className={cn(
                            "flex-1 rounded-lg border px-2 py-1.5 font-mono text-[10px] font-semibold uppercase transition-all",
                            selectedPlan === p
                              ? "border-ae-cyan/40 bg-ae-cyan/10 text-ae-cyan"
                              : "border-white/10 bg-ae-base/60 text-ae-muted hover:text-ae-text"
                          )}
                        >
                          {p}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Checkout → creates session_id + checkout_url */}
                  <button
                    onClick={handleCheckout}
                    disabled={!!actionLoading}
                    className="flex items-center justify-center gap-2 rounded-xl border border-ae-cyan/20 bg-ae-cyan/5 px-4 py-2 text-sm font-semibold text-ae-cyan transition-all hover:border-ae-cyan/40 hover:bg-ae-cyan/10 disabled:opacity-50"
                  >
                    {actionLoading === "checkout" ? <Loader2 size={12} className="animate-spin" /> : <ShoppingCart size={12} />}
                    Checkout ({selectedPlan})
                  </button>

                  <div className="h-px bg-white/[0.05]" />

                  {/* Mock activate: checkout → activate in sequence */}
                  <button
                    onClick={handleMockActivate}
                    disabled={!!actionLoading}
                    className="flex items-center justify-center gap-2 rounded-xl border border-ae-green/20 bg-ae-green/5 px-4 py-2 text-sm font-semibold text-ae-green transition-all hover:border-ae-green/40 hover:bg-ae-green/10 disabled:opacity-50"
                  >
                    {actionLoading === "activate" ? <Loader2 size={12} className="animate-spin" /> : <CheckCircle size={12} />}
                    Mock Activate ({selectedPlan})
                  </button>

                  {/* Cancel — DELETE /v1/billing/subscription */}
                  <button
                    onClick={handleCancel}
                    disabled={!!actionLoading}
                    className="flex items-center justify-center gap-2 rounded-xl border border-ae-red/20 bg-ae-red/5 px-4 py-2 text-sm font-semibold text-ae-red transition-all hover:border-ae-red/40 hover:bg-ae-red/10 disabled:opacity-50"
                  >
                    {actionLoading === "cancel" ? <Loader2 size={12} className="animate-spin" /> : <XCircle size={12} />}
                    Cancel Subscription
                  </button>
                </div>
              </div>
            </div>

            {/* Quota */}
            {quota && (
              <div className="rounded-2xl border border-white/[0.07] bg-ae-surface/40 p-5">
                <div className="mb-4 flex items-center gap-2">
                  <BarChart3 size={14} className="text-ae-muted" />
                  <h3 className="text-sm font-semibold text-ae-text">Quota — {quota.plan}</h3>
                </div>
                <div className="grid grid-cols-3 gap-3">
                  {/* API requests */}
                  <div className="rounded-xl border border-ae-cyan/15 bg-ae-cyan/5 px-3 py-3">
                    <p className="font-mono text-[9px] uppercase tracking-widest text-ae-muted mb-1.5">API Requests</p>
                    <p className="font-mono text-sm font-semibold text-ae-cyan">
                      {quota.monthly_api_requests.unlimited
                        ? "Unlimited"
                        : `${quota.monthly_api_requests.used} / ${quota.monthly_api_requests.limit}`}
                    </p>
                    {!quota.monthly_api_requests.unlimited && quota.monthly_api_requests.limit > 0 && (
                      <div className="mt-2 h-0.5 w-full rounded-full bg-ae-base overflow-hidden">
                        <div
                          className="h-full rounded-full bg-ae-cyan transition-all"
                          style={{ width: `${Math.min(100, (quota.monthly_api_requests.used / quota.monthly_api_requests.limit) * 100)}%` }}
                        />
                      </div>
                    )}
                  </div>
                  {/* Feature toggles */}
                  {(["rag_search", "vision", "workflow"] as const).map((feat) => (
                    <div
                      key={feat}
                      className={cn(
                        "rounded-xl border px-3 py-3",
                        quota.features[feat] ? "border-ae-green/15 bg-ae-green/5" : "border-ae-red/15 bg-ae-red/5"
                      )}
                    >
                      <p className="font-mono text-[9px] uppercase tracking-widest text-ae-muted mb-1.5">
                        {feat.replace(/_/g, " ")}
                      </p>
                      <p className={cn("font-mono text-sm font-semibold", quota.features[feat] ? "text-ae-green" : "text-ae-red")}>
                        {quota.features[feat] ? "Enabled" : "Disabled"}
                      </p>
                    </div>
                  ))}
                  {/* Limits */}
                  {(
                    [
                      ["Projects", quota.limits.max_projects],
                      ["Documents", quota.limits.max_documents],
                      ["Workflows", quota.limits.max_workflow_executions],
                    ] as [string, number][]
                  ).map(([label, val]) => (
                    <div key={label} className="rounded-xl border border-white/[0.07] bg-ae-base/40 px-3 py-3">
                      <p className="font-mono text-[9px] uppercase tracking-widest text-ae-muted mb-1.5">Max {label}</p>
                      <p className="font-mono text-sm font-semibold text-ae-text">
                        {val === -1 ? "Unlimited" : val.toLocaleString()}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Invoices */}
            <div className="rounded-2xl border border-white/[0.07] bg-ae-surface/40 p-5">
              <div className="mb-4 flex items-center gap-2">
                <Receipt size={14} className="text-ae-muted" />
                <h3 className="text-sm font-semibold text-ae-text">Invoices</h3>
                <span className="ml-auto font-mono text-[10px] text-ae-faint">{invoices.length} total</span>
              </div>
              {invoices.length === 0 ? (
                <p className="text-[11px] text-ae-faint">No invoices yet.</p>
              ) : (
                <div className="flex flex-col divide-y divide-white/[0.04]">
                  {invoices.map((inv) => (
                    <div key={inv.invoice_id} className="flex items-center justify-between py-3 first:pt-0 last:pb-0">
                      <div>
                        <p className="text-sm text-ae-text font-mono text-[11px]">{inv.invoice_id.slice(0, 8)}…</p>
                        <p className="font-mono text-[10px] text-ae-muted">{fmtDate(inv.invoice_date)}</p>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-sm font-semibold text-ae-text">
                          {fmtAmount(inv.amount_cents, inv.currency)}
                        </span>
                        <StatusBadge status={inv.status} />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { CheckCircle2, XCircle, AlertTriangle, ChevronRight, ArrowRight } from "lucide-react";
import { sqlQueries, type SqlQuery } from "@/lib/mock-data";
import { cn } from "@/lib/utils";
import { RelativeTime } from "@/components/relative-time";

const STAGES = [
  { id: "intent", label: "Intent", short: "INTENT", description: "NLP classifier detects ActionType.SQL_ANALYTICS" },
  { id: "draft", label: "Draft SQL", short: "DRAFT", description: "Classifier generates candidate SQL from user input" },
  { id: "ast", label: "AST Parse", short: "AST", description: "pg_query parses SQL into abstract syntax tree" },
  { id: "inject", label: "Tenant Inject", short: "INJECT", description: "WHERE tenant_id=$1 appended to every query" },
  { id: "mask", label: "Column Mask", short: "MASK", description: "PII columns replaced with redacted values" },
  { id: "limit", label: "Limit Clamp", short: "LIMIT", description: "LIMIT enforced ≤ SQL_MAX_LIMIT (100)" },
  { id: "exec", label: "Execute", short: "EXEC", description: "Parameterized query sent with timeout guard" },
];

const STAGE_NAMES = STAGES.map((s) => s.label);

function StageNode({
  stage,
  index,
  activeIndex,
  blockedIndex,
}: {
  stage: typeof STAGES[number];
  index: number;
  activeIndex: number;
  blockedIndex: number | null;
}) {
  const isBlocked = index === blockedIndex;
  const isPassed = blockedIndex !== null ? index < blockedIndex : index < activeIndex;
  const isActive = index === activeIndex && blockedIndex === null;
  const isFuture = blockedIndex !== null ? index > blockedIndex : index > activeIndex;

  return (
    <div className="flex flex-col items-center gap-1.5 min-w-0">
      <motion.div
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ delay: index * 0.07 }}
        className={cn(
          "relative flex h-12 w-20 flex-col items-center justify-center rounded-lg border text-center transition-all duration-300",
          isPassed && "border-ae-green/30 bg-ae-green/10 text-ae-green",
          isBlocked && "border-ae-red/40 bg-ae-red/10 text-ae-red",
          isActive && "border-ae-cyan/40 bg-ae-cyan/10 text-ae-cyan shadow-glow-cyan-sm",
          isFuture && "border-white/[0.06] bg-ae-base/40 text-ae-muted"
        )}
      >
        {isPassed && (
          <CheckCircle2 size={12} className="absolute -right-1.5 -top-1.5 rounded-full bg-ae-surface text-ae-green" />
        )}
        {isBlocked && (
          <XCircle size={12} className="absolute -right-1.5 -top-1.5 rounded-full bg-ae-surface text-ae-red" />
        )}
        <span className="text-[9px] font-bold tracking-wider">{stage.short}</span>
        <span className="text-[8px] font-normal opacity-70 leading-tight px-1">{stage.label}</span>
      </motion.div>
    </div>
  );
}

function QueryRow({ query, onClick, isSelected }: {
  query: SqlQuery;
  onClick: () => void;
  isSelected: boolean;
}) {
  return (
    <motion.button
      onClick={onClick}
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      className={cn(
        "w-full text-left rounded-xl border p-3 transition-all",
        isSelected
          ? "border-ae-cyan/30 bg-ae-cyan/5"
          : "border-white/[0.06] bg-ae-base/40 hover:border-white/[0.12] hover:bg-ae-base/60"
      )}
    >
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-1.5">
          {query.status === "blocked" ? (
            <XCircle size={12} className="text-ae-red" />
          ) : query.status === "rewritten" ? (
            <AlertTriangle size={12} className="text-ae-amber" />
          ) : (
            <CheckCircle2 size={12} className="text-ae-green" />
          )}
          <span
            className={cn(
              "text-[10px] font-bold uppercase tracking-wider",
              query.status === "blocked" ? "text-ae-red" : query.status === "rewritten" ? "text-ae-amber" : "text-ae-green"
            )}
          >
            {query.status}
          </span>
          {query.blockedAt && (
            <>
              <ChevronRight size={10} className="text-ae-faint" />
              <span className="text-[10px] text-ae-muted">{query.blockedAt}</span>
            </>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-[10px] text-ae-muted">{query.tenant.toUpperCase()}</span>
          {query.durationMs && (
            <span className="font-mono text-[10px] text-ae-green">{query.durationMs}ms</span>
          )}
          <RelativeTime date={query.timestamp} className="text-[10px] text-ae-faint" />
        </div>
      </div>
      <code className="block text-[10px] font-mono text-ae-text/70 truncate leading-relaxed">
        {query.original}
      </code>
      {query.reason && (
        <p className="mt-1 text-[10px] text-ae-muted">{query.reason}</p>
      )}
    </motion.button>
  );
}

export function AirlockVisualizer() {
  const [selected, setSelected] = useState<SqlQuery | null>(sqlQueries[0]);
  const [tab, setTab] = useState<"all" | "blocked" | "allowed">("all");

  const filtered = tab === "all"
    ? sqlQueries
    : tab === "blocked"
    ? sqlQueries.filter((q) => q.status === "blocked")
    : sqlQueries.filter((q) => q.status !== "blocked");

  const activeIndex = selected
    ? selected.status === "blocked"
      ? STAGE_NAMES.indexOf(selected.blockedAt ?? "Execute")
      : 6
    : 6;

  const blockedIndex = selected?.status === "blocked"
    ? STAGE_NAMES.indexOf(selected.blockedAt ?? "AST Parse")
    : null;

  return (
    <div className="flex flex-col gap-4">
      {/* Pipeline visualization */}
      <div
        className="overflow-hidden rounded-2xl border border-white/[0.07] bg-ae-surface/40 p-6"
        style={{ boxShadow: "0 0 0 1px rgba(255,255,255,0.05)" }}
      >
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-ae-text">SQL Airlock Pipeline</h3>
            <p className="text-[11px] text-ae-muted">7-stage query validation and transformation</p>
          </div>
          {selected && (
            <div
              className={cn(
                "rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider",
                selected.status === "blocked"
                  ? "border-ae-red/30 bg-ae-red/10 text-ae-red"
                  : selected.status === "rewritten"
                  ? "border-ae-amber/30 bg-ae-amber/10 text-ae-amber"
                  : "border-ae-green/30 bg-ae-green/10 text-ae-green"
              )}
            >
              {selected.status}
            </div>
          )}
        </div>

        {/* Stage pipeline */}
        <div className="flex items-center justify-between gap-1">
          {STAGES.map((stage, i) => (
            <div key={stage.id} className="flex items-center gap-1 flex-1 last:flex-none">
              <StageNode
                stage={stage}
                index={i}
                activeIndex={activeIndex}
                blockedIndex={blockedIndex}
              />
              {i < STAGES.length - 1 && (
                <div className="flex-1 flex items-center justify-center">
                  <motion.div
                    className={cn(
                      "h-px w-full",
                      i < (blockedIndex ?? activeIndex) ? "bg-ae-green/30" : "bg-white/[0.05]"
                    )}
                    initial={{ scaleX: 0 }}
                    animate={{ scaleX: 1 }}
                    style={{ transformOrigin: "left" }}
                    transition={{ delay: 0.1 + i * 0.07 }}
                  />
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Stage description */}
        <AnimatePresence mode="wait">
          <motion.div
            key={activeIndex}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="mt-4 rounded-lg border border-white/[0.05] bg-ae-base/60 px-4 py-2.5"
          >
            <div className="flex items-center gap-2">
              <ArrowRight size={11} className="text-ae-cyan" />
              <span className="text-[11px] text-ae-muted">
                {selected
                  ? STAGES[blockedIndex ?? 6]?.description
                  : "Select a query to trace its path through the airlock"}
              </span>
            </div>
            {selected?.transformed && (
              <div className="mt-2 pl-4">
                <p className="text-[10px] text-ae-muted mb-0.5">Rewritten query:</p>
                <code className="text-[10px] font-mono text-ae-violet/90 break-all leading-relaxed">
                  {selected.transformed}
                </code>
              </div>
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Query list */}
      <div
        className="overflow-hidden rounded-2xl border border-white/[0.07] bg-ae-surface/40 p-5"
        style={{ boxShadow: "0 0 0 1px rgba(255,255,255,0.05)" }}
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-ae-text">Query Log</h3>
          {/* Filter tabs */}
          <div className="flex rounded-lg border border-white/[0.07] overflow-hidden">
            {(["all", "blocked", "allowed"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={cn(
                  "px-3 py-1 text-[10px] font-semibold uppercase tracking-wider transition-colors",
                  tab === t
                    ? "bg-ae-cyan/10 text-ae-cyan"
                    : "text-ae-muted hover:text-ae-text"
                )}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-2">
          {filtered.map((query) => (
            <QueryRow
              key={query.id}
              query={query}
              onClick={() => setSelected(query.id === selected?.id ? null : query)}
              isSelected={selected?.id === query.id}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

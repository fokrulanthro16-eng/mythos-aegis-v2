"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Bot, Play, X, Loader2, ChevronRight, Wrench } from "lucide-react";
import { apiRequest } from "@/lib/api";
import { getProjectId } from "@/lib/demo-config";
import { DemoAuthBar } from "@/components/demo-auth-bar";
import { cn } from "@/lib/utils";

interface ToolCallRecord {
  tool_name: string;
  params: Record<string, unknown>;
  success: boolean;
  error?: string | null;
}

interface AgentRunResponse {
  answer: string;
  tool_calls: ToolCallRecord[];
  iterations: number;
  session_id?: string | null;
}

function ErrorBanner({ msg }: { msg: string }) {
  return (
    <div className="flex items-center gap-2 rounded-xl border border-ae-red/30 bg-ae-red/10 px-4 py-2.5 text-sm text-ae-red">
      <X size={13} className="shrink-0" />
      <span>{msg}</span>
    </div>
  );
}

const EXAMPLE_TASKS = [
  "List the top 5 most recent audit events",
  "Summarize security events from the last 24 hours",
  "How many SQL queries were blocked today?",
  "Show me tenant risk scores",
];

export default function AgentPage() {
  const [task, setTask] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AgentRunResponse | null>(null);
  const [expandedCall, setExpandedCall] = useState<number | null>(null);

  async function handleRun(e: React.FormEvent) {
    e.preventDefault();
    if (!task.trim()) return;
    const pid = getProjectId();
    if (!pid) { setError("Set a Project ID in the config bar above."); return; }
    setLoading(true);
    setError(null);
    setResult(null);
    setExpandedCall(null);
    // Backend AgentRunRequest: { project_id: UUID, question: str, max_iterations?: int }
    const { data, error: err } = await apiRequest<AgentRunResponse>("/v1/agent/run", {
      method: "POST",
      body: JSON.stringify({ project_id: pid, question: task }),
    });
    setLoading(false);
    if (err) { setError(err); return; }
    setResult(data);
  }

  return (
    <div className="h-full overflow-y-auto">
      <DemoAuthBar />
      <div className="flex flex-col gap-5 p-5">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <p className="font-mono text-[9px] font-bold uppercase tracking-[0.2em] text-ae-muted">
              AGENT RUNTIME
            </p>
            <h2 className="text-xl font-semibold tracking-tight text-ae-text">
              AI Agent Runner
            </h2>
            <p className="mt-0.5 text-sm text-ae-muted">
              Dispatch tasks to the agent · observe tool calls and reasoning steps
            </p>
          </div>
          {result?.session_id && (
            <span className="rounded-full border border-white/10 bg-ae-base px-2.5 py-1 font-mono text-[10px] text-ae-muted">
              session: {result.session_id.slice(0, 8)}…
            </span>
          )}
        </div>

        <div className="grid grid-cols-2 gap-5">
          {/* Input */}
          <div className="flex flex-col gap-4">
            <div className="rounded-2xl border border-white/[0.07] bg-ae-surface/40 p-5">
              <div className="mb-4 flex items-center gap-2">
                <Bot size={14} className="text-ae-muted" />
                <h3 className="text-sm font-semibold text-ae-text">Task</h3>
              </div>
              <form onSubmit={handleRun} className="flex flex-col gap-3">
                <textarea
                  value={task}
                  onChange={(e) => setTask(e.target.value)}
                  placeholder="Describe the task for the agent…"
                  rows={6}
                  className="w-full resize-none rounded-xl border border-white/[0.08] bg-ae-base/60 px-4 py-3 font-mono text-sm text-ae-text placeholder-ae-muted outline-none transition-colors focus:border-ae-green/40"
                />
                <button
                  type="submit"
                  disabled={loading || !task.trim()}
                  className={cn(
                    "flex items-center justify-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-semibold transition-all disabled:opacity-50",
                    "border-ae-green/20 bg-ae-green/5 text-ae-green hover:border-ae-green/40 hover:bg-ae-green/10"
                  )}
                >
                  {loading ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
                  {loading ? "Running…" : "Run Agent"}
                </button>
              </form>
              {error && <div className="mt-3"><ErrorBanner msg={error} /></div>}
            </div>

            {/* Example tasks */}
            <div className="rounded-2xl border border-white/[0.07] bg-ae-surface/40 p-5">
              <p className="mb-3 font-mono text-[9px] font-bold uppercase tracking-[0.18em] text-ae-muted">
                EXAMPLE TASKS
              </p>
              <div className="flex flex-col gap-1.5">
                {EXAMPLE_TASKS.map((t) => (
                  <button
                    key={t}
                    onClick={() => setTask(t)}
                    className="flex items-center gap-2 rounded-lg px-3 py-2 text-left text-[11px] text-ae-muted transition-colors hover:bg-white/[0.03] hover:text-ae-text"
                  >
                    <ChevronRight size={10} className="text-ae-faint shrink-0" />
                    {t}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Output */}
          <div className="flex flex-col gap-4">
            <AnimatePresence mode="wait">
              {loading && (
                <motion.div
                  key="loading"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="flex flex-col items-center justify-center gap-4 rounded-2xl border border-white/[0.07] bg-ae-surface/40 p-12"
                >
                  <div className="flex items-center gap-2">
                    {[0, 0.15, 0.3].map((d, i) => (
                      <motion.div
                        key={i}
                        className="h-2 w-2 rounded-full bg-ae-green"
                        animate={{ opacity: [0.3, 1, 0.3] }}
                        transition={{ duration: 1, delay: d, repeat: Infinity }}
                      />
                    ))}
                  </div>
                  <p className="font-mono text-[11px] text-ae-muted">Agent is thinking…</p>
                </motion.div>
              )}

              {result && !loading && (
                <motion.div
                  key="result"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex flex-col gap-3"
                >
                  {/* Answer */}
                  <div className="rounded-2xl border border-ae-green/20 bg-ae-green/5 p-5">
                    <div className="mb-2 flex items-center justify-between">
                      <p className="font-mono text-[9px] font-bold uppercase tracking-[0.18em] text-ae-green">ANSWER</p>
                      <span className="font-mono text-[9px] text-ae-faint">{result.iterations} iter</span>
                    </div>
                    <p className="text-sm leading-relaxed text-ae-text whitespace-pre-wrap">
                      {result.answer}
                    </p>
                  </div>

                  {/* Tool calls */}
                  {result.tool_calls.length > 0 && (
                    <div className="rounded-2xl border border-white/[0.07] bg-ae-surface/40 p-5">
                      <p className="mb-3 font-mono text-[9px] font-bold uppercase tracking-[0.18em] text-ae-muted">
                        TOOL CALLS — {result.tool_calls.length}
                      </p>
                      <div className="flex flex-col gap-1.5">
                        {result.tool_calls.map((tc, i) => (
                          <div key={i}>
                            <button
                              onClick={() => setExpandedCall(expandedCall === i ? null : i)}
                              className="flex w-full items-center gap-2 rounded-xl border border-white/[0.06] bg-ae-base/60 px-3 py-2 text-left transition-colors hover:bg-white/[0.03]"
                            >
                              <Wrench size={10} className={tc.success ? "text-ae-green" : "text-ae-red"} />
                              <span className="font-mono text-[10px] font-semibold text-ae-cyan flex-1">
                                {tc.tool_name}
                              </span>
                              {!tc.success && (
                                <span className="font-mono text-[9px] text-ae-red">failed</span>
                              )}
                              <ChevronRight
                                size={10}
                                className={cn("text-ae-faint transition-transform shrink-0", expandedCall === i && "rotate-90")}
                              />
                            </button>
                            {expandedCall === i && (
                              <div className="mt-1 rounded-xl border border-white/[0.04] bg-ae-base/40 px-3 py-2">
                                <pre className="text-[10px] font-mono text-ae-muted whitespace-pre-wrap break-all">
                                  {JSON.stringify(tc.params, null, 2)}
                                </pre>
                                {tc.error && (
                                  <p className="mt-1 text-[10px] text-ae-red">{tc.error}</p>
                                )}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </motion.div>
              )}

              {!result && !loading && (
                <motion.div
                  key="empty"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-white/[0.07] bg-ae-surface/20 p-12 text-center"
                >
                  <Bot size={28} className="text-ae-faint" />
                  <p className="font-mono text-[11px] text-ae-faint">Enter a task and click Run Agent</p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  );
}

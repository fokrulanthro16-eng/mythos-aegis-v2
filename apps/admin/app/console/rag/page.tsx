"use client";

import { useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Upload, Send, FileText, BookOpen, X, Loader2 } from "lucide-react";
import { apiRequest, apiUpload } from "@/lib/api";
import { getProjectId } from "@/lib/demo-config";
import { DemoAuthBar } from "@/components/demo-auth-bar";
import { cn } from "@/lib/utils";

interface DocumentListItem {
  document_id: string;
  filename: string;
  content_type: string;
  status: string;
  chunk_count?: number;
}

interface DocumentUploadResponse {
  document_id: string;
  filename: string;
  status: string;
  chunk_count: number;
}

interface Citation {
  document_id: string;
  filename: string;
  chunk_index: number;
  citation_label: string;
}

interface AskResponse {
  answer: string;
  citations: Citation[];
  provider: string;
  model: string;
}

function ErrorBanner({ msg }: { msg: string }) {
  return (
    <div className="flex items-center gap-2 rounded-xl border border-ae-red/30 bg-ae-red/10 px-4 py-2.5 text-sm text-ae-red">
      <X size={13} className="shrink-0" />
      <span>{msg}</span>
    </div>
  );
}

export default function RagPage() {
  const [docs, setDocs] = useState<DocumentListItem[]>([]);
  const [docsLoaded, setDocsLoaded] = useState(false);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);

  const [question, setQuestion] = useState("");
  const [askLoading, setAskLoading] = useState(false);
  const [askError, setAskError] = useState<string | null>(null);
  const [answer, setAnswer] = useState<AskResponse | null>(null);

  const fileRef = useRef<HTMLInputElement>(null);

  async function loadDocs() {
    const pid = getProjectId();
    if (!pid) { setUploadError("Set a Project ID in the config bar above."); return; }
    setUploadError(null);
    const { data, error } = await apiRequest<DocumentListItem[]>(
      `/v1/rag/documents?project_id=${encodeURIComponent(pid)}`
    );
    if (error) { setUploadError(error); return; }
    setDocs(data ?? []);
    setDocsLoaded(true);
  }

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    const pid = getProjectId();
    if (!pid) { setUploadError("Set a Project ID in the config bar above."); return; }
    setUploadLoading(true);
    setUploadError(null);
    setUploadMsg(null);
    const form = new FormData();
    form.append("file", file);
    form.append("project_id", pid);
    const { data, error } = await apiUpload<DocumentUploadResponse>("/v1/rag/upload", form);
    setUploadLoading(false);
    if (error) { setUploadError(error); return; }
    setUploadMsg(`Uploaded: ${data?.filename ?? file.name} · ${data?.chunk_count ?? 0} chunks`);
    if (fileRef.current) fileRef.current.value = "";
    setDocsLoaded(false);
  }

  async function handleAsk(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;
    const pid = getProjectId();
    if (!pid) { setAskError("Set a Project ID in the config bar above."); return; }
    setAskLoading(true);
    setAskError(null);
    setAnswer(null);
    const { data, error } = await apiRequest<AskResponse>("/v1/rag/ask", {
      method: "POST",
      body: JSON.stringify({ project_id: pid, question }),
    });
    setAskLoading(false);
    if (error) { setAskError(error); return; }
    setAnswer(data);
  }

  return (
    <div className="h-full overflow-y-auto">
      <DemoAuthBar />
      <div className="flex flex-col gap-5 p-5">
        {/* Header */}
        <div>
          <p className="font-mono text-[9px] font-bold uppercase tracking-[0.2em] text-ae-muted">
            RAG PIPELINE
          </p>
          <h2 className="text-xl font-semibold tracking-tight text-ae-text">
            Retrieval-Augmented Generation
          </h2>
          <p className="mt-0.5 text-sm text-ae-muted">
            Upload documents · ask questions · retrieve grounded answers with citations
          </p>
        </div>

        <div className="grid grid-cols-2 gap-5">
          {/* Upload panel */}
          <div className="flex flex-col gap-4">
            <div className="rounded-2xl border border-white/[0.07] bg-ae-surface/40 p-5">
              <div className="mb-4 flex items-center gap-2">
                <Upload size={14} className="text-ae-muted" />
                <h3 className="text-sm font-semibold text-ae-text">Upload Document</h3>
              </div>
              <form onSubmit={handleUpload} className="flex flex-col gap-3">
                <label className="flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed border-white/10 bg-ae-base/40 px-4 py-8 text-center transition-colors hover:border-ae-cyan/30 hover:bg-ae-cyan/5">
                  <FileText size={24} className="text-ae-muted" />
                  <span className="text-sm text-ae-muted">Click to select file</span>
                  <span className="font-mono text-[10px] text-ae-faint">PDF · TXT · MD · CSV · JSON</span>
                  <input
                    ref={fileRef}
                    type="file"
                    accept=".pdf,.txt,.md,.csv,.json"
                    className="hidden"
                  />
                </label>
                <button
                  type="submit"
                  disabled={uploadLoading}
                  className="flex items-center justify-center gap-2 rounded-xl border border-ae-cyan/20 bg-ae-cyan/5 px-4 py-2.5 text-sm font-semibold text-ae-cyan transition-all hover:border-ae-cyan/40 hover:bg-ae-cyan/10 disabled:opacity-50"
                >
                  {uploadLoading ? <Loader2 size={13} className="animate-spin" /> : <Upload size={13} />}
                  {uploadLoading ? "Uploading…" : "Upload"}
                </button>
              </form>
              {uploadError && <div className="mt-3"><ErrorBanner msg={uploadError} /></div>}
              {uploadMsg && (
                <div className="mt-3 flex items-center gap-2 rounded-xl border border-ae-green/30 bg-ae-green/10 px-3 py-2 text-[11px] text-ae-green">
                  <span className="h-1.5 w-1.5 rounded-full bg-ae-green" />
                  {uploadMsg}
                </div>
              )}
            </div>

            {/* Document list */}
            <div className="rounded-2xl border border-white/[0.07] bg-ae-surface/40 p-5">
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <BookOpen size={14} className="text-ae-muted" />
                  <h3 className="text-sm font-semibold text-ae-text">Documents</h3>
                </div>
                <button
                  onClick={loadDocs}
                  className="rounded-lg border border-white/10 bg-ae-base/60 px-2.5 py-1 font-mono text-[10px] text-ae-muted transition-colors hover:text-ae-text"
                >
                  Refresh
                </button>
              </div>
              {!docsLoaded ? (
                <p className="text-[11px] text-ae-faint">Click Refresh to load documents.</p>
              ) : docs.length === 0 ? (
                <p className="text-[11px] text-ae-faint">No documents indexed yet.</p>
              ) : (
                <div className="flex flex-col gap-1.5">
                  {docs.map((d) => (
                    <div
                      key={d.document_id}
                      className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-ae-base/60 px-3 py-2"
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <FileText size={11} className="text-ae-cyan shrink-0" />
                        <span className="text-[11px] text-ae-text truncate">{d.filename}</span>
                      </div>
                      <div className="flex items-center gap-2 ml-2 shrink-0">
                        <span className="font-mono text-[9px] text-ae-muted">{d.content_type}</span>
                        <span className={cn(
                          "rounded-full px-1.5 py-0.5 font-mono text-[9px]",
                          d.status === "ready" ? "bg-ae-green/10 text-ae-green" : "bg-ae-amber/10 text-ae-amber"
                        )}>{d.status}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Ask panel */}
          <div className="flex flex-col gap-4">
            <div className="rounded-2xl border border-white/[0.07] bg-ae-surface/40 p-5">
              <div className="mb-4 flex items-center gap-2">
                <Send size={14} className="text-ae-muted" />
                <h3 className="text-sm font-semibold text-ae-text">Ask a Question</h3>
              </div>
              <form onSubmit={handleAsk} className="flex flex-col gap-3">
                <textarea
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="What does the document say about…"
                  rows={5}
                  className="w-full resize-none rounded-xl border border-white/[0.08] bg-ae-base/60 px-4 py-3 font-mono text-sm text-ae-text placeholder-ae-muted outline-none transition-colors focus:border-ae-cyan/40"
                />
                <button
                  type="submit"
                  disabled={askLoading || !question.trim()}
                  className="flex items-center justify-center gap-2 rounded-xl border border-ae-violet/20 bg-ae-violet/5 px-4 py-2.5 text-sm font-semibold text-ae-violet transition-all hover:border-ae-violet/40 hover:bg-ae-violet/10 disabled:opacity-50"
                >
                  {askLoading ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
                  {askLoading ? "Asking…" : "Ask"}
                </button>
              </form>
              {askError && <div className="mt-3"><ErrorBanner msg={askError} /></div>}
            </div>

            {/* Answer */}
            <AnimatePresence>
              {answer && (
                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="flex flex-col gap-3"
                >
                  <div className="rounded-2xl border border-ae-violet/20 bg-ae-violet/5 p-5">
                    <div className="mb-2 flex items-center justify-between">
                      <p className="font-mono text-[9px] font-bold uppercase tracking-[0.18em] text-ae-violet">ANSWER</p>
                      <span className="font-mono text-[9px] text-ae-faint">{answer.model} · {answer.provider}</span>
                    </div>
                    <p className="text-sm leading-relaxed text-ae-text whitespace-pre-wrap">
                      {answer.answer}
                    </p>
                  </div>

                  {answer.citations.length > 0 && (
                    <div className="rounded-2xl border border-white/[0.07] bg-ae-surface/40 p-5">
                      <p className="mb-3 font-mono text-[9px] font-bold uppercase tracking-[0.18em] text-ae-muted">
                        CITATIONS — {answer.citations.length}
                      </p>
                      <div className="flex flex-col gap-2">
                        {answer.citations.map((c, i) => (
                          <div key={i} className="rounded-xl border border-ae-cyan/10 bg-ae-base/60 px-3 py-2">
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-[10px] text-ae-cyan">{c.citation_label}</span>
                              <span className="text-[10px] text-ae-muted">{c.filename}</span>
                              <span className="ml-auto font-mono text-[9px] text-ae-faint">chunk {c.chunk_index}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  );
}

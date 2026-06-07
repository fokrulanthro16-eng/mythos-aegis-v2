"use client";

import { useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ImageIcon, Scan, X, Loader2, FileText } from "lucide-react";
import { apiUpload } from "@/lib/api";
import { getProjectId } from "@/lib/demo-config";
import { DemoAuthBar } from "@/components/demo-auth-bar";
import { cn } from "@/lib/utils";

interface VisionAnalyzeResponse {
  summary: string;
  model: string;
  provider: string;
  content_type?: string;
  image_size_bytes?: number;
  filename?: string;
}

function ErrorBanner({ msg }: { msg: string }) {
  return (
    <div className="flex items-center gap-2 rounded-xl border border-ae-red/30 bg-ae-red/10 px-4 py-2.5 text-sm text-ae-red">
      <X size={13} className="shrink-0" />
      <span>{msg}</span>
    </div>
  );
}

export default function VisionPage() {
  const [prompt, setPrompt] = useState("Describe what you see in this image in detail.");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VisionAnalyzeResponse | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    setResult(null);
    setError(null);
    if (file.type.startsWith("image/")) {
      const reader = new FileReader();
      reader.onload = (ev) => setPreview(ev.target?.result as string);
      reader.readAsDataURL(file);
    } else {
      setPreview(null);
    }
  }

  async function handleAnalyze(e: React.FormEvent) {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    const pid = getProjectId();
    if (!pid) { setError("Set a Project ID in the config bar above."); return; }
    setLoading(true);
    setError(null);
    setResult(null);
    const form = new FormData();
    form.append("file", file);
    form.append("project_id", pid);
    form.append("prompt", prompt);
    const { data, error: err } = await apiUpload<VisionAnalyzeResponse>(
      "/v1/vision/analyze",
      form
    );
    setLoading(false);
    if (err) { setError(err); return; }
    setResult(data);
  }

  return (
    <div className="h-full overflow-y-auto">
      <DemoAuthBar />
      <div className="flex flex-col gap-5 p-5">
        {/* Header */}
        <div>
          <p className="font-mono text-[9px] font-bold uppercase tracking-[0.2em] text-ae-muted">
            VISION ANALYSIS
          </p>
          <h2 className="text-xl font-semibold tracking-tight text-ae-text">
            Vision Provider
          </h2>
          <p className="mt-0.5 text-sm text-ae-muted">
            Upload an image · describe your analysis goal · receive AI-generated summary
          </p>
        </div>

        <div className="grid grid-cols-2 gap-5">
          {/* Input */}
          <div className="flex flex-col gap-4">
            <div className="rounded-2xl border border-white/[0.07] bg-ae-surface/40 p-5">
              <div className="mb-4 flex items-center gap-2">
                <ImageIcon size={14} className="text-ae-muted" />
                <h3 className="text-sm font-semibold text-ae-text">File Input</h3>
              </div>
              <form onSubmit={handleAnalyze} className="flex flex-col gap-4">
                <label className="flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed border-white/10 bg-ae-base/40 px-4 py-8 text-center transition-colors hover:border-ae-amber/30 hover:bg-ae-amber/5">
                  {preview ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={preview} alt="preview" className="max-h-32 max-w-full rounded-lg object-contain" />
                  ) : (
                    <>
                      <ImageIcon size={24} className="text-ae-muted" />
                      <span className="text-sm text-ae-muted">Click to select image</span>
                      <span className="font-mono text-[10px] text-ae-faint">JPEG · PNG · WebP · GIF</span>
                    </>
                  )}
                  {fileName && !preview && (
                    <div className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-ae-base px-2.5 py-1">
                      <FileText size={11} className="text-ae-amber" />
                      <span className="font-mono text-[10px] text-ae-text">{fileName}</span>
                    </div>
                  )}
                  <input
                    ref={fileRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp,image/gif"
                    className="hidden"
                    onChange={handleFileChange}
                  />
                </label>

                <div className="flex flex-col gap-1.5">
                  <label className="font-mono text-[9px] uppercase tracking-widest text-ae-muted">
                    Analysis Prompt
                  </label>
                  <textarea
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    rows={3}
                    className="w-full resize-none rounded-xl border border-white/[0.08] bg-ae-base/60 px-4 py-3 font-mono text-sm text-ae-text placeholder-ae-muted outline-none transition-colors focus:border-ae-amber/40"
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading || !fileName}
                  className={cn(
                    "flex items-center justify-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-semibold transition-all disabled:opacity-50",
                    "border-ae-amber/20 bg-ae-amber/5 text-ae-amber hover:border-ae-amber/40 hover:bg-ae-amber/10"
                  )}
                >
                  {loading ? <Loader2 size={13} className="animate-spin" /> : <Scan size={13} />}
                  {loading ? "Analyzing…" : "Analyze"}
                </button>
              </form>
              {error && <div className="mt-3"><ErrorBanner msg={error} /></div>}
            </div>
          </div>

          {/* Result */}
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
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
                  >
                    <Scan size={28} className="text-ae-amber" />
                  </motion.div>
                  <p className="font-mono text-[11px] text-ae-muted">Processing visual input…</p>
                </motion.div>
              )}

              {result && !loading && (
                <motion.div
                  key="result"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex flex-col gap-3"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full border border-ae-amber/30 bg-ae-amber/10 px-2.5 py-0.5 font-mono text-[10px] text-ae-amber">
                      {result.model}
                    </span>
                    <span className="rounded-full border border-white/10 bg-ae-base px-2.5 py-0.5 font-mono text-[10px] text-ae-muted">
                      {result.provider}
                    </span>
                    {result.content_type && (
                      <span className="rounded-full border border-white/10 bg-ae-base px-2.5 py-0.5 font-mono text-[10px] text-ae-muted">
                        {result.content_type}
                      </span>
                    )}
                  </div>

                  <div className="rounded-2xl border border-ae-amber/20 bg-ae-amber/5 p-5">
                    <p className="mb-2 font-mono text-[9px] font-bold uppercase tracking-[0.18em] text-ae-amber">
                      SUMMARY
                    </p>
                    <p className="text-sm leading-relaxed text-ae-text whitespace-pre-wrap">
                      {result.summary}
                    </p>
                  </div>
                </motion.div>
              )}

              {!result && !loading && (
                <motion.div
                  key="empty"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-white/[0.07] bg-ae-surface/20 p-12 text-center"
                >
                  <ImageIcon size={28} className="text-ae-faint" />
                  <p className="font-mono text-[11px] text-ae-faint">
                    Upload an image and click Analyze
                  </p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  );
}

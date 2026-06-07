"use client";

import { useState, useEffect } from "react";
import { KeyRound, Hash, ChevronDown, ChevronUp, Save } from "lucide-react";
import { saveToken, saveProjectId, isValidUUID } from "@/lib/demo-config";
import { cn } from "@/lib/utils";

export function DemoAuthBar() {
  const [token, setToken] = useState("");
  const [projectId, setProjectId] = useState("");
  const [open, setOpen] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const t = localStorage.getItem("aegis_token") ?? "";
    const p = localStorage.getItem("aegis_project_id") ?? "";
    setToken(t);
    setProjectId(p);
    if (!t || !p) setOpen(true);
  }, []);

  function handleSave() {
    saveToken(token);
    saveProjectId(projectId);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
    if (token && isValidUUID(projectId)) setOpen(false);
  }

  const hasToken = !!token;
  const validProject = isValidUUID(projectId);
  const allSet = hasToken && validProject;

  return (
    <div
      className={cn(
        "border-b text-[11px] transition-all",
        allSet ? "border-ae-green/20 bg-ae-green/5" : "border-ae-amber/25 bg-ae-amber/5"
      )}
    >
      {/* Status bar */}
      <div className="flex items-center gap-3 px-5 py-2">
        <div className="flex items-center gap-1.5">
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              allSet ? "bg-ae-green" : "bg-ae-amber"
            )}
            style={allSet ? { boxShadow: "0 0 6px #10b981" } : {}}
          />
          <span
            className={cn(
              "font-mono font-bold uppercase tracking-widest",
              allSet ? "text-ae-green" : "text-ae-amber"
            )}
          >
            {allSet ? "DEMO CONNECTED" : "DEMO SETUP REQUIRED"}
          </span>
        </div>
        {hasToken && (
          <span className="flex items-center gap-1 text-ae-muted">
            <KeyRound size={10} />
            token set
          </span>
        )}
        {validProject && (
          <span className="flex items-center gap-1 text-ae-muted">
            <Hash size={10} />
            {projectId.slice(0, 8)}…
          </span>
        )}
        {!allSet && (
          <span className="text-ae-amber">
            {!hasToken && !validProject
              ? "Set JWT token and project ID below"
              : !hasToken
              ? "JWT token missing"
              : "Project ID missing or invalid UUID"}
          </span>
        )}
        <button
          onClick={() => setOpen((v) => !v)}
          className="ml-auto flex items-center gap-1 rounded px-2 py-0.5 text-ae-muted hover:text-ae-text"
        >
          {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          configure
        </button>
      </div>

      {/* Config panel */}
      {open && (
        <div className="border-t border-white/[0.06] px-5 py-3">
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex flex-col gap-1 flex-1 min-w-48">
              <label className="font-mono text-[9px] uppercase tracking-widest text-ae-muted">
                JWT Token (Bearer)
              </label>
              <input
                type="password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="eyJhbGciOiJIUzI1NiIsInR5..."
                className="rounded-lg border border-white/[0.08] bg-ae-base/60 px-3 py-1.5 font-mono text-xs text-ae-text placeholder-ae-faint outline-none focus:border-ae-cyan/40"
              />
            </div>
            <div className="flex flex-col gap-1 flex-1 min-w-48">
              <label className="font-mono text-[9px] uppercase tracking-widest text-ae-muted">
                Project ID (UUID)
              </label>
              <input
                type="text"
                value={projectId}
                onChange={(e) => setProjectId(e.target.value)}
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                className={cn(
                  "rounded-lg border bg-ae-base/60 px-3 py-1.5 font-mono text-xs text-ae-text placeholder-ae-faint outline-none",
                  projectId && !validProject
                    ? "border-ae-red/40 focus:border-ae-red/60"
                    : "border-white/[0.08] focus:border-ae-cyan/40"
                )}
              />
            </div>
            <button
              onClick={handleSave}
              className={cn(
                "flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-semibold transition-all",
                saved
                  ? "border-ae-green/40 bg-ae-green/10 text-ae-green"
                  : "border-ae-cyan/20 bg-ae-cyan/5 text-ae-cyan hover:border-ae-cyan/40 hover:bg-ae-cyan/10"
              )}
            >
              <Save size={11} />
              {saved ? "Saved" : "Save"}
            </button>
          </div>
          <p className="mt-2 text-ae-faint">
            Generate a token:{" "}
            <code className="font-mono text-ae-cyan text-[10px]">
              python -c &quot;from app.auth.jwt import create_token; print(create_token(tenant_id=&apos;...&apos;))&quot;
            </code>
          </p>
        </div>
      )}
    </div>
  );
}

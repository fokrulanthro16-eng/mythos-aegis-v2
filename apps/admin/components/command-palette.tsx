"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Search, CornerDownLeft, ArrowUp, ArrowDown } from "lucide-react";
import { commandItems } from "@/lib/mock-data";
import { cn } from "@/lib/utils";

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
}

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  const filtered = query.trim()
    ? commandItems.filter((item) =>
        item.label.toLowerCase().includes(query.toLowerCase()) ||
        item.group.toLowerCase().includes(query.toLowerCase())
      )
    : commandItems;

  // Group filtered results
  const grouped = filtered.reduce<Record<string, typeof commandItems>>(
    (acc, item) => {
      if (!acc[item.group]) acc[item.group] = [];
      acc[item.group].push(item);
      return acc;
    },
    {}
  );

  const flatItems = filtered;

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50);
      setQuery("");
      setSelected(0);
    }
  }, [open]);

  useEffect(() => {
    setSelected(0);
  }, [query]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!open) return;
      if (e.key === "Escape") {
        onClose();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelected((s) => Math.min(s + 1, flatItems.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelected((s) => Math.max(s - 1, 0));
      } else if (e.key === "Enter") {
        const item = flatItems[selected];
        if (item) {
          router.push(item.href);
          onClose();
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, selected, flatItems, router, onClose]);

  const handleSelect = (href: string) => {
    router.push(href);
    onClose();
  };

  let itemIndex = 0;

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm"
            onClick={onClose}
          />

          {/* Panel */}
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: -12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -12 }}
            transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
            className="fixed left-1/2 top-[20%] z-50 w-full max-w-xl -translate-x-1/2 overflow-hidden rounded-2xl shadow-panel"
            style={{
              background: "rgba(12, 18, 28, 0.95)",
              border: "1px solid rgba(255,255,255,0.10)",
              boxShadow: "0 0 0 1px rgba(255,255,255,0.08), 0 24px 80px rgba(0,0,0,0.7), 0 0 60px rgba(0,212,255,0.06)",
            }}
          >
            {/* Search input */}
            <div className="flex items-center gap-3 border-b border-white/[0.07] px-4 py-4">
              <Search size={15} className="shrink-0 text-ae-muted" />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search commands, tenants, routes…"
                className="flex-1 bg-transparent text-sm text-ae-text placeholder-ae-muted outline-none"
              />
              {query && (
                <button
                  onClick={() => setQuery("")}
                  className="text-xs text-ae-muted hover:text-ae-text"
                >
                  Clear
                </button>
              )}
            </div>

            {/* Results */}
            <div className="max-h-80 overflow-y-auto py-2">
              {Object.entries(grouped).map(([group, items]) => (
                <div key={group}>
                  <div className="px-4 py-1.5">
                    <span className="text-[10px] font-semibold uppercase tracking-widest text-ae-muted">
                      {group}
                    </span>
                  </div>
                  {items.map((item) => {
                    const idx = itemIndex++;
                    const isSelected = idx === selected;
                    return (
                      <button
                        key={item.id}
                        onClick={() => handleSelect(item.href)}
                        onMouseEnter={() => setSelected(idx)}
                        className={cn(
                          "flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors",
                          isSelected
                            ? "bg-ae-cyan/10 text-ae-cyan"
                            : "text-ae-text hover:bg-white/[0.03]"
                        )}
                      >
                        <div
                          className={cn(
                            "flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-[10px] font-bold",
                            isSelected
                              ? "bg-ae-cyan/20 text-ae-cyan"
                              : "bg-white/[0.06] text-ae-muted"
                          )}
                        >
                          {item.group[0]}
                        </div>
                        <span>{item.label}</span>
                        {isSelected && (
                          <CornerDownLeft
                            size={12}
                            className="ml-auto text-ae-muted"
                          />
                        )}
                      </button>
                    );
                  })}
                </div>
              ))}

              {filtered.length === 0 && (
                <div className="px-4 py-8 text-center text-sm text-ae-muted">
                  No commands found for &quot;{query}&quot;
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between border-t border-white/[0.06] px-4 py-2.5">
              <div className="flex items-center gap-3 text-[10px] text-ae-muted">
                <span className="flex items-center gap-1">
                  <ArrowUp size={10} />
                  <ArrowDown size={10} />
                  Navigate
                </span>
                <span className="flex items-center gap-1">
                  <CornerDownLeft size={10} />
                  Select
                </span>
                <span>ESC Dismiss</span>
              </div>
              <span className="text-[10px] font-mono text-ae-muted">
                {filtered.length} commands
              </span>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

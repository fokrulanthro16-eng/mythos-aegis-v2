"use client";

import { useState, useEffect, useCallback } from "react";
import { LeftRail } from "./left-rail";
import { TopCommandBar } from "./top-command-bar";
import { LiveEventStream } from "./live-event-stream";
import { CommandPalette } from "@/components/command-palette";

interface CommandShellProps {
  children: React.ReactNode;
}

export function CommandShell({ children }: CommandShellProps) {
  const [paletteOpen, setPaletteOpen] = useState(false);

  const openPalette = useCallback(() => setPaletteOpen(true), []);
  const closePalette = useCallback(() => setPaletteOpen(false), []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setPaletteOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-ae-base text-ae-text">
      {/* Background */}
      <div className="pointer-events-none fixed inset-0 bg-radial-base" />
      <div
        className="pointer-events-none fixed inset-0 opacity-40"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.015) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.015) 1px, transparent 1px)",
          backgroundSize: "52px 52px",
        }}
      />

      {/* Left rail */}
      <LeftRail />

      {/* Main column */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <TopCommandBar onOpenPalette={openPalette} />

        {/* Content + right rail */}
        <div className="flex flex-1 overflow-hidden">
          <main className="flex-1 overflow-hidden">
            {children}
          </main>
          <LiveEventStream />
        </div>
      </div>

      {/* Command Palette overlay */}
      <CommandPalette open={paletteOpen} onClose={closePalette} />
    </div>
  );
}

"use client";

import { useState, useEffect } from "react";
import { relativeTime } from "@/lib/utils";

interface RelativeTimeProps {
  date: Date;
  className?: string;
}

/**
 * Renders a relative timestamp safely across SSR and client hydration.
 * Shows "—" on the server and on first render, then switches to the
 * computed relative string after mount and refreshes every 30 seconds.
 */
export function RelativeTime({ date, className }: RelativeTimeProps) {
  const [text, setText] = useState("—");

  useEffect(() => {
    setText(relativeTime(date));
    const id = setInterval(() => setText(relativeTime(date)), 30_000);
    return () => clearInterval(id);
  }, [date]);

  return <span className={className}>{text}</span>;
}

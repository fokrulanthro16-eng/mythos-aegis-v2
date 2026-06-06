"use client";

import { useState, useEffect } from "react";

/** Returns false during SSR and the first render, true after mount.
 *  Use this to gate any value that differs between server and client. */
export function useHydrated(): boolean {
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => {
    setHydrated(true);
  }, []);
  return hydrated;
}

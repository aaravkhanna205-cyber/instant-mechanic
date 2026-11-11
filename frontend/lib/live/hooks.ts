"use client";
import { useCallback, useEffect, useState } from "react";
import { errorText } from "@/lib/api/phase3";

type LoadState<T> = { source: unknown; data: T | null; error: string };

/**
 * Runs a stable (useCallback) loader and re-runs it on `reload()`.
 * Pass `null` while the inputs are not ready. Data stays visible during a reload,
 * but results from a previous loader (for example another organization) are never shown.
 */
export function useLoad<T>(loader: (() => Promise<T>) | null) {
  const [state, setState] = useState<LoadState<T>>({ source: null, data: null, error: "" });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!loader) return;
    let alive = true;
    loader()
      .then((data) => { if (alive) setState({ source: loader, data, error: "" }); })
      .catch((error) => {
        if (alive) setState((current) => ({ source: loader, data: current.source === loader ? current.data : null, error: errorText(error) }));
      });
    return () => {
      alive = false;
    };
  }, [loader, tick]);
  const reload = useCallback(() => setTick((n) => n + 1), []);
  const current = loader !== null && state.source === loader;
  return { data: current ? state.data : null, error: current ? state.error : "", loading: loader !== null && !current, reload };
}

/** Wraps a mutation with busy, error and success-message state. */
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const run = useCallback(async (work: () => Promise<unknown>, success = "") => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await work();
      setNotice(success);
      return true;
    } catch (failure) {
      setError(errorText(failure));
      return false;
    } finally {
      setBusy(false);
    }
  }, []);
  const clear = useCallback(() => { setError(""); setNotice(""); }, []);
  return { busy, error, notice, run, clear };
}

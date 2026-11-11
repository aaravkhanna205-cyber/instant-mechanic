"use client";
import { useCallback, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { ApiError, errorText } from "@/lib/api/phase3";

/**
 * Returns a function that sends the person to sign-in when the server says the
 * session is gone (expired, signed out elsewhere, or the account was closed).
 */
function useSessionGuard() {
  const router = useRouter();
  const pathname = usePathname();
  return useCallback((error: unknown) => {
    if (!(error instanceof ApiError) || error.status !== 401) return false;
    router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    return true;
  }, [router, pathname]);
}

type LoadState<T> = { source: unknown; data: T | null; error: string };

/**
 * Runs a stable (useCallback) loader and re-runs it on `reload()`.
 * Pass `null` while the inputs are not ready. Data stays visible during a reload,
 * but results from a previous loader (for example another organization) are never shown.
 */
export function useLoad<T>(loader: (() => Promise<T>) | null) {
  const [state, setState] = useState<LoadState<T>>({ source: null, data: null, error: "" });
  const [tick, setTick] = useState(0);
  const expired = useSessionGuard();
  useEffect(() => {
    if (!loader) return;
    let alive = true;
    loader()
      .then((data) => { if (alive) setState({ source: loader, data, error: "" }); })
      .catch((error) => {
        if (!alive || expired(error)) return;
        if (alive) setState((current) => ({ source: loader, data: current.source === loader ? current.data : null, error: errorText(error) }));
      });
    return () => {
      alive = false;
    };
  }, [loader, tick, expired]);
  const reload = useCallback(() => setTick((n) => n + 1), []);
  const current = loader !== null && state.source === loader;
  return { data: current ? state.data : null, error: current ? state.error : "", loading: loader !== null && !current, reload };
}

/** Wraps a mutation with busy, error and success-message state. */
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const expired = useSessionGuard();
  const run = useCallback(async (work: () => Promise<unknown>, success = "") => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await work();
      setNotice(success);
      return true;
    } catch (failure) {
      if (!expired(failure)) setError(errorText(failure));
      return false;
    } finally {
      setBusy(false);
    }
  }, [expired]);
  const clear = useCallback(() => { setError(""); setNotice(""); }, []);
  return { busy, error, notice, run, clear };
}

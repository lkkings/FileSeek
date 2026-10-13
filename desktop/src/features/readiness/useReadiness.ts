import { useEffect, useState } from "react";

import { getReadiness, onReadinessChange, type Readiness } from "../../services/tauri/readiness";

export interface ReadinessView {
  readiness: Readiness | null;
  /** The backend has been ready at least once since the window opened. */
  everReady: boolean;
  /** A download step has been seen, so this is a first run rather than a plain start. */
  installing: boolean;
}

const DOWNLOAD_STATES = new Set(["space_check", "downloading", "verifying", "installing"]);

export function useReadiness(): ReadinessView {
  const [view, setView] = useState<ReadinessView>({ readiness: null, everReady: false, installing: false });

  useEffect(() => {
    let disposed = false;
    let unsubscribe: (() => void) | undefined;
    const apply = (readiness: Readiness) => {
      if (disposed) return;
      setView((current) => ({
        readiness,
        everReady: current.everReady || readiness.state === "ready",
        installing:
          current.installing ||
          DOWNLOAD_STATES.has(readiness.state) ||
          (readiness.failedStep !== null && DOWNLOAD_STATES.has(readiness.failedStep)),
      }));
    };

    // Subscribe before reading the current state, so a change in between is not lost; and
    // once an event has arrived, the (possibly older) initial read must not overwrite it.
    let sawEvent = false;
    void onReadinessChange((readiness) => {
      sawEvent = true;
      apply(readiness);
    }).then((stop) => {
      if (disposed) stop();
      else unsubscribe = stop;
    });
    void getReadiness()
      .then((readiness) => {
        if (!sawEvent) apply(readiness);
      })
      .catch(() => {});

    return () => {
      disposed = true;
      unsubscribe?.();
    };
  }, []);

  return view;
}

import { createContext, type ReactNode, useContext, useEffect, useMemo, useState } from "react";

import { browserEntitlement, getEntitlement, onEntitlementChange, type Entitlement } from "../../services/tauri/license";

interface LicenseContextValue {
  entitlement: Entitlement;
  setEntitlement: (entitlement: Entitlement) => void;
}

const LicenseContext = createContext<LicenseContextValue>({
  entitlement: browserEntitlement,
  setEntitlement: () => {},
});

/**
 * The entitlement as Rust last decided it. Rust pushes every change (launch check,
 * activation, the 24-hour check), so there is nothing to poll.
 */
export function LicenseProvider({ children }: { children: ReactNode }) {
  const [entitlement, setEntitlement] = useState<Entitlement>(browserEntitlement);

  useEffect(() => {
    let disposed = false;
    let unsubscribe: (() => void) | undefined;
    // Subscribe first, so a change between the read and the subscription is not lost;
    // once an event has arrived the (possibly older) initial read must not overwrite it.
    let sawEvent = false;
    void onEntitlementChange((next) => {
      sawEvent = true;
      if (!disposed) setEntitlement(next);
    }).then((stop) => {
      if (disposed) stop();
      else unsubscribe = stop;
    });
    void getEntitlement()
      .then((next) => {
        if (!disposed && !sawEvent) setEntitlement(next);
      })
      .catch(() => {});
    return () => {
      disposed = true;
      unsubscribe?.();
    };
  }, []);

  const value = useMemo(() => ({ entitlement, setEntitlement }), [entitlement]);

  return <LicenseContext.Provider value={value}>{children}</LicenseContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components -- the hook belongs with its provider
export function useLicense() {
  return useContext(LicenseContext);
}

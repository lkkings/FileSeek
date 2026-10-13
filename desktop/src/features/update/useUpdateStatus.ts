import { useEffect, useState } from "react";

import {
  browserUpdateStatus,
  getUpdateStatus,
  onUpdateStatusChange,
  type UpdateStatus,
} from "../../services/tauri/update";

export function useUpdateStatus(): [UpdateStatus, (status: UpdateStatus) => void] {
  const [status, setStatus] = useState<UpdateStatus>(browserUpdateStatus);

  useEffect(() => {
    let disposed = false;
    let sawEvent = false;
    let unsubscribe: (() => void) | undefined;
    void onUpdateStatusChange((next) => {
      sawEvent = true;
      if (!disposed) setStatus(next);
    }).then((stop) => {
      if (disposed) stop();
      else unsubscribe = stop;
    });
    void getUpdateStatus()
      .then((next) => {
        if (!disposed && !sawEvent) setStatus(next);
      })
      .catch(() => {});
    return () => {
      disposed = true;
      unsubscribe?.();
    };
  }, []);

  return [status, setStatus];
}
